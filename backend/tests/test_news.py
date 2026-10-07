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


def test_refresh_endpoint_returns_valid_summary_schema(client, monkeypatch):
    """POST /api/news/refresh responds 200 with the NewsRefreshSummary schema."""
    from app.providers.news.base import NormalizedNewsItem

    now = datetime.now(timezone.utc)
    good_item = NormalizedNewsItem(
        source_key="eia",
        source_name="EIA",
        title="U.S. crude inventories fall",
        url="https://example.com/eia-refresh-test",
        published_at=now - timedelta(hours=2),
        snippet="Weekly EIA report.",
        region="international",
        topic="inventories",
    )

    class _GoodProvider:
        source_key = "eia"
        source_name = "EIA"
        async def fetch(self):
            return [good_item]

    monkeypatch.setattr("app.services.news_ingestion.get_news_providers", lambda: [_GoodProvider()])

    response = client.post("/api/news/refresh")
    assert response.status_code == 200
    body = response.json()

    # Schema fields must all be present
    for field in ("sources_requested", "sources_succeeded", "items_found",
                  "stored", "updated", "unchanged", "failed", "errors",
                  "sources", "retrieved_at"):
        assert field in body, f"Missing field: {field}"

    assert body["sources_requested"] == 1
    assert body["sources_succeeded"] == 1
    assert body["stored"] == 1
    assert body["failed"] == 0
    assert body["errors"] == []


def test_refresh_endpoint_partial_failure_is_non_blocking(client, monkeypatch):
    """POST /api/news/refresh still returns 200 when one source raises (e.g. OPEC 403)."""
    from app.providers.news.base import NormalizedNewsItem

    now = datetime.now(timezone.utc)
    good_item = NormalizedNewsItem(
        source_key="eia",
        source_name="EIA",
        title="Partial refresh test item",
        url="https://example.com/partial-refresh",
        published_at=now - timedelta(hours=1),
        snippet="Excerpt.",
        region="international",
        topic="inventories",
    )

    class _GoodProvider:
        source_key = "eia"
        source_name = "EIA"
        async def fetch(self):
            return [good_item]

    class _FailingProvider:
        source_key = "opec"
        source_name = "OPEC"
        async def fetch(self):
            raise RuntimeError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(
        "app.services.news_ingestion.get_news_providers",
        lambda: [_GoodProvider(), _FailingProvider()],
    )

    response = client.post("/api/news/refresh")
    # Partial failure must NOT cause a 5xx — the endpoint is non-blocking.
    assert response.status_code == 200
    body = response.json()

    assert body["sources_requested"] == 2
    assert body["sources_succeeded"] == 1

    # OPEC failure is reported but no raw Python traceback is exposed
    assert len(body["errors"]) == 1
    assert "Traceback" not in body["errors"][0]
    assert "opec" in body["errors"][0].lower()

    # The good source's item was stored
    assert body["stored"] == 1


MOCK_AEC_HTML = """
<div class="elementor-posts-container">
  <article class="elementor-post elementor-grid-item post-1">
    <h3 class="elementor-post__title">
      <a href="https://energychamber.org/kenya-refinery/">Africa Must Build, Not Block: AEC Condemns Court Order Threatening Dangote’s Kenya Refinery</a>
    </h3>
    <div class="elementor-post__excerpt">
      <p>Dangote’s planned 700,000-barrel-per-day refinery in Lamu could transform East Africa’s downstream landscape.</p>
    </div>
    <span class="elementor-post-date">September 29, 2026</span>
  </article>

  <!-- Duplicate item with identical URL should be deduplicated -->
  <article class="elementor-post elementor-grid-item post-1-dup">
    <h3 class="elementor-post__title">
      <a href="https://energychamber.org/kenya-refinery/">Africa Must Build, Not Block: AEC Condemns Court Order Threatening Dangote’s Kenya Refinery</a>
    </h3>
    <div class="elementor-post__excerpt">
      <p>Dangote’s planned 700,000-barrel-per-day refinery in Lamu could transform East Africa’s downstream landscape.</p>
    </div>
    <span class="elementor-post-date">September 29, 2026</span>
  </article>

  <article class="elementor-post elementor-grid-item post-2">
    <h3 class="elementor-post__title">
      <a href="https://energychamber.org/nigeria-lng-expansion/">Ima Gas’ $800M FID Brings Major Boost to Nigeria’s LNG Expansion</a>
    </h3>
    <div class="elementor-post__excerpt">
      <p>The Ima Gas FID advances upstream gas discovery for Nigeria LNG export and domestic supply.</p>
    </div>
    <span class="elementor-post-date">September 24, 2026</span>
  </article>

  <article class="elementor-post elementor-grid-item post-3">
    <h3 class="elementor-post__title">
      <a href="https://energychamber.org/ludoil-mediterranean-refinery/">Ludoil Acquires Controlling Stake in Mediterranean’s Largest Refinery</a>
    </h3>
    <div class="elementor-post__excerpt">
      <p>Ludoil finalizes acquisition of ISAB refinery in Sicily, creating Italy's largest private energy company.</p>
    </div>
    <span class="elementor-post-date">September 25, 2026</span>
  </article>

  <!-- Item with missing publication date should be skipped -->
  <article class="elementor-post elementor-grid-item post-undated">
    <h3 class="elementor-post__title">
      <a href="https://energychamber.org/undated-story/">Undated energy briefing</a>
    </h3>
    <div class="elementor-post__excerpt"><p>Some briefing text.</p></div>
  </article>
</div>
"""


