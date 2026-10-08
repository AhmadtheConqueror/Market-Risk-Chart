from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from openpyxl import load_workbook
from app.models.historical import HistoricalMarketObservation as Historical
from app.services.excel_ingestion import ExcelObservation, ExcelValidationError, parse_excel_date, parse_nullable_number

# These definitions are intentionally independent of API source policies/defaults.
HISTORICAL_MAPPING = {
    "brent": ("PCAAS00", "Platts Dated Brent", "USD/BBL", None, "PAAAM00_PCAAS00_naphtha_crack_s", 3),
    "naphtha": ("PAAAM00", "Platts Naphtha FOB Rotterdam", "USD/MT", 8.9000, "PAAAM00_PCAAS00_naphtha_crack_s", 2),
    "gasoil": ("AAVJI00", "Platts Gasoil 0.1%S FOB Med", "USD/MT", 7.3137, "AAVJI00_PCAAS00_Gasoi_crak_spre", 2),
    "gasoline": ("PGABM00", "Platts Gasoline Prem 10ppmS FOB AR Barge", "USD/MT", 8.5286, "PGABM00_PCAAS00_gasoline_crack_", 3),
    "forcados": ("PCABC00", "Platts Forcados FOB Nigeria", "USD/BBL", None, "Market Risk", None),
    "wti": ("PCACG00", "Platts WTI Cushing Mo01", "USD/BBL", None, "Market Risk", None),
    "jet": ("PJAAV00", "Platts Jet FOB NWE Cargo", "USD/MT", 7.7892, "PCAAS00_minus_PJAAV00_jet_crack", 3),
}


def parse_historical_workbook(file_bytes: bytes):
    try:
        workbook = load_workbook(BytesIO(file_bytes), data_only=True)
    except Exception as exc:
        raise ExcelValidationError("Workbook could not be opened as a valid .xlsx file.") from exc
    if "Market Risk" not in workbook.sheetnames:
        raise ExcelValidationError("Required sheet 'Market Risk' is missing.")
    market = workbook["Market Risk"]
    symbol_columns = {}
    symbol_row = 0
    symbols = {v[0] for v in HISTORICAL_MAPPING.values()}
    for row in market.iter_rows(min_row=1, max_row=min(60,market.max_row)):
        matches = {str(c.value).strip(): c.column for c in row if str(c.value).strip() in symbols}
        if len(matches)>len(symbol_columns):
            symbol_columns, symbol_row = matches, row[0].row
    if not symbol_columns:
        raise ExcelValidationError("Required Platts columns were not found in the Market Risk sheet.")
    date_column = None
    for row in market.iter_rows(min_row=symbol_row, max_row=symbol_row+8):
        for cell in row:
            if date_column is None and str(cell.value).lower().replace(" ","") in {"date","assessdate","assessmentdate"}:
                date_column = cell.column
    if date_column is None:
        raise ExcelValidationError("Required AssessDate column was not found.")
    selected = []
    rejected = rows_read = 0
    errors = []
    for key,(symbol,label,unit,factor,sheet,column) in HISTORICAL_MAPPING.items():
        candidates = []
        if symbol in symbol_columns:
            mc = symbol_columns[symbol]
            actual_unit = f"{market.cell(symbol_row+3,mc).value}/{market.cell(symbol_row+2,mc).value}".upper()
            if actual_unit != unit:
                raise ExcelValidationError(f"Unexpected unit for {symbol}: found '{actual_unit}', expected '{unit}'.")
            candidates.append((market,symbol_row+5,date_column,mc))
        if sheet != "Market Risk" and sheet in workbook.sheetnames:
            ws = workbook[sheet]
            header = str(ws.cell(1,column).value)
            if symbol not in header or ("mt" if factor else "bbl") not in header.lower():
                raise ExcelValidationError(f"Unexpected historical column for {symbol} in {sheet}.")
            candidates.append((ws,2,1,column))
        histories = []
        for ws,start,dc,vc in candidates:
            history = {}
            local_rejected = local_rows = 0
            for row in ws.iter_rows(min_row=start,values_only=True):
                raw_date, raw_value = row[dc-1], row[vc-1]
                if raw_date is None and raw_value is None:
                    continue
                assessment = parse_excel_date(raw_date,workbook.epoch)
                # Ignore descriptive/filter cells before the table's actual data.
                local_rows += 1
                value = parse_nullable_number(raw_value)
                if assessment is None or value is None:
                    local_rejected += 1
                    continue
                if assessment in history:
                    local_rejected += 1
                    if len(errors)<50: errors.append(f"{symbol}: duplicate assessment date {assessment} in {ws.title}.")
                    continue
                history[assessment] = ExcelObservation(key,symbol,value,unit,assessment,label,
                    value/factor if factor else value,factor,ws.title)
            histories.append((history,local_rows,local_rejected))
        if histories:
            # Prefer the longest authoritative copy. Never concatenate worksheet copies.
            history,local_rows,local_rejected = max(histories,key=lambda h:(len(h[0]),max(h[0],default=date.min)))
            selected.extend(history[d] for d in sorted(history))
            rows_read += local_rows
            rejected += local_rejected
    if not selected:
        raise ExcelValidationError("No valid supported market observations were found in the workbook.")
    dates=[o.assessment_date for o in selected]
    return selected, {"rows_read":rows_read,"rows_valid":len(selected),"rows_rejected":rejected,
        "instruments_affected":sorted({o.instrument_key for o in selected}),
        "date_range":{"from":str(min(dates)),"to":str(max(dates))},"errors":errors,
        "uploaded_at":datetime.now(timezone.utc).isoformat()}


