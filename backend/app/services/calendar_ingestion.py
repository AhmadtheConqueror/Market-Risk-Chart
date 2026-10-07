from __future__ import annotations

from datetime import date, datetime, timezone
import logging
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calendar import CalendarEvent
from app.providers.calendar import CalendarProvider, get_calendar_providers

logger = logging.getLogger(__name__)

CANONICAL_CATEGORIES = {
    "energy",
    "central_bank",
    "macro",
    "election",
    "public_holiday",
    "bank_holiday",
    "geopolitical",
}

CANONICAL_REGIONS = {"Nigeria", "USA", "Africa", "Global"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_event_date(val: Any) -> date | None:
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str) and val.strip():
        clean_val = val.strip()[:10]
        try:
            return date.fromisoformat(clean_val)
        except ValueError:
            return None
    return None


def normalize_category(category: str | None) -> str:
    cleaned = str(category or "").strip().lower()
    # Aliases
    if cleaned in ("rates", "monetary", "centralbank"):
        return "central_bank"
    if cleaned in ("political", "geopolitics"):
        return "geopolitical"
    if cleaned in ("holidays", "holiday"):
        return "public_holiday"
    if cleaned in CANONICAL_CATEGORIES:
        return cleaned
    return "macro"


def normalize_region(region: str | None) -> str:
    cleaned = str(region or "").strip()
    for reg in CANONICAL_REGIONS:
        if cleaned.lower() == reg.lower():
            return reg
    return "Global"


def upsert_calendar_event(session: Session, event_data: dict[str, Any]) -> tuple[CalendarEvent, str]:
    """Upserts an official or manual calendar event using stable deduplication keys.

    Returns: (event, "created" | "updated" | "unchanged")
    """
    provider = str(event_data.get("provider") or "manual").strip().lower()
    external_id = event_data.get("external_id")
    title = str(event_data.get("title") or "").strip()
    raw_date = event_data.get("event_date")
    parsed_date = parse_event_date(raw_date)
    raw_end = event_data.get("end_date")
    parsed_end = parse_event_date(raw_end)
    legacy_date = event_data.get("legacy_date")
    if not parsed_date and isinstance(raw_date, str) and raw_date.strip():
        legacy_date = raw_date.strip()

    category = normalize_category(event_data.get("category"))
    region = normalize_region(event_data.get("region"))
    country = event_data.get("country")
    impact_level = str(event_data.get("impact_level") or "").strip().lower() or None
    if impact_level not in ("low", "moderate", "high"):
        impact_level = None
    description = event_data.get("description")
    source_name = event_data.get("source_name")
    source_url = event_data.get("source_url")
    source_type = event_data.get("source_type") or ("official" if provider != "manual" else "manual")
    active = event_data.get("active", True)
    if isinstance(active, str):
        active = active.lower() not in ("false", "0")
    active = bool(active)

    # 1. Deduplication lookup
    existing: CalendarEvent | None = None
    if external_id:
        existing = session.scalars(
            select(CalendarEvent).where(
                CalendarEvent.provider == provider,
                CalendarEvent.external_id == str(external_id),
            )
        ).first()

    if not existing and parsed_date:
        # Fallback dedupe by (provider, title, event_date, region)
        existing = session.scalars(
            select(CalendarEvent).where(
                CalendarEvent.provider == provider,
                CalendarEvent.title == title,
                CalendarEvent.event_date == parsed_date,
                CalendarEvent.region == region,
            )
        ).first()

    now_ts = utc_now()

    if existing:
        changed = False
        if existing.event_date != parsed_date:
            existing.event_date = parsed_date
            changed = True
        if existing.end_date != parsed_end:
            existing.end_date = parsed_end
            changed = True
        if existing.title != title:
            existing.title = title
            changed = True
        if existing.category != category:
            existing.category = category
            changed = True
        if existing.region != region:
            existing.region = region
            changed = True
        if existing.country != country:
            existing.country = country
            changed = True
        if existing.impact_level != impact_level:
            existing.impact_level = impact_level
            changed = True
        if description and existing.description != description:
            existing.description = description
            changed = True
        if source_url and existing.source_url != source_url:
            existing.source_url = source_url
            changed = True
        if source_name and existing.source_name != source_name:
            existing.source_name = source_name
            changed = True
        if existing.active != active:
            existing.active = active
            changed = True

        if source_type == "official":
            existing.verified_at = now_ts

        if changed:
            existing.updated_at = now_ts
            return existing, "updated"
        return existing, "unchanged"

    # Create new event
    new_event = CalendarEvent(
        external_id=str(external_id) if external_id else None,
        provider=provider,
        event_date=parsed_date,
        end_date=parsed_end,
        legacy_date=legacy_date,
        title=title,
        category=category,
        region=region,
        country=country,
        impact_level=impact_level,
        description=description,
        source_name=source_name,
        source_url=source_url,
        source_type=source_type,
        verified_at=now_ts if source_type == "official" else None,
        active=active,
        created_at=now_ts,
        updated_at=now_ts,
    )
    session.add(new_event)
    return new_event, "created"


