from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market import MarketInstrument, MarketObservation
from app.providers.market.oilpriceapi import OilPriceAPIError, OilPriceAPIProvider
from app.services.calculations import calculate_instrument_stats
from app.services.market_ingestion import (
    backfill_history,
    ingest_latest_market_data,
    upsert_observation,
)


@pytest.fixture
def mock_httpx_client():
    """Fixture providing a mock httpx.AsyncClient for provider unit tests."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


# 1. Single-code response normalization
def test_normalize_single_code_response():
    provider = OilPriceAPIProvider(api_key="test-key")
    now = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)
    raw_item = {
        "code": "BRENT_CRUDE_USD",
        "price": 74.52,
        "currency": "USD",
        "unit": "USD/bbl",
        "created_at": "2026-09-24T11:45:00.000Z",
    }
    norm = provider.normalize_price_item(raw_item, now)
    assert norm["provider"] == "oilpriceapi"
    assert norm["provider_symbol"] == "BRENT_CRUDE_USD"
    assert norm["raw_value"] == 74.52
    assert norm["raw_unit"] == "USD/bbl"
    assert norm["assessment_date"] == "2026-09-24"
    assert norm["source_timestamp"] == datetime(2026, 9, 24, 11, 45, 0, tzinfo=timezone.utc)
    assert norm["retrieved_at"] == now


# 2. Multi-code response handling
@pytest.mark.anyio
async def test_get_latest_multi_code(mock_httpx_client):
    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "success",
        "data": [
            {
                "code": "BRENT_CRUDE_USD",
                "price": 74.50,
                "currency": "USD",
                "unit": "USD/bbl",
                "created_at": "2026-09-24T10:00:00Z",
            },
            {
                "code": "WTI_USD",
                "price": 70.20,
                "currency": "USD",
                "unit": "USD/bbl",
                "created_at": "2026-09-24T10:00:00Z",
            },
        ],
    }
    mock_httpx_client.get.return_value = mock_resp

    provider = OilPriceAPIProvider(api_key="test-key", client=mock_httpx_client)
    observations = await provider.get_latest(["BRENT_CRUDE_USD", "WTI_USD"])

    assert len(observations) == 2
    symbols = {o["provider_symbol"] for o in observations}
    assert symbols == {"BRENT_CRUDE_USD", "WTI_USD"}
    brent = next(o for o in observations if o["provider_symbol"] == "BRENT_CRUDE_USD")
    assert brent["raw_value"] == 74.50


# 3. Alternative data.prices dictionary structure
@pytest.mark.anyio
async def test_get_latest_prices_dict_structure(mock_httpx_client):
    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "success",
        "data": {
            "prices": [
                {
                    "code": "BRENT_CRUDE_USD",
                    "price": 75.10,
                    "currency": "USD",
                    "unit": "USD/bbl",
                    "created_at": "2026-09-24T11:00:00Z",
                }
            ]
        },
    }
    mock_httpx_client.get.return_value = mock_resp

    provider = OilPriceAPIProvider(api_key="test-key", client=mock_httpx_client)
    observations = await provider.get_latest(["BRENT_CRUDE_USD"])
    assert len(observations) == 1
    assert observations[0]["raw_value"] == 75.10


# 4. Error handling: HTTP 401 Unauthorized
@pytest.mark.anyio
async def test_http_401_error(mock_httpx_client):
    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.json.return_value = {"error": "Invalid API key"}
    mock_httpx_client.get.return_value = mock_resp

    provider = OilPriceAPIProvider(api_key="invalid-key", client=mock_httpx_client)
    with pytest.raises(OilPriceAPIError) as exc_info:
        await provider.get_latest(["BRENT_CRUDE_USD"])
    assert exc_info.value.status_code == 401


# 5. Error handling: Malformed JSON
@pytest.mark.anyio
async def test_invalid_json_handling(mock_httpx_client):
    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON")
    mock_httpx_client.get.return_value = mock_resp

    provider = OilPriceAPIProvider(api_key="test-key", client=mock_httpx_client)
    with pytest.raises(OilPriceAPIError) as exc_info:
        await provider.get_latest(["BRENT_CRUDE_USD"])
    assert "Failed to parse JSON" in str(exc_info.value)


# 6. Missing price or timestamp in provider payload
def test_missing_price_and_timestamp():
    provider = OilPriceAPIProvider(api_key="test-key")
    now = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)

    # Missing price
    item_no_price = {"code": "BRENT_CRUDE_USD", "price": None, "created_at": "2026-09-24T10:00:00Z"}
    norm_no_price = provider.normalize_price_item(item_no_price, now)
    assert norm_no_price["raw_value"] is None

    # Missing timestamp defaults to retrieved_at
    item_no_ts = {"code": "BRENT_CRUDE_USD", "price": 75.0}
    norm_no_ts = provider.normalize_price_item(item_no_ts, now)
    assert norm_no_ts["assessment_date"] == "2026-09-24"
    assert norm_no_ts["source_timestamp"] == now


# 7. Idempotent upsert (same-day refresh semantics)
def test_same_day_upsert(db_session: Session):
    inst = MarketInstrument(
        instrument_key="brent",
        display_name="Dated Brent",
        unit="USD/bbl",
        provider="oilpriceapi",
        provider_symbol="BRENT_CRUDE_USD",
        enabled=True,
    )
    db_session.add(inst)
    db_session.flush()

    raw_obs_morning = {
        "provider": "oilpriceapi",
        "provider_symbol": "BRENT_CRUDE_USD",
        "raw_value": 74.00,
        "raw_unit": "USD/bbl",
        "assessment_date": "2026-09-24",
        "source_timestamp": datetime(2026, 9, 24, 9, 0, 0, tzinfo=timezone.utc),
        "retrieved_at": datetime(2026, 9, 24, 9, 5, 0, tzinfo=timezone.utc),
    }

    obs1, action1 = upsert_observation(db_session, inst, raw_obs_morning)
    db_session.commit()
    assert action1 == "stored"
    assert obs1.value == Decimal("74.00")

    # Afternoon refresh on same assessment_date
    raw_obs_afternoon = {
        "provider": "oilpriceapi",
        "provider_symbol": "BRENT_CRUDE_USD",
        "raw_value": 75.50,
        "raw_unit": "USD/bbl",
        "assessment_date": "2026-09-24",
        "source_timestamp": datetime(2026, 9, 24, 16, 0, 0, tzinfo=timezone.utc),
        "retrieved_at": datetime(2026, 9, 24, 16, 5, 0, tzinfo=timezone.utc),
    }

    obs2, action2 = upsert_observation(db_session, inst, raw_obs_afternoon)
    db_session.commit()
    assert action2 == "updated"
    assert obs2.id == obs1.id
    assert obs2.value == Decimal("75.50")

    # Ensure no duplicate observation exists
    count = db_session.scalars(
        select(MarketObservation).where(
            MarketObservation.instrument_id == inst.id,
            MarketObservation.assessment_date == date(2026, 9, 24),
        )
    ).all()
    assert len(count) == 1


# 8. Preservation of raw provider unit (no premature mt -> bbl conversion)
def test_preserve_raw_provider_units(db_session: Session):
    inst = MarketInstrument(
        instrument_key="naphtha",
        display_name="Naphtha Cargoes CIF NWE",
        unit="USD/mt",
        provider="oilpriceapi",
        provider_symbol="NAPHTHA_USD",
        enabled=True,
    )
    db_session.add(inst)
    db_session.flush()

    raw_naphtha = {
        "provider": "oilpriceapi",
        "provider_symbol": "NAPHTHA_USD",
        "raw_value": 625.50,
        "raw_unit": "USD/mt",
        "assessment_date": "2026-09-24",
    }
    obs, action = upsert_observation(db_session, inst, raw_naphtha)
    db_session.commit()
    assert action == "stored"
    # Preserves raw USD/mt price exactly
    assert obs.value == Decimal("625.50")
    assert obs.unit == "USD/mt"


# 9. Ingest latest market data service with mock provider
@pytest.mark.anyio
async def test_ingest_latest_market_data(db_session: Session):
    # Add mapped instruments
    brent_inst = MarketInstrument(
        instrument_key="brent",
        display_name="Dated Brent",
        unit="USD/bbl",
        provider="oilpriceapi",
        provider_symbol="BRENT_CRUDE_USD",
        enabled=True,
    )
    wti_inst = MarketInstrument(
        instrument_key="wti",
        display_name="WTI",
        unit="USD/bbl",
        provider="oilpriceapi",
        provider_symbol="WTI_USD",
        enabled=True,
    )
    db_session.add_all([brent_inst, wti_inst])
    db_session.commit()

    mock_provider = AsyncMock(spec=OilPriceAPIProvider)
    mock_provider.get_latest.return_value = [
        {
            "provider": "oilpriceapi",
            "provider_symbol": "BRENT_CRUDE_USD",
            "raw_value": 74.80,
            "raw_unit": "USD/bbl",
            "assessment_date": "2026-09-24",
            "source_timestamp": datetime.now(timezone.utc),
            "retrieved_at": datetime.now(timezone.utc),
        },
        {
            "provider": "oilpriceapi",
            "provider_symbol": "WTI_USD",
            "raw_value": 70.30,
            "raw_unit": "USD/bbl",
            "assessment_date": "2026-09-24",
            "source_timestamp": datetime.now(timezone.utc),
            "retrieved_at": datetime.now(timezone.utc),
        },
    ]

    summary = await ingest_latest_market_data(db_session, provider=mock_provider)
    assert summary["provider"] == "oilpriceapi"
    assert summary["requested"] == 2
    assert summary["stored"] == 2
    assert summary["failed"] == 0
    assert "brent" in summary["instruments"]
    assert "wti" in summary["instruments"]


# 10. Insufficient 90D history returns z_score = None and status = insufficient_history
def test_insufficient_90d_history_z_score():
    # Only 30 days of data provided
    base_date = date(2026, 9, 24)
    observations = [
        {"assessment_date": (base_date - timedelta(days=i)).isoformat(), "value": 70.0 + (i % 3)}
        for i in range(30)
    ]

    # With min_history_points=60 required for a 90-day z-score
    stats = calculate_instrument_stats(observations, window_days=90, min_history_points=60)
    assert stats["current_value"] is not None
    assert stats["window_count"] == 30
    assert stats["history_status"] == "insufficient_history"
    assert stats["z_score"] is None

    # With sufficient history (e.g. 75 points >= 60)
    obs_75 = [
        {"assessment_date": (base_date - timedelta(days=i)).isoformat(), "value": 70.0 + (i % 3)}
        for i in range(75)
    ]
    stats_75 = calculate_instrument_stats(obs_75, window_days=90, min_history_points=60)
    assert stats_75["window_count"] == 75
    assert stats_75["history_status"] == "valid"
    assert stats_75["z_score"] is not None
