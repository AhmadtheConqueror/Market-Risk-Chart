from __future__ import annotations

import html
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import httpx


REGIONS = {"international", "africa", "nigeria"}
TOPICS = {
    "crude_supply", "production", "opec_policy", "demand", "inventories",
    "refining", "downstream", "regulation", "nigeria_upstream", "prices",
    "geopolitics", "infrastructure",
}


@dataclass(frozen=True)
class NormalizedNewsItem:
    source_key: str
    source_name: str
    title: str
    url: str
    published_at: datetime
    snippet: str | None = None
    region: str = "international"
    topic: str = "crude_supply"
    relevance_status: str = "relevant"
    metadata_json: dict[str, Any] = field(default_factory=dict)


class NewsProvider(ABC):
    source_key: str
    source_name: str

    @abstractmethod
    async def fetch(self) -> list[NormalizedNewsItem]:
        pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_news_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(raw)
            except (TypeError, ValueError, OverflowError):
                short_formats = {"%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"}
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
                    try:
                        parsed = datetime.strptime(raw[:10] if fmt in short_formats else raw, fmt)
                        break
                    except ValueError:
                        parsed = None
                if parsed is None:
                    return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def clean_text(value: Any, limit: int | None = None) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip() if limit else text


def is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def energy_relevant(title: str, snippet: str | None = None) -> bool:
    text = f"{title} {snippet or ''}".lower()
    keywords = (
        "oil", "crude", "petroleum", "energy", "opec", "refin", "fuel", "gas", "gasoline",
        "diesel", "lng", "production", "inventory", "barrel", "pipeline", "upstream",
        "downstream", "supply", "demand", "sanction", "offshore", "terminal",
    )
    return any(keyword in text for keyword in keywords)


def classify_region(source_key: str, title: str, snippet: str | None = None) -> str:
    if source_key in {"nuprc", "nnpc"}:
        return "nigeria"
    text = f"{title} {snippet or ''}".lower()
    if any(country in text for country in ("nigeria", "angola", "libya", "algeria", "africa", "ghana")):
        return "africa"
    return "international"


def classify_topic(source_key: str, title: str, snippet: str | None = None) -> str:
    text = f"{title} {snippet or ''}".lower()
    ordered = (
        ("opec_policy", ("opec", "quota", "production cut")),
        ("nigeria_upstream", ("nuprc", "upstream", "oil licensing", "marginal field")),
        ("inventories", ("inventory", "inventories", "stockpile", "storage")),
        ("refining", ("refinery", "refining", "refined product", "crack spread")),
        ("downstream", ("fuel demand", "gasoline", "diesel", "jet fuel")),
        ("infrastructure", ("pipeline", "terminal", "port", "outage", "facility")),
        ("regulation", ("regulator", "regulation", "compliance", "sanction")),
        ("geopolitics", ("war", "conflict", "shipping", "hormuz", "red sea")),
        ("demand", ("demand", "consumption", "economic growth")),
        ("production", ("production", "output", "drilling")),
        ("prices", ("price", "brent", "wti", "market")),
    )
    for topic, terms in ordered:
        if any(term in text for term in terms):
            return topic
    return "crude_supply" if source_key in {"eia", "opec"} else "production"


def parse_rss_items(
    xml_text: str,
    *,
    source_key: str,
    source_name: str,
    base_url: str | None = None,
    limit: int = 40,
) -> list[NormalizedNewsItem]:
    root = ET.fromstring(xml_text)
    items: list[NormalizedNewsItem] = []
    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1].lower()
        if local_name not in {"item", "entry"}:
            continue
        values: dict[str, str] = {}
        for child in element:
            child_name = child.tag.rsplit("}", 1)[-1].lower()
            if child_name == "link" and child.attrib.get("href"):
                values["link"] = child.attrib["href"]
            elif child.text:
                values[child_name] = child.text
        title = clean_text(values.get("title"), 500)
        raw_url = values.get("link", "").strip()
        url = urljoin(base_url or "", raw_url)
        published_at = parse_news_datetime(
            values.get("pubdate") or values.get("published") or values.get("updated") or values.get("date")
        )
        snippet = clean_text(values.get("description") or values.get("summary") or values.get("content"), 600)
        if title and url and is_valid_url(url) and published_at and energy_relevant(title, snippet):
            items.append(NormalizedNewsItem(
                source_key=source_key,
                source_name=source_name,
                title=title,
                url=url,
                published_at=published_at,
                snippet=snippet or None,
                region=classify_region(source_key, title, snippet),
                topic=classify_topic(source_key, title, snippet),
                metadata_json={"feed": base_url or ""},
            ))
        if len(items) >= limit:
            break
    return items


