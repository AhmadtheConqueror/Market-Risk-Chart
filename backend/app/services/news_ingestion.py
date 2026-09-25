from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news import NewsItem
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


async def refresh_news(db: Session) -> NewsRefreshSummary:
    providers = get_news_providers()
    retrieved_at = datetime.now(timezone.utc)
    total_found = stored = updated = unchanged = failed = 0
    errors: list[str] = []
    source_results: list[NewsSourceResult] = []

    for provider in providers:
        try:
            items = await provider.fetch()
            total_found += len(items)
            source_stored = source_updated = source_unchanged = source_rejected = 0
            for item in items:
                try:
                    action = upsert_news_item(db, item, retrieved_at)
                except ValueError as exc:
                    source_rejected += 1
                    if len(errors) < 50:
                        errors.append(f"{provider.source_key}: {exc}")
                    continue
                if action == "stored":
                    stored += 1
                    source_stored += 1
                elif action == "updated":
                    updated += 1
                    source_updated += 1
                else:
                    unchanged += 1
                    source_unchanged += 1
            if source_rejected:
                failed += source_rejected
            source_results.append(NewsSourceResult(
                source_key=provider.source_key,
                status="partial" if source_rejected else "succeeded",
                items_found=len(items),
                stored=source_stored,
                updated=source_updated,
                unchanged=source_unchanged,
                error=f"{source_rejected} item(s) rejected during validation" if source_rejected else None,
            ))
        except Exception as exc:  # One source must not block the others.
            failed += 1
            message = f"{provider.source_key}: {type(exc).__name__}: {exc}"
            logger.warning("News source failed: %s", message)
            errors.append(message)
            source_results.append(NewsSourceResult(
                source_key=provider.source_key,
                status="failed",
                error=str(exc),
            ))

    db.commit()
    return NewsRefreshSummary(
        sources_requested=len(providers),
        sources_succeeded=sum(1 for result in source_results if result.status in {"succeeded", "partial"}),
        items_found=total_found,
        stored=stored,
        updated=updated,
        unchanged=unchanged,
        failed=failed,
        errors=errors[:50],
        sources=source_results,
        retrieved_at=retrieved_at,
    )


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
