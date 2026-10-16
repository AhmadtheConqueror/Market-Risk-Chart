"""Synthetic fixtures: bounded snapshot reads must preserve legacy calculations."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.models.historical import HistoricalMarketObservation as H
from app.models.macro import MacroIndicator
from app.services import official_market as official
from app.services.historical_market import load_historical_series, HISTORICAL_MAPPING
from app.services import macro_ingestion as macro


@pytest.mark.parametrize("sparse", [False, True])
def test_snapshot_window_matches_full_history(db_session, seed_platts_data, monkeypatch, sparse):
    # Add older history; sparse products deliberately need Brent outside its 90D window.
    for key, spec in HISTORICAL_MAPPING.items():
        for days in (120, 240, 400):
            db_session.add(H(instrument_key=key, provider="platts_excel", provider_symbol=spec[0],
                assessment_date=date(2026, 9, 24)-timedelta(days=days), native_value=Decimal("42"),
                native_unit=spec[2], converted_value=42, benchmark_definition="SYNTHETIC",
                workbook_source="SYNTHETIC.xlsx", workbook_sha256="0"*64, worksheet="SYNTHETIC",
                imported_at=datetime(2026, 9, 25, tzinfo=timezone.utc)))
    db_session.flush()
    if sparse:
        from sqlalchemy import delete
        db_session.execute(delete(H).where(H.instrument_key == "jet",
            H.assessment_date > date(2026, 9, 24)-timedelta(days=240)))
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 16, tzinfo=timezone.utc)
    monkeypatch.setattr(official, "datetime", Frozen)
    bounded = official.load_snapshot_history(db_session)
    full = load_historical_series(db_session)
    assert sum(map(len, bounded.values())) < sum(map(len, full.values()))
    actual = official.official_market_snapshot(db_session)
    monkeypatch.setattr(official, "load_snapshot_history", load_historical_series)
    expected = official.official_market_snapshot(db_session)
    def dump(result):
        return [[item.model_dump(mode="json") for item in group] for group in result]
    assert dump(actual) == dump(expected)
    assert len(full["brent"]) == 94


def test_macro_rank_matches_python_for_irregular_periods_and_ties(db_session):
    periods = ["2026-02-28", "2026-02-30", "2026", "Aug 2026", "August 2026",
               "Q4 2026", "Q1 2027", "Mystery 2026", "unknown", " 2026-12-31 "]
    now = datetime.now(timezone.utc)
    for key, config in macro.CANONICAL_MACRO_CONFIG.items():
        for i, period in enumerate(periods + [str(now.year), str(now.year+1)]):
            for source_index in range(2):
                db_session.add(MacroIndicator(indicator_key=key, display_name=config["display_name"],
                    value=Decimal(i), unit=config["unit"], reporting_period=period,
                    source=f"SYNTHETIC {i}-{source_index}",
                    published_at=now if source_index else None, retrieved_at=now,
                    metadata_json={"synthetic": True}))
    db_session.flush()
    all_records = db_session.scalars(select(MacroIndicator)).all()
    actual = {r.indicator_key: r for r in macro.get_latest_macro_indicators(db_session)}
    for key, config in macro.CANONICAL_MACRO_CONFIG.items():
        rows = [r for r in all_records if r.indicator_key == key and
            (config["frequency"] not in {"weo", "outlook"} or r.reporting_period == str(now.year))]
        reference = max(rows, key=macro.period_sort_key)
        assert actual[key].model_dump() == macro.macro_response(reference).model_dump()


def test_macro_empty_database_is_honestly_unavailable(db_session):
    result = macro.get_latest_macro_indicators(db_session)
    assert len(result) == len(macro.CANONICAL_MACRO_CONFIG)
    assert all(r.value is None and r.status == "unavailable" for r in result)


@pytest.mark.parametrize("periods", [
    ["Aug 2026", "September 2026"],
    ["Q2 2026", "May 2026"],
    ["2026-02-30", "2026-02-28"],
    ["unknown", "also unknown"],
    ["Aug 2026", "August 2026"],
    ["0001-01-01", "unknown"],
    ["Mystery 2026", "Jan 2026"],
])
def test_macro_period_and_id_ordering_edges(db_session, periods):
    now = datetime.now(timezone.utc)
    for i, period in enumerate(periods):
        db_session.add(MacroIndicator(indicator_key="headline_inflation", display_name="SYNTHETIC",
            value=i, unit="%", reporting_period=period, source=f"SYNTHETIC {i}",
            published_at=None, retrieved_at=now))
    db_session.flush()
    rows = db_session.scalars(select(MacroIndicator)).all()
    expected = max(rows, key=macro.period_sort_key)
    actual = next(r for r in macro.get_latest_macro_indicators(db_session)
                  if r.indicator_key == "headline_inflation")
    assert actual.id == expected.id
    assert actual.reporting_period == expected.reporting_period
