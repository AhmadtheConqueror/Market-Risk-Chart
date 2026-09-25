from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Set test environment
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.market import MarketInstrument, MarketObservation
from app.models.macro import MacroIndicator
from app.models.risk import DashboardContent, RiskRegisterEntry


TEST_DB_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seed_test_data(db_session: Session) -> dict[str, MarketInstrument]:
    instruments_data = [
        {"instrument_key": "brent", "display_name": "Dated Brent", "unit": "USD/bbl", "category": "crude"},
        {"instrument_key": "wti", "display_name": "WTI", "unit": "USD/bbl", "category": "crude"},
        {"instrument_key": "forcados", "display_name": "Forcados", "unit": "USD/bbl", "category": "crude"},
        {"instrument_key": "naphtha", "display_name": "Naphtha Cargoes CIF NWE", "unit": "USD/mt", "category": "refined"},
        {"instrument_key": "gasoil", "display_name": "Gasoil 0.1% Cargoes CIF NWE", "unit": "USD/mt", "category": "refined"},
        {"instrument_key": "gasoline", "display_name": "Eurobob Non-Oxy Barges FOB Rdam", "unit": "USD/mt", "category": "refined"},
        {"instrument_key": "jet", "display_name": "Jet Aviation Fuel Cargoes CIF NWE", "unit": "USD/mt", "category": "refined"},
    ]

    inst_map: dict[str, MarketInstrument] = {}
    for data in instruments_data:
        inst = MarketInstrument(
            instrument_key=data["instrument_key"],
            display_name=data["display_name"],
            unit=data["unit"],
            category=data["category"],
            provider="test_fixture",
            provider_symbol=f"TEST_{data['instrument_key'].upper()}",
            enabled=True,
        )
        db_session.add(inst)
        db_session.flush()
        inst_map[data["instrument_key"]] = inst

    # Seed 90 days of deterministic test observations
    now = datetime.now(timezone.utc)
    base_date = date(2026, 9, 24)
    base_prices = {
        "brent": 75.0,
        "wti": 70.0,
        "forcados": 76.0,
        "naphtha": 667.5,   # 667.5 / 8.90 = 75.0 (spread = 0)
        "gasoil": 632.4,    # 632.4 / 7.44 = 85.0 (spread = +10)
        "gasoline": 749.7,  # 749.7 / 8.33 = 90.0 (spread = +15)
        "jet": 731.5,       # 731.5 / 7.70 = 95.0 (spread = +20)
    }

    for inst_key, inst in inst_map.items():
        base_val = base_prices[inst_key]
        for i in range(90, -1, -1):
            obs_dt = base_date - timedelta(days=i)
            # deterministic slight variation for non-zero SD
            val = base_val + (i % 5 - 2) * 0.5
            obs = MarketObservation(
                instrument_id=inst.id,
                assessment_date=obs_dt,
                value=val,
                unit=inst.unit,
                provider="test_fixture",
                provider_symbol=f"TEST_{inst_key.upper()}",
                retrieved_at=now,
                source_timestamp=now,
            )
            db_session.add(obs)

    # Simplified risk register
    db_session.add(
        RiskRegisterEntry(
            risk_category="Crude Price Volatility",
            materiality="Major",
            trend="increasing",
            risk_owner="Head of Oil Trading",
            display_order=1,
            active=True,
        )
    )

    # Macro indicator
    db_session.add(
        MacroIndicator(
            indicator_key="DXY",
            display_name="US Dollar Index",
            value=102.5,
            unit="Index",
            reporting_period="Daily",
            source="Test Provider",
            retrieved_at=now,
        )
    )

    # Dashboard content
    db_session.add(
        DashboardContent(
            section_key="briefing",
            item_key="daily_summary",
            title="Daily Briefing",
            content="Crude markets steady ahead of economic data.",
            classification="info",
            display_order=1,
            active=True,
        )
    )

    db_session.commit()
    return inst_map
