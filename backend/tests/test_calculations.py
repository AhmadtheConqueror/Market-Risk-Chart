from __future__ import annotations

import math
from datetime import date

import pytest

from app.services.calculations import (
    PRODUCT_CONVERSIONS,
    REFINED_PRODUCT_ORDER,
    calculate_all_product_spreads,
    calculate_change,
    calculate_instrument_stats,
    calculate_mean,
    calculate_percent_change,
    calculate_product_spread,
    calculate_sample_std_dev,
    calculate_z_score,
    calendar_window,
    convert_product_price,
    to_float,
)


def test_1d_change():
    assert calculate_change(75.50, 74.00) == 1.50
    assert calculate_change(70.00, 72.50) == -2.50
    assert calculate_change(70.00, 70.00) == 0.0
    assert calculate_change(None, 70.00) is None
    assert calculate_change(70.00, None) is None


def test_1d_percent_change():
    # 1.5 change on 74.00 base -> ~2.027%
    pct = calculate_percent_change(1.50, 74.00)
    assert pct is not None
    assert math.isclose(pct, (1.50 / 74.00) * 100.0, rel_tol=1e-6)

    # Negative change
    pct_neg = calculate_percent_change(-2.50, 72.50)
    assert pct_neg is not None
    assert math.isclose(pct_neg, (-2.50 / 72.50) * 100.0, rel_tol=1e-6)

    # Division by zero handling
    assert calculate_percent_change(5.0, 0.0) is None
    assert calculate_percent_change(None, 50.0) is None


def test_mean_calculation():
    values = [70.0, 72.0, 74.0, 76.0, 78.0]
    expected_mean = 74.0
    assert calculate_mean(values) == expected_mean

    # Single value
    assert calculate_mean([50.0]) == 50.0

    # Empty
    assert calculate_mean([]) is None

    # Handles None in series
    assert calculate_mean([70.0, None, 74.0]) == 72.0


def test_sample_standard_deviation():
    # Values: [10, 12, 23, 23, 16, 23, 21, 16]
    # N = 8, sum = 144, mean = 18
    # squared diffs: (10-18)^2 + (12-18)^2 + (23-18)^2 * 3 + (16-18)^2 * 2 + (21-18)^2
    # = 64 + 36 + 75 + 8 + 9 = 192
    # sample variance = 192 / (8 - 1) = 192 / 7 = 27.428571...
    # sample SD = sqrt(27.428571...) = 5.237229...
    values = [10.0, 12.0, 23.0, 23.0, 16.0, 23.0, 21.0, 16.0]
    sd = calculate_sample_std_dev(values)
    assert sd is not None
    assert math.isclose(sd, 5.237229, rel_tol=1e-5)

    # Sample SD requires N >= 2
    assert calculate_sample_std_dev([10.0]) is None
    assert calculate_sample_std_dev([]) is None


def test_z_score_calculation():
    # z = (current - mean) / sd
    # +2.0 sigma
    z_pos = calculate_z_score(90.0, 70.0, 10.0)
    assert z_pos == 2.0

    # -2.0 sigma
    z_neg = calculate_z_score(50.0, 70.0, 10.0)
    assert z_neg == -2.0

    # Mean equals current
    assert calculate_z_score(70.0, 70.0, 10.0) == 0.0


def test_zero_standard_deviation_handling():
    # All values identical -> variance is 0, SD is 0.
    values = [75.0, 75.0, 75.0, 75.0]
    sd = calculate_sample_std_dev(values)
    assert sd == 0.0

    # z-score must return None rather than raising ZeroDivisionError
    z = calculate_z_score(75.0, 75.0, sd)
    assert z is None


def test_missing_values_strict_handling():
    # Rule: blank != 0, no interpolation, no forward fill, no backward fill
    assert to_float("") is None
    assert to_float("   ") is None
    assert to_float(None) is None
    assert to_float(0) == 0.0
    assert to_float("0") == 0.0

    # Series with gaps
    observations = [
        {"assessment_date": "2026-09-20", "value": 70.0},
        {"assessment_date": "2026-09-21", "value": ""},      # Blank string
        {"assessment_date": "2026-09-22", "value": None},    # Missing
        {"assessment_date": "2026-09-23", "value": 74.0},
        {"assessment_date": "2026-09-24", "value": 75.0},
    ]

    stats = calculate_instrument_stats(observations, window_days=90)
    assert stats["current_value"] == 75.0
    assert stats["previous_value"] == 74.0
    assert stats["change"] == 1.0
    # Only the 3 valid observations are in window
    assert stats["window_count"] == 3
    # Mean of [70.0, 74.0, 75.0] = 73.0
    assert math.isclose(stats["mean_90"], 73.0)


