from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import anyio
from threading import Lock
from fastapi import HTTPException
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.news import NewsItem
from app.models.risk import DashboardContent
from app.providers.news.base import news_audit
from app.providers.news import NormalizedNewsItem, get_news_providers
from app.schemas.news import NewsRefreshSummary, NewsSourceResult

logger = logging.getLogger(__name__)


def validate_news_item(item: NormalizedNewsItem) -> None:
    if not item.source_key or not item.source_name:
        raise ValueError("Source is required.")
    if not item.title.strip():
        raise ValueError("Headline is required.")
    parsed_url = urlparse(item.url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("A valid external URL is required.")
    if not item.published_at:
        raise ValueError("Publication timestamp is required.")
    if item.region not in {"international", "africa", "nigeria"}:
        raise ValueError(f"Unsupported region: {item.region}")


def upsert_news_item(db: Session, item: NormalizedNewsItem, retrieved_at: datetime) -> str:
    validate_news_item(item)
    existing = db.scalars(select(NewsItem).where(NewsItem.url == item.url)).first()
    values = {
        "source_key": item.source_key,
        "source_name": item.source_name,
        "title": item.title,
        "published_at": item.published_at,
        "retrieved_at": retrieved_at,
        "snippet": item.snippet,
        "region": item.region,
        "topic": item.topic,
        "relevance_status": item.relevance_status,
        "metadata_json": item.metadata_json or {},
        "active": True,
    }
    if existing is None:
        db.add(NewsItem(url=item.url, created_at=retrieved_at, updated_at=retrieved_at, **values))
        return "stored"

    changed = any(
        not _values_equal(getattr(existing, key), value)
        for key, value in values.items()
        if key != "retrieved_at"
    )
    if not changed:
        existing.retrieved_at = retrieved_at
        return "unchanged"
    for key, value in values.items():
        setattr(existing, key, value)
    existing.updated_at = retrieved_at
    return "updated"


def _values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, datetime) and isinstance(right, datetime):
        left_utc = left.replace(tzinfo=timezone.utc) if left.tzinfo is None else left.astimezone(timezone.utc)
        right_utc = right.replace(tzinfo=timezone.utc) if right.tzinfo is None else right.astimezone(timezone.utc)
        return left_utc == right_utc
    return left == right


_refresh_lock = Lock()
NEWS_REFRESH_LOCK_ID = 1313167187
PROVIDER_BUDGET_SECONDS = 45


async def refresh_news(db: Session) -> NewsRefreshSummary:
    """One refresh per database; transaction lock is safe on Supabase poolers."""
    postgres = db.get_bind().dialect.name == "postgresql"
    if postgres:
        acquired = db.execute(text("SELECT pg_try_advisory_xact_lock(:key)"),
                              {"key": NEWS_REFRESH_LOCK_ID}).scalar_one()
    else:
        acquired = _refresh_lock.acquire(blocking=False)
    if not acquired:
        raise HTTPException(status_code=409, detail="News refresh already in progress")
    try:
        return await _refresh_news(db)
    except BaseException:
        db.rollback()  # Also releases PostgreSQL transaction lock on cancellation.
        raise
    finally:
        if not postgres:
            _refresh_lock.release()