async def refresh_calendar_events(
    session: Session,
    providers: Sequence[CalendarProvider] | None = None,
) -> dict[str, Any]:
    """Runs official calendar event ingestion across all providers with complete failure isolation."""
    if providers is None:
        providers = get_calendar_providers()

    summary: dict[str, Any] = {
        "sources_requested": len(providers),
        "sources_succeeded": 0,
        "sources_failed": 0,
        "events_created": 0,
        "events_updated": 0,
        "events_unchanged": 0,
        "provider_results": [],
    }

    for provider in providers:
        prov_res = {
            "name": provider.name,
            "source": provider.source_name,
            "status": "pending",
            "events_found": 0,
            "created": 0,
            "updated": 0,
            "error": None,
        }
        try:
            raw_events = await provider.get_events()
            prov_res["events_found"] = len(raw_events)

            for ev in raw_events:
                ev["provider"] = provider.name
                ev["source_name"] = provider.source_name
                ev["source_url"] = ev.get("source_url") or provider.source_url
                ev["source_type"] = "official"

                _, action = upsert_calendar_event(session, ev)
                if action == "created":
                    prov_res["created"] += 1
                    summary["events_created"] += 1
                elif action == "updated":
                    prov_res["updated"] += 1
                    summary["events_updated"] += 1
                else:
                    summary["events_unchanged"] += 1

            session.commit()
            prov_res["status"] = "success"
            summary["sources_succeeded"] += 1

        except Exception as exc:
            session.rollback()
            logger.warning("Provider %s failed during calendar refresh: %s", provider.name, exc)
            prov_res["status"] = "failed"
            prov_res["error"] = str(exc)
            summary["sources_failed"] += 1

        summary["provider_results"].append(prov_res)

    return summary


def get_calendar_events_query(
    session: Session,
    start_date: date | None = None,
    end_date: date | None = None,
    month: str | None = None,
    category: str | None = None,
    region: str | None = None,
    active: bool = True,
    include_unscheduled: bool = True,
) -> list[CalendarEvent]:
    """Queries calendar events with flexible month/date/category/region filtering."""
    stmt = select(CalendarEvent)

    if active is not None:
        stmt = stmt.where(CalendarEvent.active == active)

    if category:
        norm_cat = normalize_category(category)
        stmt = stmt.where(CalendarEvent.category == norm_cat)

    if region:
        norm_reg = normalize_region(region)
        stmt = stmt.where(CalendarEvent.region == norm_reg)

    if month:
        # Format: YYYY-MM
        try:
            m_year, m_num = int(month[:4]), int(month[5:7])
            m_start = date(m_year, m_num, 1)
            # Calculate next month start
            if m_num == 12:
                m_next = date(m_year + 1, 1, 1)
            else:
                m_next = date(m_year, m_num + 1, 1)

            if include_unscheduled:
                stmt = stmt.where(
                    (CalendarEvent.event_date.is_(None))
                    | (
                        (CalendarEvent.event_date < m_next)
                        & (
                            (CalendarEvent.end_date.isnot(None) & (CalendarEvent.end_date >= m_start))
                            | (CalendarEvent.event_date >= m_start)
                        )
                    )
                )
            else:
                stmt = stmt.where(
                    CalendarEvent.event_date.isnot(None),
                    CalendarEvent.event_date < m_next,
                    (
                        (CalendarEvent.end_date.isnot(None) & (CalendarEvent.end_date >= m_start))
                        | (CalendarEvent.event_date >= m_start)
                    ),
                )
        except Exception:
            pass
    elif start_date or end_date:
        if start_date and end_date:
            if include_unscheduled:
                stmt = stmt.where(
                    (CalendarEvent.event_date.is_(None))
                    | (CalendarEvent.event_date.between(start_date, end_date))
                )
            else:
                stmt = stmt.where(CalendarEvent.event_date.between(start_date, end_date))
        elif start_date:
            stmt = stmt.where(CalendarEvent.event_date >= start_date)
        elif end_date:
            stmt = stmt.where(CalendarEvent.event_date <= end_date)

    stmt = stmt.order_by(
        CalendarEvent.event_date.asc().nullslast(),
        CalendarEvent.title.asc(),
    )
    return session.scalars(stmt).all()