class _HTMLNewsListParser(HTMLParser):
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.items: list[dict[str, str]] = []
        self.block: dict[str, str] | None = None
        self.block_depth = 0
        self.block_tag: str | None = None
        self.capture: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in {"article", "li"} and self.block is None:
            self.block = {"title": "", "url": "", "snippet": "", "published": ""}
            self.block_depth = 1
            self.block_tag = tag
        elif tag == "a" and self.block is None and any(
            marker in attrs_dict.get("class", "") for marker in ("featured-news", "news-block")
        ):
            self.block = {"title": "", "url": "", "snippet": "", "published": ""}
            self.block_depth = 1
            self.block_tag = tag
        elif tag == "div" and self.block is None and "news-block" in attrs_dict.get("class", "").split():
            self.block = {"title": "", "url": "", "snippet": "", "published": ""}
            self.block_depth = 1
            self.block_tag = tag
        elif self.block is not None and tag not in self.VOID_TAGS:
            self.block_depth += 1
        if self.block is None:
            return
        if tag == "a" and attrs_dict.get("href") and not self.block["url"]:
            self.block["url"] = urljoin(self.base_url, attrs_dict["href"] or "")
            if self.block_tag == "a":
                self.capture = None
            else:
                self.capture = "title"
        elif tag == "time":
            self.block["published"] = attrs_dict.get("datetime") or ""
            self.capture = None
        elif tag in {"p", "summary"}:
            self.capture = "snippet"
        elif tag == "div":
            css_class = attrs_dict.get("class", "")
            if "news-date" in css_class:
                self.capture = "published"
            elif "__desc" in css_class:
                self.capture = "title" if not self.block["title"].strip() else "snippet"

    def handle_endtag(self, tag: str) -> None:
        if self.block is None:
            return
        if self.capture and tag in {"a", "time", "p", "summary"}:
            self.capture = None
        self.block_depth -= 1
        if tag == self.block_tag and self.block_depth <= 0:
            self.items.append(self.block)
            self.block = None
            self.block_depth = 0
            self.block_tag = None

    def handle_data(self, data: str) -> None:
        if self.block is not None and self.capture:
            self.block[self.capture] = f"{self.block.get(self.capture, '')} {data}"


def parse_html_news_list(
    html_text: str,
    *,
    source_key: str,
    source_name: str,
    base_url: str,
    limit: int = 40,
) -> list[NormalizedNewsItem]:
    parser = _HTMLNewsListParser(base_url)
    parser.feed(html_text)
    items: list[NormalizedNewsItem] = []
    for raw in parser.items:
        title = clean_text(raw.get("title"), 500)
        snippet = clean_text(raw.get("snippet"), 600)
        published_at = parse_news_datetime(raw.get("published"))
        url = raw.get("url", "")
        if title and is_valid_url(url) and published_at and energy_relevant(title, snippet):
            items.append(NormalizedNewsItem(
                source_key=source_key,
                source_name=source_name,
                title=title,
                url=url,
                published_at=published_at,
                snippet=snippet or None,
                region=classify_region(source_key, title, snippet),
                topic=classify_topic(source_key, title, snippet),
                metadata_json={"page": base_url},
            ))
        if len(items) >= limit:
            break
    return items


async def fetch_text(url: str, *, timeout: float = 20.0) -> str:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "OilTradingRiskDashboard/1.0"})
        response.raise_for_status()
        return response.text
