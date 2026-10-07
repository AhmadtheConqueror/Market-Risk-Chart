from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.calendar import (
    CalendarEventCreate,
    CalendarEventItem,
    CalendarEventUpdate,
    CalendarMigrationRequest,
    CalendarMigrationResponse,
    CalendarRefreshResponse,
)
from app.services.calendar_ingestion import (
    create_manual_event,
    delete_manual_event,
    get_calendar_events_query,
    migrate_legacy_events,
    parse_event_date,
    refresh_calendar_events,
    update_manual_event,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.post("/refresh", response_model=CalendarRefreshResponse)
async def refresh_calendar(
    session: Annotated[Session, Depends(get_db)],
) -> Any:
    """Runs official calendar event ingestion across all providers with isolated error handling."""
    summary = await refresh_calendar_events(session)
    return summary


@router.get("/events", response_model=list[CalendarEventItem])
def get_events(
    session: Annotated[Session, Depends(get_db)],
    month: str | None = Query(None, description="Month in YYYY-MM format"),
    start_date: str | None = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str | None = Query(None, description="End date in YYYY-MM-DD format"),
    category: str | None = Query(None, description="Event category filter"),
    region: str | None = Query(None, description="Event region filter"),
    active: bool = Query(True, description="Filter active events"),
    include_unscheduled: bool = Query(True, description="Whether to include events with null date"),
) -> Any:
    """Retrieves calendar events with flexible month/date/category/region filtering."""
    s_date: date | None = parse_event_date(start_date) if start_date else None
    e_date: date | None = parse_event_date(end_date) if end_date else None

    events = get_calendar_events_query(
        session=session,
        start_date=s_date,
        end_date=e_date,
        month=month,
        category=category,
        region=region,
        active=active,
        include_unscheduled=include_unscheduled,
    )
    return [e.to_dict() for e in events]


@router.post("/events", response_model=CalendarEventItem, status_code=status.HTTP_201_CREATED)
def create_event(
    event_in: CalendarEventCreate,
    session: Annotated[Session, Depends(get_db)],
) -> Any:
    """Creates a new manual calendar event."""
    try:
        event = create_manual_event(session, event_in.model_dump())
        return event.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/events/{event_id}", response_model=CalendarEventItem)
def update_event(
    event_id: int,
    event_in: CalendarEventUpdate,
    session: Annotated[Session, Depends(get_db)],
) -> Any:
    """Updates an existing manual event. Rejects modifications to official events."""
    try:
        data = event_in.model_dump(exclude_unset=True)
        event = update_manual_event(session, event_id, data)
        return event.to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/events/{event_id}")
def delete_event(
    event_id: int,
    session: Annotated[Session, Depends(get_db)],
) -> Any:
    """Deletes an existing manual event. Rejects deletion of official events."""
    try:
        delete_manual_event(session, event_id)
        return {"status": "deleted", "id": event_id}
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/migrate-legacy", response_model=CalendarMigrationResponse)
def migrate_legacy(
    req: CalendarMigrationRequest,
    session: Annotated[Session, Depends(get_db)],
) -> Any:
    """Migrates browser localStorage calendar events to the database authoritative store."""
    result = migrate_legacy_events(session, req.events)
    return result
