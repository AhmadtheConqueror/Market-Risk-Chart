from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.db.session import get_engine
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    db_status = "not_configured"

    if settings.database_url:
        try:
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception:
            db_status = "unreachable"

    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
        database=db_status,
    )