async def _refresh_news(db: Session) -> NewsRefreshSummary:
    providers = get_news_providers()
    retrieved_at = datetime.now(timezone.utc)
    total_found = stored = updated = unchanged = failed = 0
    errors: list[str] = []
    source_results: list[NewsSourceResult] = []

    # sqlite legacy transaction control does not BEGIN for SELECT/SAVEPOINT.
    # Establish the outer transaction so releasing a savepoint cannot commit it.
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN")

    for provider in providers:
        audit = {"requests": [], "candidates": 0, "rejections": {}}
        token = news_audit.set(audit)
        result = NewsSourceResult(source_key=provider.source_key, status="failed")
        try:
            with anyio.fail_after(PROVIDER_BUDGET_SECONDS):
                items = await provider.fetch()
            total_found += len(items)
            result.items_found = len(items)
            unique = {item.url: item for item in items}
            result.duplicates = len(items) - len(unique)
            result.latest_publication = max((item.published_at for item in items), default=None)
            cutoff = retrieved_at - timedelta(days=7)
            result.fresh_items = sum(item.published_at >= cutoff for item in unique.values())
            result.excluded_stale = len(unique) - result.fresh_items
            result.fresh_by_region = {region: sum(item.region == region and item.published_at >= cutoff
                for item in unique.values()) for region in ("international", "africa", "nigeria")}
            # A failed source rolls back only its own changes, never other providers.
            with db.begin_nested():
                for item in unique.values():
                    try:
                        action = upsert_news_item(db, item, retrieved_at)
                    except ValueError as exc:
                        result.rejected += 1
                        reasons = audit["rejections"]
                        reason = str(exc)
                        reasons[reason] = reasons.get(reason, 0) + 1
                        continue
                    setattr(result, action, getattr(result, action) + 1)
                    db.flush()  # URL dedupe also works with autoflush=False.
            request_errors = any(request.get("error") for request in audit["requests"])
            parser_rejected = sum(audit["rejections"].values())
            validation_rejected = result.rejected
            result.rejected = parser_rejected
            if not items and (request_errors or any(reason not in {"not_energy_relevant", "duplicate_url"} for reason in audit["rejections"])):
                result.status = "failed"
                result.error = "No valid dated energy stories; inspect requests and rejection reasons."
                failed += 1
            elif validation_rejected or request_errors:
                result.status = "partial"
                result.error = "Some requests or candidate stories failed; inspect provider audit."
                failed += 1
            else:
                result.status = "succeeded"
            stored += result.stored
            updated += result.updated
            unchanged += result.unchanged
        except Exception as exc:
            failed += 1
            result.stored = result.updated = result.unchanged = 0
            result.error = f"{type(exc).__name__}: {exc}"
            logger.warning("News source failed: %s: %s", provider.source_key, result.error)
        finally:
            news_audit.reset(token)
            result.requests = audit["requests"]
            result.latest_source_publication = audit.get("latest_source_publication", result.latest_publication)
            result.candidates = audit["candidates"]
            result.outcome = ("provider_unavailable" if result.status == "failed" else
                "articles_available" if result.fresh_items else
                "articles_rejected_irrelevant" if audit["rejections"].get("not_energy_relevant") else
                "no_recent_articles")
            result.rejection_reasons = audit["rejections"]
            result.rejected = sum(audit["rejections"].values())
            if result.error:
                errors.append(f"{provider.source_key}: {result.error}")
            source_results.append(result)

    summary = NewsRefreshSummary(
        sources_requested=len(providers),
        sources_succeeded=sum(1 for result in source_results if result.status in {"succeeded", "partial"}),
        items_found=total_found, stored=stored, updated=updated, unchanged=unchanged,
        failed=failed, errors=errors[:50], sources=source_results, retrieved_at=retrieved_at,
    )
    # Keep the last refresh auditable without adding a table or migration.
    entry = db.scalars(select(DashboardContent).where(
        DashboardContent.section_key == "news_refresh", DashboardContent.item_key == "latest",
    )).first()
    if entry is None:
        entry = DashboardContent(section_key="news_refresh", item_key="latest", content="Provider refresh audit")
        db.add(entry)
    entry.active = False  # Operational audit, not dashboard/AI narrative content.
    entry.metadata_json = summary.model_dump(mode="json")
    entry.updated_at = retrieved_at
    db.commit()
    return summary


def get_last_news_refresh(db: Session) -> dict | None:
    entry = db.scalars(select(DashboardContent).where(
        DashboardContent.section_key == "news_refresh", DashboardContent.item_key == "latest",
    )).first()
    return entry.metadata_json if entry else None


def get_recent_news(
    db: Session,
    *,
    region: str | None = None,
    topic: str | None = None,
    limit: int = 15,
    days: int = 7,
) -> list[NewsItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    statement = select(NewsItem).where(NewsItem.active.is_(True), NewsItem.published_at >= cutoff)
    if region:
        statement = statement.where(NewsItem.region == region)
    if topic:
        statement = statement.where(NewsItem.topic == topic)
    statement = statement.order_by(NewsItem.published_at.desc(), NewsItem.id.desc()).limit(limit)
    return list(db.scalars(statement).all())
