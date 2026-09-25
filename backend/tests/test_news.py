from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.news import NewsItem
from app.providers.news.base import (
    NormalizedNewsItem,
    classify_region,
    classify_topic,
    parse_html_news_list,
    parse_rss_items,
)
from app.services.ai_context import build_dashboard_ai_context
from app.services.news_ingestion import get_recent_news, refresh_news


def test_rss_parser_normalizes_energy_headline_and_rejects_missing_date():
    xml = """
    <rss><channel>
      <item>
        <title>OPEC discusses crude supply outlook</title>
        <link>https://example.com/opec-1</link>
        <pubDate>Thu, 24 Sep 2026 10:00:00 GMT</pubDate>
        <description>Official production policy update.</description>
      </item>
      <item>
        <title>Undated energy note</title>
        <link>https://example.com/undated</link>
        <description>Oil market note without a publication date.</description>
      </item>
    </channel></rss>
    """
    items = parse_rss_items(
        xml,
        source_key="opec",
        source_name="OPEC",
        base_url="https://example.com/feed.xml",
    )
    assert len(items) == 1
    assert items[0].region == "international"
    assert items[0].topic == "opec_policy"
    assert items[0].snippet == "Official production policy update."


def test_html_news_list_parser_extracts_metadata_without_article_body():
    html = """
    <ul><li>
      <a href="/news/1">Nigeria crude production update</a>
      <time datetime="2026-09-24T10:00:00Z">24 September 2026</time>
      <p>Short public excerpt only.</p>
    </li></ul>
    """
    items = parse_html_news_list(
        html,
        source_key="nnpc",
        source_name="NNPC Limited",
        base_url="https://example.com/news/",
    )
    assert len(items) == 1
    assert items[0].url == "https://example.com/news/1"
    assert items[0].region == "nigeria"
    assert "full article" not in (items[0].snippet or "").lower()


def test_region_and_topic_classification_is_deterministic():
    assert classify_region("nuprc", "Production update", "Nigeria crude output") == "nigeria"
    assert classify_region("opec", "OPEC discusses Angola quota", "Africa supply") == "africa"
    assert classify_topic("eia", "U.S. crude inventories rise", "Storage data") == "inventories"


class FakeProvider:
    def __init__(self, source_key: str, items: list[NormalizedNewsItem], error: Exception | None = None):
        self.source_key = source_key
        self.source_name = source_key.upper()
        self.items = items
        self.error = error

    async def fetch(self):
        if self.error:
            raise self.error
        return self.items


@pytest.mark.anyio
async def test_refresh_is_idempotent_and_partial_source_failure_is_reported(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    item = NormalizedNewsItem(
        source_key="eia",
        source_name="EIA",
        title="U.S. crude inventories rise",
        url="https://example.com/news/1",
        published_at=now - timedelta(days=1),
        snippet="Short source excerpt.",
        region="international",
        topic="inventories",
    )
    providers = [FakeProvider("eia", [item]), FakeProvider("opec", [], RuntimeError("feed unavailable"))]
    monkeypatch.setattr("app.services.news_ingestion.get_news_providers", lambda: providers)

    first = await refresh_news(db_session)
    assert first.stored == 1
    assert first.sources_succeeded == 1
    assert first.failed == 1

    second = await refresh_news(db_session)
    assert second.stored == 0
    assert second.unchanged == 1
    assert db_session.query(NewsItem).count() == 1
    assert db_session.query(NewsItem).first().snippet == "Short source excerpt."


def test_recent_news_excludes_old_items_and_filters_region(db_session):
    now = datetime.now(timezone.utc)
    db_session.add_all([
        NewsItem(
            source_key="eia", source_name="EIA", title="Recent Nigeria supply item",
            url="https://example.com/recent", published_at=now - timedelta(days=1),
            retrieved_at=now, snippet="Excerpt", region="nigeria", topic="production",
            relevance_status="relevant", metadata_json={}, active=True,
        ),
        NewsItem(
            source_key="eia", source_name="EIA", title="Old item",
            url="https://example.com/old", published_at=now - timedelta(days=30),
            retrieved_at=now, snippet="Old excerpt", region="international", topic="prices",
            relevance_status="relevant", metadata_json={}, active=True,
        ),
    ])
    db_session.commit()
    recent = get_recent_news(db_session, region="nigeria")
    assert [item.title for item in recent] == ["Recent Nigeria supply item"]


def test_latest_news_endpoint_returns_verified_recent_items(client, db_session):
    now = datetime.now(timezone.utc)
    db_session.add(NewsItem(
        source_key="nuprc", source_name="NUPRC", title="Nigeria production update",
        url="https://example.com/endpoint", published_at=now - timedelta(days=1),
        retrieved_at=now, snippet="Short excerpt", region="nigeria", topic="production",
        relevance_status="relevant", metadata_json={}, active=True,
    ))
    db_session.commit()
    response = client.get("/api/news/latest?region=nigeria&limit=5")
    assert response.status_code == 200
    assert response.json()["items"][0]["source_name"] == "NUPRC"


def test_ai_context_contains_recent_news_only(db_session, seed_test_data):
    now = datetime.now(timezone.utc)
    db_session.add(NewsItem(
        source_key="opec", source_name="OPEC", title="OPEC supply policy update",
        url="https://example.com/opec", published_at=now - timedelta(days=1),
        retrieved_at=now, snippet="Source excerpt", region="international", topic="opec_policy",
        relevance_status="relevant", metadata_json={}, active=True,
    ))
    db_session.add(NewsItem(
        source_key="opec", source_name="OPEC", title="Full article body must not be sent",
        url="https://example.com/old-body", published_at=now - timedelta(days=20),
        retrieved_at=now, snippet="Old", region="international", topic="prices",
        relevance_status="relevant", metadata_json={}, active=True,
    ))
    db_session.commit()

    context = build_dashboard_ai_context(db_session)
    assert len(context["news"]) == 1
    assert context["news"][0]["source"] == "OPEC"
    assert context["news"][0]["snippet"] == "Source excerpt"
