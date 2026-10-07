from __future__ import annotations

import re
from urllib.parse import urljoin

from app.providers.news.base import (
    NewsProvider,
    NormalizedNewsItem,
    classify_region,
    classify_topic,
    clean_text,
    energy_relevant,
    fetch_text,
    is_valid_url,
    parse_news_datetime,
    parse_rss_items,
)


class AfricanEnergyChamberNewsProvider(NewsProvider):
    source_key = "african_energy_chamber"
    source_name = "African Energy Chamber"
    NEWS_URL = "https://energychamber.org/news/"
    FEED_URL = "https://energychamber.org/feed/"

    async def fetch(self) -> list[NormalizedNewsItem]:
        text = await fetch_text(self.NEWS_URL)
        items = self.parse_news_listing(text, base_url=self.NEWS_URL)
        if not items:
            # Fallback to official RSS feed if HTML listing yielded no items
            try:
                feed_text = await fetch_text(self.FEED_URL)
                items = parse_rss_items(
                    feed_text,
                    source_key=self.source_key,
                    source_name=self.source_name,
                    base_url=self.NEWS_URL,
                )
            except Exception:
                pass
        return items

    def parse_news_listing(
        self,
        html_text: str,
        base_url: str = "https://energychamber.org/news/",
    ) -> list[NormalizedNewsItem]:
        pattern = re.compile(
            r"<article[^>]*class=[\"'][^\"']*elementor-post[^\"']*[\"'][^>]*>(.*?)</article>",
            re.DOTALL | re.IGNORECASE,
        )
        articles = pattern.findall(html_text)
        if not articles:
            # Fallback for generic article tags in HTML or test fixtures
            fallback_pattern = re.compile(r"<article[^>]*>(.*?)</article>", re.DOTALL | re.IGNORECASE)
            articles = fallback_pattern.findall(html_text)

        items: list[NormalizedNewsItem] = []
        seen_urls: set[str] = set()

        for art in articles:
            # Extract title & link
            title_m = re.search(
                r"<h[1-6][^>]*class=[\"'][^\"']*elementor-post__title[^\"']*[\"'][^>]*>\s*<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>\s*</h[1-6]>",
                art,
                re.DOTALL | re.IGNORECASE,
            )
            if not title_m:
                title_m = re.search(
                    r"<h[1-6][^>]*>\s*<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>\s*</h[1-6]>",
                    art,
                    re.DOTALL | re.IGNORECASE,
                )
            if not title_m:
                title_m = re.search(
                    r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
                    art,
                    re.DOTALL | re.IGNORECASE,
                )

            # Extract excerpt
            excerpt_m = re.search(
                r"<div[^>]*class=[\"'][^\"']*elementor-post__excerpt[^\"']*[\"'][^>]*>(.*?)</div>",
                art,
                re.DOTALL | re.IGNORECASE,
            )
            if not excerpt_m:
                excerpt_m = re.search(r"<p[^>]*>(.*?)</p>", art, re.DOTALL | re.IGNORECASE)

            # Extract date
            date_m = re.search(
                r"<span[^>]*class=[\"'][^\"']*elementor-post-date[^\"']*[\"'][^>]*>(.*?)</span>",
                art,
                re.DOTALL | re.IGNORECASE,
            )
            if not date_m:
                date_m = re.search(
                    r"<time[^>]*datetime=[\"']([^\"']+)[\"'][^>]*>(.*?)</time>",
                    art,
                    re.DOTALL | re.IGNORECASE,
                )
            if not date_m:
                date_m = re.search(
                    r"<span[^>]*class=[\"'][^\"']*date[^\"']*[\"'][^>]*>(.*?)</span>",
                    art,
                    re.DOTALL | re.IGNORECASE,
                )

            raw_url = title_m.group(1).strip() if title_m else None
            url = urljoin(base_url, raw_url) if raw_url else ""
            title = clean_text(title_m.group(2) if title_m else "", 500)
            snippet = clean_text(excerpt_m.group(1) if excerpt_m else "", 600)
            raw_date = clean_text(date_m.group(1) if date_m else "")
            published_at = parse_news_datetime(raw_date) if raw_date else None

            if not title or not url or not is_valid_url(url) or not published_at:
                continue
            if url in seen_urls:
                continue
            if not energy_relevant(title, snippet):
                continue

            seen_urls.add(url)
            items.append(
                NormalizedNewsItem(
                    source_key=self.source_key,
                    source_name=self.source_name,
                    title=title,
                    url=url,
                    published_at=published_at,
                    snippet=snippet or None,
                    region=classify_region(self.source_key, title, snippet),
                    topic=classify_topic(self.source_key, title, snippet),
                    metadata_json={"page": base_url},
                )
            )

        return items
