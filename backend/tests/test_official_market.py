"""Synthetic data only: official Platts lineage must never fall back to API proxies."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import math
import pytest
from sqlalchemy import select, delete
from app.models.historical import HistoricalMarketObservation as H
from app.models.market import MarketObservation, MarketInstrument
from app.services.historical_market import HISTORICAL_MAPPING
from app.services.calculations import calculate_instrument_stats, PRODUCT_CONVERSIONS
from app.services.ai_context import build_dashboard_ai_context


@pytest.mark.parametrize("key", list(HISTORICAL_MAPPING))
def test_official_latest_history_statistics_and_identity_agree(client, seed_platts_data, db_session, key):
    symbol, label, unit, factor, *_ = HISTORICAL_MAPPING[key]
    # A newer differently defined API assessment is deliberately extreme.
    db_session.add(MarketObservation(instrument_id=seed_platts_data[key].id,
        provider="oilpriceapi", provider_symbol="BRENT_CRUDE_USD" if key == "brent" else "PROXY",
        assessment_date=date(2026, 10, 15), value=99999, unit="gallon",
        retrieved_at=datetime.now(timezone.utc)))
    db_session.flush()
    latest = next(s for s in client.get("/api/market/latest").json()["observations"] if s["instrumentId"] == key)
    stat = next(s for s in client.get("/api/dashboard/snapshot").json()["market_stats"] if s["instrument_id"] == key)
    history = client.get(f"/api/market/history?instrument={key}&days=90").json()["observations"]
    historical = next(s for s in client.get("/api/market/historical").json()["instruments"] if s["instrument"] == key)
    assert latest["providerSymbol"] == stat["provider_symbol"] == historical["symbol"] == symbol
    assert latest["provider"] == stat["provider"] == "platts_excel"
    assert latest["unit"] == stat["unit"] == historical["unit"] == unit
    assert latest["value"] == stat["current_value"] == historical["latest"]
    assert latest["assessmentDate"] == stat["latest_date"] == historical["latest_date"] == "2026-09-24"
    assert stat["change"] == pytest.approx(history[-1]["value"] - history[-2]["value"])
    assert all(s["provider"] == "platts_excel" and s["providerSymbol"] == symbol for s in history)
    reference = calculate_instrument_stats([{"assessment_date": h["assessmentDate"], "value": h["value"]} for h in history], min_history_points=60)
    assert stat["z_score"] == historical["z_score"] == pytest.approx(reference["z_score"])
    assert stat["window_count"] == historical["count_90d"] == 90
    assert len(stat["history"]) == 90
    assert stat["history"][-1]["value"] == stat["current_value"]
    assert all(r["providerSymbol"] == symbol and r["provider"] == "platts_excel" for r in stat["history"])
    assert stat["freshness_status"] == historical["freshness"] == "stale"
    if factor:
        assert latest["barrelsPerMT"] == factor
        assert latest["convertedValue"] == pytest.approx(latest["value"] / factor)
    context = next(s for s in build_dashboard_ai_context(db_session)["market_stats"] if s["instrument_id"] == key)
    assert context["source_symbol"] == symbol
    assert all(r["provider_symbol"] == symbol and r["provider"] == "platts_excel" for r in context["history_30d"])


def test_api_only_data_cannot_supply_official_kpis_or_spreads(client, seed_test_data):
    assert client.get("/api/market/latest").json()["observations"] == []
    snapshot = client.get("/api/dashboard/snapshot").json()
    assert len(snapshot["market_stats"]) == 7
    assert all(s["current_value"] is None and s["z_score"] is None for s in snapshot["market_stats"])
    assert all(s["spread"] is None for s in snapshot["product_spreads"])
    assert snapshot["outliers"] == []


def test_spreads_use_workbook_factors_and_same_date_platts_brent(client, seed_platts_data, db_session):
    snapshot = client.get("/api/dashboard/snapshot").json()
    stats = {s["instrument_id"]: s for s in snapshot["market_stats"]}
    for spread in snapshot["product_spreads"]:
        key = spread["instrument_id"]; factor = HISTORICAL_MAPPING[key][3]
        assert spread["barrels_per_mt"] == factor
        assert spread["spread"] == pytest.approx(stats[key]["current_value"]/factor - stats["brent"]["current_value"])
    assert PRODUCT_CONVERSIONS["gasoil"] == 7.44  # preserved API default, not workbook 7.3137
    db_session.execute(delete(H).where(H.instrument_key == "brent", H.assessment_date == date(2026, 9, 24)))
    mismatch = client.get("/api/dashboard/snapshot").json()["product_spreads"]
    assert all(s["spread"] is None and not s["is_comparable"] for s in mismatch)


@pytest.mark.parametrize("count,eligible", [(59, False), (60, True)])
def test_official_statistics_preserve_sixty_observation_rule(client, seed_platts_data, db_session, count, eligible):
    cutoff = date(2026, 9, 24) - timedelta(days=count-1)
    db_session.execute(delete(H).where(H.instrument_key == "brent", H.assessment_date < cutoff))
    latest = db_session.scalar(select(H).where(H.instrument_key == "brent", H.assessment_date == date(2026, 9, 24)))
    latest.native_value = 10000
    db_session.flush()
    snapshot = client.get("/api/dashboard/snapshot").json()
    stat = next(s for s in snapshot["market_stats"] if s["instrument_id"] == "brent")
    assert stat["window_count"] == count
    assert (stat["z_score"] is not None) == eligible
    assert ("brent" in {s["instrument_id"] for s in snapshot["outliers"]}) == eligible


def test_official_reload_does_not_collect_api_data(client, seed_platts_data, monkeypatch):
    def forbidden():
        raise AssertionError("Official refresh must not collect OilPriceAPI values")
    monkeypatch.setattr("app.services.market_ingestion.get_market_provider", forbidden)
    response = client.post("/api/market/refresh")
    assert response.status_code == 200
    assert response.json()["provider"] == "platts_excel"
    assert response.json()["stored"] == 0
    assert "workbook" in response.json()["message"]


def test_wrong_platts_identifier_or_unit_is_not_accepted(client, seed_platts_data, db_session):
    db_session.execute(delete(H).where(H.instrument_key == "brent"))
    db_session.add(H(instrument_key="brent",provider="platts_excel",provider_symbol="BRENT_CRUDE_USD",
        native_unit="USD/BBL",native_value=999,converted_value=999,benchmark_definition="SYNTHETIC mismatch",
        assessment_date=date(2026,10,14),workbook_source="SYNTHETIC.xlsx",workbook_sha256="0"*64,
        worksheet="Market Risk",imported_at=datetime.now(timezone.utc)))
    db_session.flush()
    stat = next(s for s in client.get("/api/dashboard/snapshot").json()["market_stats"] if s["instrument_id"] == "brent")
    assert stat["current_value"] is None
    assert stat["provider_symbol"] == "PCAAS00"
