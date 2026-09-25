from __future__ import annotations

from app.providers.news.base import NewsProvider, NormalizedNewsItem, fetch_text, parse_html_news_list, parse_rss_items


class OPECNewsProvider(NewsProvider):
    source_key = "opec"
    source_name = "OPEC"
    NEWS_URL = "https://www.opec.org/press-releases.html"

    async def fetch(self) -> list[NormalizedNewsItem]:
        text = await fetch_text(self.NEWS_URL)
        if text.lstrip().startswith("<rss") or "<item" in text.lower() or "<entry" in text.lower():
            return parse_rss_items(
                text,
                source_key=self.source_key,
                source_name=self.source_name,
                base_url=self.NEWS_URL,
            )
        return parse_html_news_list(
            text,
            source_key=self.source_key,
            source_name=self.source_name,
            base_url=self.NEWS_URL,
        )