def persist_history(session: Session, observations, file_bytes: bytes, filename: str, imported_at: datetime):
    existing={(o.instrument_key,o.provider_symbol,o.assessment_date) for o in session.scalars(
        select(Historical).where(Historical.provider=="platts_excel")).all()}
    records=[dict(instrument_key=o.instrument_key,provider="platts_excel",provider_symbol=o.provider_symbol,
        benchmark_definition=o.benchmark_definition,assessment_date=o.assessment_date,
        native_value=Decimal(str(o.value)),native_unit=o.unit,
        converted_value=Decimal(str(o.converted_value)),conversion_factor=Decimal(str(o.conversion_factor)) if o.conversion_factor else None,
        workbook_source=Path(filename.replace("\\","/")).name[:255],workbook_sha256=sha256(file_bytes).hexdigest(),
        worksheet=o.worksheet,imported_at=imported_at) for o in observations]
    stored=sum((o.instrument_key,o.provider_symbol,o.assessment_date) not in existing for o in observations)
    dialect=session.get_bind().dialect.name
    insert = pg_insert if dialect=="postgresql" else sqlite_insert if dialect=="sqlite" else None
    if insert is None:
        raise ExcelValidationError("Historical imports require PostgreSQL or SQLite.")
    # Batches avoid SQLite/PostgreSQL bind-parameter limits.
    for offset in range(0,len(records),100):
        stmt=insert(Historical).values(records[offset:offset+100])
        stmt=stmt.on_conflict_do_update(index_elements=["instrument_key","provider","provider_symbol","assessment_date"],
            set_={k:getattr(stmt.excluded,k) for k in records[0] if k not in {"instrument_key","provider","provider_symbol","assessment_date"}})
        session.execute(stmt)
    return stored,len(records)-stored


def historical_analytics(session: Session, today: date | None = None):
    today=today or datetime.now(timezone.utc).date()
    rows=session.scalars(select(Historical).where(Historical.provider=="platts_excel").order_by(Historical.assessment_date)).all()
    grouped={key:[] for key in HISTORICAL_MAPPING}
    for row in rows:
        if row.instrument_key in grouped and row.provider_symbol==HISTORICAL_MAPPING[row.instrument_key][0]:
            grouped[row.instrument_key].append(row)
    brent={r.assessment_date:float(r.native_value) for r in grouped["brent"]}
    instruments=[]
    for key,(symbol,label,unit,factor,_,_) in HISTORICAL_MAPPING.items():
        history=grouped[key]
        latest=history[-1] if history else None
        def window(days):
            return [r for r in history if r.assessment_date>=latest.assessment_date-timedelta(days=days-1)] if latest else []
        def change(days):
            subset=window(days)
            return float(subset[-1].native_value-subset[0].native_value) if len(subset)>1 else None
        previous=history[-2] if len(history)>1 else None
        instruments.append(dict(instrument=key,label=label,provider="platts_excel",symbol=symbol,unit=unit,
            latest_date=str(latest.assessment_date) if latest else None,
            latest=float(latest.native_value) if latest else None,
            change_1d=float(latest.native_value-previous.native_value) if previous else None,
            change_30d=change(30),change_90d=change(90),count_30d=len(window(30)),count_90d=len(window(90)),
            observation_count=len(history),freshness="stale" if latest and (today-latest.assessment_date).days>3 else "fresh" if latest else "unavailable",
            factor=factor,spread=(float(latest.converted_value)-brent[latest.assessment_date]) if latest and factor and latest.assessment_date in brent else None,
            workbook=latest.workbook_source if latest else None,worksheet=latest.worksheet if latest else None,
            imported_at=latest.imported_at.isoformat() if latest else None,
            points=[dict(date=str(r.assessment_date),value=float(r.native_value)) for r in window(90)]))
    return {"instruments":instruments,"spread_definition":"Converted product USD/bbl minus same-date Platts Dated Brent USD/bbl",
        "window_definition":"Inclusive calendar days ending at each instrument's latest valid observation; change is latest minus first valid observation in window."}
