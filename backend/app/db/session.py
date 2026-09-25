from __future__ import annotations

from collections.abc import Generator

from fastapi import HTTPException, status
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


_engine: Engine | None = None
_engine_url: str | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _engine_url, _session_factory

    database_url = get_settings().sqlalchemy_database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")

    if _engine is None or _engine_url != database_url:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        _engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        _engine_url = database_url
        _session_factory = sessionmaker(
            bind=_engine,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    try:
        factory = get_session_factory()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "database": "not_configured"},
        ) from exc

    with factory() as session:
        yield session
