from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calendar import CalendarEvent
from app.providers.calendar.base import CalendarProvider
from app.providers.calendar.fed import FedCalendarProvider
from app.providers.calendar.bls import BlsCalendarProvider
from app.providers.calendar.bea import BeaCalendarProvider
from app.providers.calendar.eia import EiaCalendarProvider
from app.providers.calendar.cbn import CbnCalendarProvider
from app.providers.calendar.nbs import NbsCalendarProvider
from app.providers.calendar.opec import OpecCalendarProvider
from app.providers.calendar.holidays import HolidaysCalendarProvider
from app.services.ai_context import build_dashboard_ai_context
from app.services.calendar_ingestion import (
    create_manual_event,
    delete_manual_event,
    get_calendar_events_query,
    migrate_legacy_events,
    refresh_calendar_events,
    update_manual_event,
    upsert_calendar_event,
)


def test_official_providers_generate_events():
    """Verify that all isolated official calendar providers return structured events with valid metadata."""
    async def _run():
        fed = FedCalendarProvider()
        fed_events = await fed.get_events()
        assert len(fed_events) >= 8
        fomc = fed_events[0]
        assert "FOMC" in fomc["title"]
        assert fomc["category"] == "central_bank"
        assert fomc["region"] == "USA"
        assert fomc["impact_level"] == "high"

        bls = BlsCalendarProvider()
        bls_events = await bls.get_events()
        assert len(bls_events) >= 10
        assert any("CPI" in e["title"] for e in bls_events)
        assert any("Employment" in e["title"] for e in bls_events)

        bea = BeaCalendarProvider()
        bea_events = await bea.get_events()
        assert len(bea_events) >= 8
        assert all("GDP" in e["title"] for e in bea_events)

        eia = EiaCalendarProvider()
        eia_events = await eia.get_events()
        assert len(eia_events) >= 10
        assert any("WPSR" in e["title"] or "Petroleum Status" in e["title"] for e in eia_events)
        assert any("STEO" in e["title"] for e in eia_events)

        cbn = CbnCalendarProvider()
        cbn_events = await cbn.get_events()
        assert len(cbn_events) >= 5
        assert all(e["region"] == "Nigeria" for e in cbn_events)

        nbs = NbsCalendarProvider()
        nbs_events = await nbs.get_events()
        assert len(nbs_events) >= 10
        assert any("CPI" in e["title"] for e in nbs_events)

        opec = OpecCalendarProvider()
        opec_events = await opec.get_events()
        assert len(opec_events) >= 10
        assert any("MOMR" in e["title"] for e in opec_events)
        assert any("Ministerial" in e["title"] or "JMMC" in e["title"] for e in opec_events)

        holidays = HolidaysCalendarProvider()
        holidays_events = await holidays.get_events()
        assert len(holidays_events) >= 10
        assert any(e["region"] == "USA" for e in holidays_events)
        assert any(e["region"] == "Nigeria" for e in holidays_events)

    asyncio.run(_run())


def test_upsert_deduplication_and_date_change(db_session: Session):
    """Verify that upsert deduplicates stable keys and updates date in place without duplication."""
    raw_event = {
        "external_id": "fomc-2026-10-28",
        "provider": "fed",
        "event_date": "2026-10-28",
        "title": "FOMC Meeting Decision",
        "category": "central_bank",
        "region": "USA",
        "impact_level": "high",
        "source_name": "Federal Reserve Board",
    }

    # 1. First upsert -> created
    ev1, action1 = upsert_calendar_event(db_session, raw_event)
    db_session.commit()
    assert action1 == "created"
    assert ev1.id is not None
    event_id = ev1.id

    # 2. Second upsert identical -> unchanged
    ev2, action2 = upsert_calendar_event(db_session, raw_event)
    db_session.commit()
    assert action2 == "unchanged"
    assert ev2.id == event_id

    # 3. Third upsert with changed date -> updated in place
    updated_raw = dict(raw_event)
    updated_raw["event_date"] = "2026-10-29"
    ev3, action3 = upsert_calendar_event(db_session, updated_raw)
    db_session.commit()
    assert action3 == "updated"
    assert ev3.id == event_id
    assert ev3.event_date == date(2026, 10, 29)

    # Confirm only 1 event exists in database
    total = db_session.scalars(select(CalendarEvent)).all()
    assert len(total) == 1


def test_provider_failure_isolation(db_session: Session):
    """Verify that if one provider fails, others proceed normally and the failure is isolated."""
    class WorkingProvider(CalendarProvider):
        name = "working"
        source_name = "Working Provider"
        source_url = "https://example.com"

        async def get_events(self) -> list[dict[str, Any]]:
            return [
                {
                    "external_id": "work-1",
                    "title": "Working Event",
                    "event_date": "2026-10-15",
                    "category": "energy",
                    "region": "Global",
                }
            ]

    class FailingProvider(CalendarProvider):
        name = "failing"
        source_name = "Failing Provider"
        source_url = "https://example.com"

        async def get_events(self) -> list[dict[str, Any]]:
            raise RuntimeError("Upstream API network error")

    async def _run():
        summary = await refresh_calendar_events(db_session, providers=[WorkingProvider(), FailingProvider()])
        assert summary["sources_requested"] == 2
        assert summary["sources_succeeded"] == 1
        assert summary["sources_failed"] == 1
        assert summary["events_created"] == 1

        # Check results per provider
        res_working = next(p for p in summary["provider_results"] if p["name"] == "working")
        assert res_working["status"] == "success"
        assert res_working["created"] == 1

        res_failing = next(p for p in summary["provider_results"] if p["name"] == "failing")
        assert res_failing["status"] == "failed"
        assert "network error" in res_failing["error"]

    asyncio.run(_run())


