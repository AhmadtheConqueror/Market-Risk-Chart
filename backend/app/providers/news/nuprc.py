from __future__ import annotations

from typing import Any

from app.providers.news.base import NewsProvider, NormalizedNewsItem, classify_region, classify_topic, clean_text, energy_relevant, fetch_text, parse_news_datetime


class NUPRCNewsProvider(NewsProvider):
    source_key = "nuprc"
    source_name = "Nigerian Upstream Petroleum Regulatory Commission"
    API_URL = "https://www.nuprc.gov.ng/api/news"
    ARTICLE_URL = "https://www.nuprc.gov.ng/media/news/{article_id}"

    async def fetch(self) -> list[NormalizedNewsItem]:
        import json

        payload = json.loads(await fetch_text(self.API_URL + "?status=published&limit=50"))
        articles = payload.get("data", []) if isinstance(payload, dict) else []
        items: list[NormalizedNewsItem] = []
        for article in articles:
            if not isinstance(article, dict):
                continue
            title = clean_text(article.get("title"), 500)
            snippet = clean_text(article.get("excerpt") or article.get("summary"), 600)
            published_at = parse_news_datetime(article.get("publishedAt") or article.get("createdAt"))
            article_id = str(article.get("_id") or article.get("id") or "").strip()
            url = self.ARTICLE_URL.format(article_id=article_id) if article_id else str(article.get("url") or "")
            if not title or not url or not published_at or not energy_relevant(title, snippet):
                continue
            items.append(NormalizedNewsItem(
                source_key=self.source_key,
                source_name=self.source_name,
                title=title,
                url=url,
                published_at=published_at,
                snippet=snippet or None,
                region=classify_region(self.source_key, title, snippet),
                topic=classify_topic(self.source_key, title, snippet),
                metadata_json={"provider_record": {"id": article_id}},
            ))
        return items
