from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.market import MarketInstrument


def test_health_endpoint(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "Daily Oil Trading Risk Dashboard API"
    assert data["database"] in ("connected", "not_configured")


def test_market_instruments_endpoint(client: TestClient, seed_test_data: dict[str, MarketInstrument]):
    response = client.get("/api/market/instruments")
    assert response.status_code == 200
    instruments = response.json()
    assert len(instruments) == 7
    keys = {inst["instrument_key"] for inst in instruments}
    assert keys == {"brent", "wti", "forcados", "naphtha", "gasoil", "gasoline", "jet"}


def test_market_latest_endpoint(client: TestClient, seed_test_data: dict[str, MarketInstrument]):
    response = client.get("/api/market/latest")
    assert response.status_code == 200
    data = response.json()
    assert "observations" in data
    assert len(data["observations"]) == 7

    brent_obs = next(o for o in data["observations"] if o["instrumentId"] == "brent")
    assert brent_obs["unit"] == "USD/bbl"
    assert brent_obs["assessmentDate"] == "2026-09-24"
    assert brent_obs["provider"] == "test_fixture"


def test_market_history_endpoint(client: TestClient, seed_test_data: dict[str, MarketInstrument]):
    response = client.get("/api/market/history?instrument=brent&days=90")
    assert response.status_code == 200
    data = response.json()
    assert data["instrument"] == "brent"
    assert data["days"] == 90
    assert len(data["observations"]) > 0
    assert len(data["history_points"]) > 0

    # Ensure chronological order
    dates = [pt["date"] for pt in data["history_points"]]
    assert dates == sorted(dates)


def test_market_history_not_found(client: TestClient, seed_test_data: dict[str, MarketInstrument]):
    response = client.get("/api/market/history?instrument=unknown_asset&days=90")
    assert response.status_code == 404


def test_dashboard_snapshot_endpoint(client: TestClient, seed_test_data: dict[str, MarketInstrument]):
    response = client.get("/api/dashboard/snapshot")
    assert response.status_code == 200
    data = response.json()

    assert "snapshot_date" in data
    assert "market_stats" in data
    assert len(data["market_stats"]) == 7

    # Check stats calculated
    brent_stat = next(s for s in data["market_stats"] if s["instrument_id"] == "brent")
    assert brent_stat["current_value"] is not None
    assert brent_stat["mean_90"] is not None
    assert brent_stat["std_dev_90"] is not None

    # Check product spreads
    assert "product_spreads" in data
    assert len(data["product_spreads"]) == 4

    # Check macro indicators
    assert "macro_indicators" in data
    assert len(data["macro_indicators"]) >= 1

    # Check risk register
    assert "risk_register" in data
    assert len(data["risk_register"]) >= 1
    # Verify simplified fields: no risk_event, no mitigant
    first_risk = data["risk_register"][0]
    assert "risk_category" in first_risk
    assert "materiality" in first_risk
    assert "trend" in first_risk
    assert "risk_owner" in first_risk
    assert "risk_event" not in first_risk
    assert "mitigant" not in first_risk


def test_ai_analyse_unconfigured(client: TestClient):
    response = client.post("/api/ai/analyse", json={"context": {"market": []}})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unconfigured"
    assert data["configured"] is False
    assert "scaffold" in data["message"].lower()


def test_ai_chat_unconfigured(client: TestClient):
    response = client.post("/api/ai/chat", json={"message": "What is the Brent risk?", "context": {}})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unconfigured"
    assert data["configured"] is False
    assert data["reply"] is None


def test_risk_register_get_and_put_persistence(client: TestClient):
    # 1. GET risk register
    res = client.get("/api/dashboard/risk-register")
    assert res.status_code == 200
    rows = res.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1

    # 2. PUT updated risk register
    new_rows = [
        {
            "risk_category": "Updated FX Risk",
            "materiality": "Major",
            "trend": "increasing",
            "risk_owner": "Treasurer",
            "display_order": 1,
            "active": True,
        },
        {
            "risk_category": "Updated Credit Risk",
            "materiality": "Moderate",
            "trend": "decreasing",
            "risk_owner": "Risk Lead",
            "display_order": 2,
            "active": True,
        },
    ]
    put_res = client.put("/api/dashboard/risk-register", json=new_rows)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert len(updated) == 2
    assert updated[0]["risk_category"] == "Updated FX Risk"
    assert updated[0]["materiality"] == "Major"
    assert updated[0]["trend"] == "increasing"
    assert updated[0]["risk_owner"] == "Treasurer"

    # 3. GET /api/risk-register alias returns same updated rows
    alias_res = client.get("/api/risk-register")
    assert alias_res.status_code == 200
    alias_data = alias_res.json()
    assert len(alias_data) == 2
    assert alias_data[0]["risk_category"] == "Updated FX Risk"

    # 4. Verify snapshot also reflects updated risk register
    snap_res = client.get("/api/dashboard/snapshot")
    assert snap_res.status_code == 200
    snap_data = snap_res.json()
    assert len(snap_data["risk_register"]) == 2
    assert snap_data["risk_register"][0]["risk_category"] == "Updated FX Risk"