def test_manual_crud_and_official_event_protection(client: TestClient, db_session: Session):
    """Verify manual event creation, updating, and deletion, and that official events cannot be altered."""
    # 1. Create official event directly
    official = CalendarEvent(
        external_id="fed-official-1",
        provider="fed",
        event_date=date(2026, 10, 28),
        title="Official FOMC Decision",
        category="central_bank",
        region="USA",
        source_type="official",
        active=True,
    )
    db_session.add(official)
    db_session.commit()
    db_session.refresh(official)

    # 2. Attempt to update official event via PUT -> 403 Forbidden
    res = client.put(f"/api/calendar/events/{official.id}", json={"title": "Hacked FOMC"})
    assert res.status_code == 403
    assert "Official calendar events cannot be edited" in res.json()["detail"]

    # 3. Attempt to delete official event via DELETE -> 403 Forbidden
    del_res = client.delete(f"/api/calendar/events/{official.id}")
    assert del_res.status_code == 403
    assert "Official calendar events cannot be deleted" in del_res.json()["detail"]

    # 4. Create manual event via POST -> 201 Created
    create_res = client.post(
        "/api/calendar/events",
        json={
            "title": "Internal Risk Committee Meeting",
            "event_date": "2026-10-20",
            "category": "macro",
            "region": "Nigeria",
            "impact_level": "moderate",
            "description": "Quarterly portfolio review",
        },
    )
    assert create_res.status_code == 201
    manual_data = create_res.json()
    manual_id = manual_data["id"]
    assert manual_data["source_type"] == "manual"
    assert manual_data["title"] == "Internal Risk Committee Meeting"

    # 5. Update manual event via PUT -> 200 OK
    put_res = client.put(
        f"/api/calendar/events/{manual_id}",
        json={"title": "Updated Risk Committee Meeting", "impact_level": "high"},
    )
    assert put_res.status_code == 200
    assert put_res.json()["title"] == "Updated Risk Committee Meeting"
    assert put_res.json()["impact_level"] == "high"

    # 6. Delete manual event via DELETE -> 200 OK
    delete_res = client.delete(f"/api/calendar/events/{manual_id}")
    assert delete_res.status_code == 200
    assert delete_res.json()["status"] == "deleted"

    # Confirm it was removed
    get_res = client.get(f"/api/calendar/events?month=2026-10")
    assert get_res.status_code == 200
    events = get_res.json()
    assert not any(e["id"] == manual_id for e in events)


def test_calendar_filtering(client: TestClient, db_session: Session):
    """Verify month, category, and region filtering on GET /api/calendar/events."""
    ev1 = CalendarEvent(
        title="OPEC JMMC",
        event_date=date(2026, 10, 4),
        category="energy",
        region="Global",
        provider="opec",
        source_type="official",
    )
    ev2 = CalendarEvent(
        title="CBN MPC",
        event_date=date(2026, 10, 19),
        category="central_bank",
        region="Nigeria",
        provider="cbn",
        source_type="official",
    )
    ev3 = CalendarEvent(
        title="US Thanksgiving",
        event_date=date(2026, 11, 26),
        category="bank_holiday",
        region="USA",
        provider="holidays",
        source_type="official",
    )
    db_session.add_all([ev1, ev2, ev3])
    db_session.commit()

    # Filter by month 2026-10
    r1 = client.get("/api/calendar/events?month=2026-10")
    assert r1.status_code == 200
    titles1 = [e["title"] for e in r1.json()]
    assert "OPEC JMMC" in titles1
    assert "CBN MPC" in titles1
    assert "US Thanksgiving" not in titles1

    # Filter by category central_bank
    r2 = client.get("/api/calendar/events?category=central_bank")
    assert r2.status_code == 200
    titles2 = [e["title"] for e in r2.json()]
    assert "CBN MPC" in titles2
    assert "OPEC JMMC" not in titles2

    # Filter by region Nigeria
    r3 = client.get("/api/calendar/events?region=Nigeria")
    assert r3.status_code == 200
    titles3 = [e["title"] for e in r3.json()]
    assert titles3 == ["CBN MPC"]