def create_manual_event(session: Session, data: dict[str, Any]) -> CalendarEvent:
    """Creates a new manual event."""
    title = str(data.get("title") or "").strip()
    if not title:
        raise ValueError("Title is required.")

    ev_data = {
        **data,
        "provider": "manual",
        "source_type": "manual",
        "source_name": data.get("source_name") or "Manual entry",
    }
    event, _ = upsert_calendar_event(session, ev_data)
    session.commit()
    session.refresh(event)
    return event


def update_manual_event(session: Session, event_id: int, data: dict[str, Any]) -> CalendarEvent:
    """Updates an existing manual event. Rejects modifications to official events."""
    event = session.get(CalendarEvent, event_id)
    if not event:
        raise KeyError(f"Calendar event {event_id} not found.")

    if event.source_type == "official":
        raise PermissionError("Official calendar events cannot be edited through manual event editing.")

    if "title" in data:
        t = str(data["title"]).strip()
        if not t:
            raise ValueError("Title cannot be empty.")
        event.title = t

    if "event_date" in data:
        event.event_date = parse_event_date(data["event_date"])
    if "end_date" in data:
        event.end_date = parse_event_date(data["end_date"])
    if "category" in data:
        event.category = normalize_category(data["category"])
    if "region" in data:
        event.region = normalize_region(data["region"])
    if "country" in data:
        event.country = data["country"]
    if "impact_level" in data:
        imp = str(data["impact_level"] or "").strip().lower() or None
        if imp in ("low", "moderate", "high"):
            event.impact_level = imp
        else:
            event.impact_level = None
    if "description" in data:
        event.description = data["description"]
    if "active" in data:
        event.active = bool(data["active"])

    event.updated_at = utc_now()
    session.commit()
    session.refresh(event)
    return event


def delete_manual_event(session: Session, event_id: int) -> bool:
    """Deletes an existing manual event. Rejects deletion of official events."""
    event = session.get(CalendarEvent, event_id)
    if not event:
        raise KeyError(f"Calendar event {event_id} not found.")

    if event.source_type == "official":
        raise PermissionError("Official calendar events cannot be deleted.")

    session.delete(event)
    session.commit()
    return True


def migrate_legacy_events(session: Session, legacy_events: list[dict[str, Any]]) -> dict[str, Any]:
    """Migrates legacy browser localStorage calendar events to the database authoritative store."""
    migrated = 0
    skipped = 0

    for item in legacy_events:
        title = str(item.get("title") or "").strip()
        if not title:
            skipped += 1
            continue

        raw_id = str(item.get("id") or "").strip()
        # Discard default demo fixtures if requested
        if raw_id.startswith("fixture-") or raw_id.startswith("demo-"):
            skipped += 1
            continue

        # Force provider to manual and preserve legacy date
        payload = {
            **item,
            "provider": "manual",
            "source_type": "manual",
            "source_name": item.get("source_name") or "Migrated from browser storage",
            "external_id": raw_id or None,
        }

        try:
            _, action = upsert_calendar_event(session, payload)
            if action in ("created", "updated"):
                migrated += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1

    session.commit()
    return {
        "migrated": migrated,
        "skipped": skipped,
        "total_submitted": len(legacy_events),
    }
