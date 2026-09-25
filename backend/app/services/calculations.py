from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Sequence

# Canonical conversion factors (barrels per metric ton)
PRODUCT_CONVERSIONS: dict[str, float] = {
    "naphtha": 8.90,
    "gasoil": 7.44,
    "gasoline": 8.33,
    "jet": 7.70,
}

REFINED_PRODUCT_ORDER: list[str] = ["naphtha", "gasoil", "gasoline", "jet"]


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, Decimal):
        f_val = float(value)
        return f_val if math.isfinite(f_val) else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            f_val = float(stripped)
            return f_val if math.isfinite(f_val) else None
        except ValueError:
            return None
    return None


def calendar_window(
    observations: Sequence[dict[str, Any]],
    window_days: int = 90,
) -> list[dict[str, Any]]:
    """Filters observations within [latest_date - (window_days - 1), latest_date].

    Strict missing-data rule:
    - No interpolation
    - No forward-fill / back-fill
    - Missing dates remain omitted
    """
    valid_obs: list[tuple[date, dict[str, Any]]] = []
    for obs in observations:
        dt = parse_date(obs.get("assessment_date") or obs.get("date") or obs.get("assessmentDate"))
        val = to_float(obs.get("value"))
        if dt is not None and val is not None:
            valid_obs.append((dt, obs))

    if not valid_obs:
        return []

    valid_obs.sort(key=lambda item: item[0])
    latest_date = valid_obs[-1][0]
    start_date = latest_date - timedelta(days=window_days - 1)

    return [obs for dt, obs in valid_obs if start_date <= dt <= latest_date]


def calculate_mean(values: Sequence[float | None]) -> float | None:
    valid_values = [v for v in values if v is not None and math.isfinite(v)]
    if not valid_values:
        return None
    return sum(valid_values) / len(valid_values)


def calculate_sample_std_dev(
    values: Sequence[float | None],
    mean_value: float | None = None,
) -> float | None:
    """Calculates sample standard deviation using N - 1 divisor.

    Returns None if count < 2 or mean is None.
    """
    valid_values = [v for v in values if v is not None and math.isfinite(v)]
    if len(valid_values) < 2:
        return None

    if mean_value is None or not math.isfinite(mean_value):
        mean_value = sum(valid_values) / len(valid_values)

    variance = sum((x - mean_value) ** 2 for x in valid_values) / (len(valid_values) - 1)
    return math.sqrt(variance)


def calculate_z_score(
    current_value: float | None,
    mean_value: float | None,
    std_dev: float | None,
) -> float | None:
    """Calculates z-score: z = (current_value - mean_value) / std_dev.

    Returns None if std_dev is 0, None, or not positive.
    """
    if current_value is None or mean_value is None or std_dev is None:
        return None
    if not (math.isfinite(current_value) and math.isfinite(mean_value) and math.isfinite(std_dev)):
        return None
    if std_dev <= 0:
        return None
    return (current_value - mean_value) / std_dev


def calculate_change(
    current_value: float | None,
    previous_value: float | None,
) -> float | None:
    if current_value is None or previous_value is None:
        return None
    if not (math.isfinite(current_value) and math.isfinite(previous_value)):
        return None
    return current_value - previous_value


def calculate_percent_change(
    change: float | None,
    previous_value: float | None,
) -> float | None:
    """Calculates 1D % change: (change / |previous_value|) * 100.

    Returns None if previous_value is 0 or either value is None.
    """
    if change is None or previous_value is None:
        return None
    if not (math.isfinite(change) and math.isfinite(previous_value)):
        return None
    if previous_value == 0:
        return None
    return (change / abs(previous_value)) * 100.0