def test_legacy_migration_endpoint(client: TestClient, db_session: Session):
    """Verify POST /api/calendar/migrate-legacy imports browser localStorage events."""
    legacy_items = [
        {
            "id": "user-custom-1",
            "title": "Legacy Crude Contract Expiry",
            "event_date": "2026-10-31",
            "category": "energy",
            "region": "Global",
            "impact_level": "high",
        },
        {
            "id": "demo-mock-event",
            "title": "Should be skipped demo fixture",
            "event_date": "2026-10-15",
        },
        {
            "title": "",  # Empty title -> skipped
            "event_date": "2026-10-12",
        },
    ]

    res = client.post("/api/calendar/migrate-legacy", json={"events": legacy_items})
    assert res.status_code == 200
    data = res.json()
    assert data["migrated"] == 1
    assert data["skipped"] == 2
    assert data["total_submitted"] == 3

    # Verify event exists in DB as manual
    migrated = db_session.scalars(
        select(CalendarEvent).where(CalendarEvent.title == "Legacy Crude Contract Expiry")
    ).first()
    assert migrated is not None
    assert migrated.source_type == "manual"
    assert migrated.provider == "manual"


def test_ai_context_includes_upcoming_calendar(db_session: Session, seed_test_data: Any):
    """Verify that build_dashboard_ai_context enriches the AI payload with upcoming calendar events."""
    today_dt = date.today()
    ev = CalendarEvent(
        title="Upcoming Fed Meeting",
        event_date=today_dt + timedelta(days=3),
        category="central_bank",
        region="USA",
        impact_level="high",
        provider="fed",
        source_type="official",
        source_name="Federal Reserve Board",
    )
    db_session.add(ev)
    db_session.commit()

    context = build_dashboard_ai_context(db_session)
    assert "upcoming_calendar_events" in context
    upcoming = context["upcoming_calendar_events"]
    assert any(e["title"] == "Upcoming Fed Meeting" for e in upcoming)


def test_refresh_calendar_script_success(monkeypatch: pytest.MonkeyPatch, db_session: Session):
    """Verify that scripts.refresh_calendar.run_refresh calls the service layer and exits 0."""
    from scripts import refresh_calendar

    mock_summary = {
        "sources_requested": 8,
        "sources_succeeded": 8,
        "sources_failed": 0,
        "events_created": 2,
        "events_updated": 1,
        "events_unchanged": 171,
        "provider_results": [],
    }

    class DummySessionFactory:
        def __call__(self):
            class DummyContext:
                def __enter__(self):
                    return db_session
                def __exit__(self, *args):
                    pass
            return DummyContext()

    monkeypatch.setattr(refresh_calendar, "get_session_factory", lambda: DummySessionFactory())
    mock_refresh = AsyncMock(return_value=mock_summary)
    monkeypatch.setattr(refresh_calendar, "refresh_calendar_events", mock_refresh)

    exit_code = refresh_calendar.run_refresh()
    assert exit_code == 0
    mock_refresh.assert_awaited_once_with(db_session)


def test_refresh_calendar_script_partial_provider_failure(monkeypatch: pytest.MonkeyPatch, db_session: Session):
    """Verify that partial provider failures still complete acceptably with exit code 0."""
    from scripts import refresh_calendar

    mock_summary = {
        "sources_requested": 8,
        "sources_succeeded": 7,
        "sources_failed": 1,
        "events_created": 0,
        "events_updated": 0,
        "events_unchanged": 160,
        "provider_results": [
            {
                "name": "opec",
                "source": "OPEC Secretariat",
                "status": "failed",
                "events_found": 0,
                "created": 0,
                "updated": 0,
                "error": "HTTP 403 Forbidden",
            }
        ],
    }

    class DummySessionFactory:
        def __call__(self):
            class DummyContext:
                def __enter__(self):
                    return db_session
                def __exit__(self, *args):
                    pass
            return DummyContext()

    monkeypatch.setattr(refresh_calendar, "get_session_factory", lambda: DummySessionFactory())
    monkeypatch.setattr(refresh_calendar, "refresh_calendar_events", AsyncMock(return_value=mock_summary))

    exit_code = refresh_calendar.run_refresh()
    assert exit_code == 0


def test_refresh_calendar_script_fatal_db_failure(monkeypatch: pytest.MonkeyPatch):
    """Verify that fatal DB connection initialization failure returns exit code 1."""
    from scripts import refresh_calendar

    def broken_factory():
        raise ConnectionRefusedError("Database connection refused")

    monkeypatch.setattr(refresh_calendar, "get_session_factory", broken_factory)

    exit_code = refresh_calendar.run_refresh()
    assert exit_code == 1


def test_refresh_calendar_script_fatal_service_failure(monkeypatch: pytest.MonkeyPatch, db_session: Session):
    """Verify that an unhandled crash in the service layer returns exit code 1."""
    from scripts import refresh_calendar

    class DummySessionFactory:
        def __call__(self):
            class DummyContext:
                def __enter__(self):
                    return db_session
                def __exit__(self, *args):
                    pass
            return DummyContext()

    monkeypatch.setattr(refresh_calendar, "get_session_factory", lambda: DummySessionFactory())

    async def crashing_refresh(_session):
        raise RuntimeError("Unexpected fatal disk corruption")

    monkeypatch.setattr(refresh_calendar, "refresh_calendar_events", crashing_refresh)

    exit_code = refresh_calendar.run_refresh()
    assert exit_code == 1
