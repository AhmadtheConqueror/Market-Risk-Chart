from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from openpyxl.utils.datetime import from_excel

EXCEL_PROVIDER = "internal_excel"

class ExcelValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ExcelObservation:
    instrument_key: str
    provider_symbol: str
    value: float
    unit: str
    assessment_date: date
    benchmark_definition: str
    converted_value: float | None = None
    conversion_factor: float | None = None
    worksheet: str = "Market Risk"


def parse_excel_date(value: Any, epoch: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        try:
            converted = from_excel(value, epoch)
            return converted.date() if isinstance(converted, datetime) else converted
        except (TypeError, ValueError, OverflowError):
            return None
    if isinstance(value, str) and value.strip():
        raw = value.strip()
        for parser in (datetime.fromisoformat,):
            try:
                return parser(raw.replace("Z", "+00:00")).date()
            except ValueError:
                pass
        for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                pass
    return None


def parse_nullable_number(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_market_workbook(file_bytes: bytes) -> tuple[list[ExcelObservation], dict[str, Any]]:
    from app.services.historical_market import parse_historical_workbook
    return parse_historical_workbook(file_bytes)