def test_aec_listing_parsing_and_duplicate_url_handling():
    from app.providers.news.african_energy_chamber import AfricanEnergyChamberNewsProvider

    provider = AfricanEnergyChamberNewsProvider()
    items = provider.parse_news_listing(MOCK_AEC_HTML, base_url="https://energychamber.org/news/")

    # 5 articles in HTML: 1 duplicate skipped, 1 undated skipped -> 3 valid items
    assert len(items) == 3

    # Verify Item 1: Kenya/East Africa story -> region = "africa"
    kenya_item = items[0]
    assert kenya_item.source_key == "african_energy_chamber"
    assert kenya_item.source_name == "African Energy Chamber"
    assert kenya_item.title == "Africa Must Build, Not Block: AEC Condemns Court Order Threatening Dangote’s Kenya Refinery"
    assert kenya_item.url == "https://energychamber.org/kenya-refinery/"
    assert kenya_item.published_at == datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
    assert kenya_item.region == "africa"
    assert kenya_item.topic == "refining"
    assert "Dangote’s planned 700,000-barrel-per-day refinery" in (kenya_item.snippet or "")

    # Verify Item 2: Nigeria-specific story -> region = "nigeria"
    nigeria_item = items[1]
    assert nigeria_item.title == "Ima Gas’ $800M FID Brings Major Boost to Nigeria’s LNG Expansion"
    assert nigeria_item.url == "https://energychamber.org/nigeria-lng-expansion/"
    assert nigeria_item.published_at == datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc)
    assert nigeria_item.region == "nigeria"

    # Verify Item 3: Explicitly global/non-African story -> region = "international"
    global_item = items[2]
    assert global_item.title == "Ludoil Acquires Controlling Stake in Mediterranean’s Largest Refinery"
    assert global_item.url == "https://energychamber.org/ludoil-mediterranean-refinery/"
    assert global_item.region == "international"


def test_aec_factory_registration_and_five_sources_requested():
    from app.providers.news.factory import get_news_providers

    providers = get_news_providers()
    assert len(providers) == 5
    source_keys = [p.source_key for p in providers]
    assert source_keys == ["eia", "opec", "nuprc", "nnpc", "african_energy_chamber"]

    aec_provider = next(p for p in providers if p.source_key == "african_energy_chamber")
    assert aec_provider.source_name == "African Energy Chamber"


@pytest.mark.anyio
async def test_aec_partial_source_failure_is_non_blocking(db_session):
    from app.services.news_ingestion import refresh_news

    now = datetime.now(timezone.utc)
    good_item = NormalizedNewsItem(
        source_key="african_energy_chamber",
        source_name="African Energy Chamber",
        title="Namibia Offshore Exploration Accelerates",
        url="https://energychamber.org/namibia-offshore",
        published_at=now - timedelta(hours=2),
        snippet="New exploration campaigns offshore Namibia.",
        region="africa",
        topic="production",
    )

    class _GoodAECProvider:
        source_key = "african_energy_chamber"
        source_name = "African Energy Chamber"
        async def fetch(self):
            return [good_item]

    class _FailingOPECProvider:
        source_key = "opec"
        source_name = "OPEC"
        async def fetch(self):
            raise RuntimeError("HTTP Error 403: Forbidden")

    from unittest.mock import patch
    with patch("app.services.news_ingestion.get_news_providers", return_value=[_GoodAECProvider(), _FailingOPECProvider()]):
        summary = await refresh_news(db_session)
        assert summary.sources_requested == 2
        assert summary.sources_succeeded == 1
        assert summary.stored == 1
        assert len(summary.errors) == 1
        assert "opec" in summary.errors[0].lower()


def test_aec_7day_filtering_and_gemini_context_inclusion(db_session):
    now = datetime.now(timezone.utc)

    # 1 recent item (2 days ago) - should be included
    recent_aec = NewsItem(
        source_key="african_energy_chamber",
        source_name="African Energy Chamber",
        title="Recent AEC Africa Story",
        url="https://energychamber.org/recent-story",
        published_at=now - timedelta(days=2),
        retrieved_at=now,
        snippet="Recent African energy developments.",
        region="africa",
        topic="crude_supply",
        relevance_status="relevant",
        metadata_json={},
        active=True,
    )
    # 1 old item (12 days ago) - should be excluded by 7-day window
    old_aec = NewsItem(
        source_key="african_energy_chamber",
        source_name="African Energy Chamber",
        title="Old AEC Africa Story",
        url="https://energychamber.org/old-story",
        published_at=now - timedelta(days=12),
        retrieved_at=now,
        snippet="Old African energy developments.",
        region="africa",
        topic="crude_supply",
        relevance_status="relevant",
        metadata_json={},
        active=True,
    )
    db_session.add(recent_aec)
    db_session.add(old_aec)
    db_session.commit()

    # Test 7-day filtering
    africa_news = get_recent_news(db_session, region="africa", days=7)
    titles = [item.title for item in africa_news]
    assert "Recent AEC Africa Story" in titles
    assert "Old AEC Africa Story" not in titles

    # Test Gemini AI context inclusion
    context = build_dashboard_ai_context(db_session)
    assert "news" in context
    news_titles = [n["title"] for n in context["news"]]
    assert "Recent AEC Africa Story" in news_titles
    assert "Old AEC Africa Story" not in news_titles

    aec_entry = next(n for n in context["news"] if n["title"] == "Recent AEC Africa Story")
    assert aec_entry["source"] == "African Energy Chamber"
    assert aec_entry["source_key"] == "african_energy_chamber"
    assert aec_entry["region"] == "africa"
    assert aec_entry["topic"] == "crude_supply"
    assert aec_entry["url"] == "https://energychamber.org/recent-story"
    assert aec_entry["snippet"] == "Recent African energy developments."
    assert "published_at" in aec_entry