def calculate_instrument_stats(
    observations: Sequence[dict[str, Any]],
    window_days: int = 90,
    min_history_points: int | None = None,
) -> dict[str, Any]:
    """Calculates full statistical metrics for an instrument series.

    Expects observations sorted chronologically or will sort them by assessment_date.
    """
    valid_obs: list[tuple[date, float, dict[str, Any]]] = []
    for obs in observations:
        dt = parse_date(obs.get("assessment_date") or obs.get("date") or obs.get("assessmentDate"))
        val = to_float(obs.get("value"))
        if dt is not None and val is not None:
            valid_obs.append((dt, val, obs))

    if not valid_obs:
        return {
            "current_value": None,
            "previous_value": None,
            "change": None,
            "percent_change": None,
            "mean_90": None,
            "std_dev_90": None,
            "z_score": None,
            "window_count": 0,
            "history_status": "unavailable",
            "latest_date": None,
            "latest_observation": None,
        }

    valid_obs.sort(key=lambda item: item[0])
    latest_dt, current_val, latest_obs = valid_obs[-1]
    prev_val = valid_obs[-2][1] if len(valid_obs) >= 2 else None

    change = calculate_change(current_val, prev_val)
    pct_change = calculate_percent_change(change, prev_val)

    # 90-day window
    start_date = latest_dt - timedelta(days=window_days - 1)
    window_points = [val for dt, val, _ in valid_obs if start_date <= dt <= latest_dt]

    mean_val = calculate_mean(window_points)
    sd_val = calculate_sample_std_dev(window_points, mean_val)

    # Evaluate sufficiency if min_history_points is specified
    if min_history_points is not None and len(window_points) < min_history_points:
        z_score = None
        history_status = "insufficient_history"
    else:
        z_score = calculate_z_score(current_val, mean_val, sd_val)
        history_status = "valid"

    return {
        "current_value": current_val,
        "previous_value": prev_val,
        "change": change,
        "percent_change": pct_change,
        "mean_90": mean_val,
        "std_dev_90": sd_val,
        "z_score": z_score,
        "window_count": len(window_points),
        "history_status": history_status,
        "latest_date": latest_dt.isoformat(),
        "latest_observation": latest_obs,
    }


def convert_product_price(
    original_price: float | None,
    barrels_per_mt: float | None,
) -> float | None:
    """Converts price from USD/mt to USD/bbl: original_price / barrels_per_mt."""
    if original_price is None or barrels_per_mt is None:
        return None
    if not (math.isfinite(original_price) and math.isfinite(barrels_per_mt)):
        return None
    if barrels_per_mt <= 0:
        return None
    return original_price / barrels_per_mt


def calculate_product_spread(
    converted_price: float | None,
    brent_price: float | None,
) -> float | None:
    """Calculates product spread against Brent: converted_price (USD/bbl) - brent_price (USD/bbl)."""
    if converted_price is None or brent_price is None:
        return None
    if not (math.isfinite(converted_price) and math.isfinite(brent_price)):
        return None
    return converted_price - brent_price


def calculate_all_product_spreads(
    latest_by_instrument: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Calculates product spreads for standard refined products in canonical order."""
    brent_obs = latest_by_instrument.get("brent")
    brent_price = to_float(brent_obs.get("value") if brent_obs else None)

    spreads: list[dict[str, Any]] = []
    for instrument_id in REFINED_PRODUCT_ORDER:
        obs = latest_by_instrument.get(instrument_id)
        if not obs:
            continue

        orig_price = to_float(obs.get("value"))
        conversion_factor = (
            to_float(obs.get("barrels_per_mt") or obs.get("barrelsPerMT"))
            or PRODUCT_CONVERSIONS.get(instrument_id)
        )
        converted_price = convert_product_price(orig_price, conversion_factor)
        spread = calculate_product_spread(converted_price, brent_price)

        spreads.append({
            "instrument_id": instrument_id,
            "display_name": obs.get("display_name") or obs.get("name") or instrument_id.title(),
            "date": str(obs.get("assessment_date") or obs.get("date")),
            "original_price": orig_price,
            "original_unit": obs.get("unit", "USD/mt"),
            "barrels_per_mt": conversion_factor,
            "converted_price": converted_price,
            "brent_price": brent_price,
            "spread": spread,
            "is_comparable": converted_price is not None and brent_price is not None,
        })

    return spreads