def test_calendar_window_filtering():
    # Window of 5 days ending 2026-09-25: includes 2026-09-21 to 2026-09-25
    observations = [
        {"assessment_date": "2026-09-19", "value": 68.0},  # outside
        {"assessment_date": "2026-09-20", "value": 69.0},  # outside
        {"assessment_date": "2026-09-21", "value": 70.0},  # inside
        {"assessment_date": "2026-09-23", "value": 72.0},  # inside
        {"assessment_date": "2026-09-25", "value": 75.0},  # latest (anchor)
    ]
    window = calendar_window(observations, window_days=5)
    dates = [obs["assessment_date"] for obs in window]
    assert dates == ["2026-09-21", "2026-09-23", "2026-09-25"]


def test_approved_product_conversions():
    # Naphtha: 8.90 barrels / metric ton
    assert PRODUCT_CONVERSIONS["naphtha"] == 8.90
    assert math.isclose(convert_product_price(623.00, 8.90), 623.00 / 8.90)

    # Gasoil: 7.44 barrels / metric ton
    assert PRODUCT_CONVERSIONS["gasoil"] == 7.44
    assert math.isclose(convert_product_price(669.60, 7.44), 669.60 / 7.44)

    # Gasoline: 8.33 barrels / metric ton
    assert PRODUCT_CONVERSIONS["gasoline"] == 8.33
    assert math.isclose(convert_product_price(749.70, 8.33), 749.70 / 8.33)

    # Jet: 7.70 barrels / metric ton
    assert PRODUCT_CONVERSIONS["jet"] == 7.70
    assert math.isclose(convert_product_price(770.00, 7.70), 770.00 / 7.70)

    # Invalid / non-positive factor handling
    assert convert_product_price(700.0, 0) is None
    assert convert_product_price(700.0, -1.0) is None
    assert convert_product_price(None, 8.90) is None


def test_product_brent_spread():
    # Brent price = 75.0 USD/bbl
    # Gasoil price = 632.4 USD/mt -> 632.4 / 7.44 = 85.0 USD/bbl
    # Spread = 85.0 - 75.0 = +10.0 USD/bbl
    brent_price = 75.0
    gasoil_converted = convert_product_price(632.4, 7.44)
    spread = calculate_product_spread(gasoil_converted, brent_price)
    assert spread is not None
    assert math.isclose(spread, 10.0)

    # Missing brent or product price
    assert calculate_product_spread(None, 75.0) is None
    assert calculate_product_spread(85.0, None) is None


def test_calculate_all_product_spreads():
    latest_obs = {
        "brent": {"value": 75.0, "assessment_date": "2026-09-24", "unit": "USD/bbl"},
        "naphtha": {"value": 667.5, "assessment_date": "2026-09-24", "unit": "USD/mt"},
        "gasoil": {"value": 632.4, "assessment_date": "2026-09-24", "unit": "USD/mt"},
        "gasoline": {"value": 749.7, "assessment_date": "2026-09-24", "unit": "USD/mt"},
        "jet": {"value": 731.5, "assessment_date": "2026-09-24", "unit": "USD/mt"},
    }

    spreads = calculate_all_product_spreads(latest_obs)
    assert [s["instrument_id"] for s in spreads] == REFINED_PRODUCT_ORDER

    # Check Naphtha: 667.5 / 8.90 = 75.0, spread vs 75.0 Brent = 0.0
    naphtha_spread = next(s for s in spreads if s["instrument_id"] == "naphtha")
    assert math.isclose(naphtha_spread["converted_price"], 75.0)
    assert math.isclose(naphtha_spread["spread"], 0.0)

    # Check Gasoil: 632.4 / 7.44 = 85.0, spread vs 75.0 Brent = +10.0
    gasoil_spread = next(s for s in spreads if s["instrument_id"] == "gasoil")
    assert math.isclose(gasoil_spread["converted_price"], 85.0)
    assert math.isclose(gasoil_spread["spread"], 10.0)
