from __future__ import annotations

from app.providers.news.base import NewsProvider, NormalizedNewsItem, fetch_text, parse_rss_items


class EIANewsProvider(NewsProvider):
    source_key = "eia"
    source_name = "U.S. Energy Information Administration"
    FEED_URLS = (
        "https://www.eia.gov/rss/todayinenergy.xml",
        "https://www.eia.gov/rss/press_rss.xml",
    )

    async def fetch(self) -> list[NormalizedNewsItem]:
        items: list[NormalizedNewsItem] = []
        errors: list[Exception] = []
        for feed_url in self.FEED_URLS:
            try:
                xml_text = await fetch_text(feed_url)
                items.extend(parse_rss_items(
                    xml_text,
                    source_key=self.source_key,
                    source_name=self.source_name,
                    base_url=feed_url,
                ))
            except Exception as exc:
                errors.append(exc)
        if not items and len(errors) == len(self.FEED_URLS):
            raise errors[0]
        return _dedupe(items)


def _dedupe(items: list[NormalizedNewsItem]) -> list[NormalizedNewsItem]:
    seen: set[str] = set()
    result: list[NormalizedNewsItem] = []
    for item in sorted(items, key=lambda value: value.published_at, reverse=True):
        if item.url not in seen:
            seen.add(item.url)
            result.append(item)
    return result
