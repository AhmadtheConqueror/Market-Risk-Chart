from __future__ import annotations

from contextvars import ContextVar
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
import anyio


# One refresh task owns its audit; no credentials or response bodies are retained.
news_audit: ContextVar[dict | None] = ContextVar("news_audit", default=None)


def reject_reason(*, title, url, published_at, snippet=None):
    if not title:
        return "missing_title"
    if not is_valid_url(url):
        return "invalid_url"
    if not published_at:
        return "missing_or_invalid_publication_date"
    if not energy_relevant(title, snippet):
        return "not_energy_relevant"
    return None


def audit_candidate(reason=None, published_at=None):
    audit = news_audit.get()
    if audit is not None:
        if published_at is not None:
            previous = audit.get("latest_source_publication")
            audit["latest_source_publication"] = max(previous, published_at) if previous else published_at
        audit["candidates"] = audit.get("candidates", 0) + 1
        if reason:
            reasons = audit.setdefault("rejections", {})
            reasons[reason] = reasons.get(reason, 0) + 1


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
        "nnpc", "nuprc", "oil", "crude", "petroleum", "energy", "opec", "refin", "fuel", "gas", "gasoline",
        "diesel", "lng", "production", "inventory", "barrel", "pipeline", "upstream",
        "downstream", "supply", "demand", "sanction", "offshore", "terminal",
    )
    return any(keyword in text for keyword in keywords)


NIGERIA_TERMS = (
    "nigeria", "nigerian", "nnpc", "nuprc", "nlng",
    "lagos", "abuja", "port harcourt", "bonny", "forcados",
    "escravos", "brass river", "niger delta",
)
AFRICA_TERMS = (
    "africa", "african", "angola", "libya", "algeria", "ghana",
    "mozambique", "namibia", "senegal", "gabon", "congo",
    "equatorial guinea", "south africa", "egypt", "kenya",
    "uganda", "tanzania", "ivory coast", "côte d'ivoire", "cote d'ivoire",
    "mauritania", "cameroon", "chad", "sudan", "south sudan",
    "rwanda", "zambia", "zimbabwe", "somalia", "ethiopia",
    "ecowas", "aec", "energy chamber", "lamu",
)
NON_NIGERIA_AFRICAN_COUNTRIES = (
    "kenya", "angola", "mozambique", "south africa", "ivory coast",
    "côte d'ivoire", "cote d'ivoire", "zimbabwe", "ghana", "senegal",
    "namibia", "gabon", "congo", "uganda", "tanzania", "egypt", "libya", "algeria",
)


def _mentions(text: str, terms) -> bool:
    return any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I) for term in terms)


def _first_position(text: str, terms) -> int | None:
    positions = [m.start() for term in terms
                 if (m := re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I))]
    return min(positions) if positions else None


# Nigerian institutional providers publish Nigerian-subject releases by definition.
NIGERIA_DEFAULT_SOURCES = {"nuprc", "nnpc"}
_MULTILATERAL_JOINERS = re.compile(r"(?<!\w)(and|&|with|vs\.?|versus|between)(?!\w)", re.I)


def _nigeria_led(text: str, nigeria, competing) -> bool:
    """Nigeria is the headline's leading subject and is not paired with a counterparty.

    Foreign countries / OPEC that appear AFTER the Nigerian subject are treated as
    destinations, sources or context ("Nigeria crude exports to India"). A foreign
    or OPEC entity that comes first, or is joined by "and/with/vs/between", marks
    a multinational story that stays International.
    """
    ng_pos = _first_position(text, nigeria)
    other_pos = _first_position(text, competing)
    if other_pos is None:
        return True
    if ng_pos is None or other_pos < ng_pos:
        return False
    return not _MULTILATERAL_JOINERS.search(text[ng_pos:other_pos])


def classify_region(source_key: str, title: str, snippet: str | None = None) -> str:
    """Subject/location first; Nigerian institutional providers default to Nigeria.

    Titles outrank incidental excerpt mentions. Multiple African countries use
    Africa; cross-continent/unknown focus uses the broad International bucket.
    A Nigeria-led headline stays Nigeria despite a trailing foreign mention.
    """
    if source_key in NIGERIA_DEFAULT_SOURCES:
        return "nigeria"
    nigeria = NIGERIA_TERMS + ("dangote refinery", "cbn", "naira", "seplat", "oando")
    africa = tuple(t for t in AFRICA_TERMS if t not in {"aec", "energy chamber"})
    specific_africa = tuple(t for t in africa if t not in {"africa", "african", "ecowas"})
    foreign = ("united states", "u.s.", "usa", "united kingdom", "britain", "china",
               "india", "iran", "iraq", "saudi arabia", "russia", "europe", "brazil", "venezuela")
    multinational = foreign + ("opec", "opec+")
    if _mentions(title, ("global", "worldwide", "world oil", "international markets")) and not _mentions(title, nigeria + africa):
        return "international"
    for text in (title, snippet or ""):
        ng = _mentions(text, nigeria)
        af = _mentions(text, africa)
        outside = _mentions(text, foreign)
        if ng or af or outside:
            if ng and not _mentions(text, specific_africa):
                return "nigeria" if _nigeria_led(text, nigeria, multinational) else "international"
            if outside and (af or ng):
                return "international"
            if af:
                return "africa"
            if ng:
                return "nigeria"
            return "international"
    return "international"


def classify_source_type(source_key: str, metadata: dict | None = None) -> str:
    # Genre requires explicit source metadata, never guesses from headline words.
    if (metadata or {}).get("article_kind") in {"analysis", "commentary", "opinion"}:
        return "commentary_analysis"
    if source_key in {"eia", "opec", "nuprc"}:
        return "official_institutional_release"
    if source_key == "nnpc":
        return "official_company_release"
    if source_key == "african_energy_chamber":
        return "industry_organization_release"
    if source_key in {"cnn", "bbc", "aljazeera", "bloomberg", "nairametrics"}:
        return "independent_media_reporting"
    return "unclassified"


def classify_topic(source_key: str, title: str, snippet: str | None = None) -> str:
    text = f"{title} {snippet or ''}".lower()
    ordered = (
        ("opec_policy", ("opec", "quota", "production cut")),
        ("nigeria_upstream", ("nuprc", "upstream", "oil licensing", "marginal field")),
        ("inventories", ("inventory", "inventories", "stockpile", "storage")),
        ("refining", ("refinery", "refining", "refined product", "crack spread", "raffinerie")),
        ("downstream", ("fuel demand", "gasoline", "diesel", "jet fuel")),
        ("infrastructure", ("pipeline", "terminal", "port", "outage", "facility")),
        ("regulation", ("regulator", "regulation", "compliance", "sanction", "court order", "litigation")),
        ("geopolitics", ("war", "conflict", "shipping", "hormuz", "red sea")),
        ("demand", ("demand", "consumption", "economic growth")),
        ("production", ("production", "output", "drilling", "exploration", "fid")),
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
        reason = reject_reason(title=title, url=url, published_at=published_at, snippet=snippet)
        audit_candidate(reason, published_at)
        if reason is None:
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
        self.capture_depth = 0

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
            self.capture = None if self.block["published"] else "published"
        elif tag in {"p", "summary"}:
            self.capture = "snippet"
        elif tag == "div":
            css_class = attrs_dict.get("class", "")
            if "news-date" in css_class:
                self.capture = "published"
            elif "__desc" in css_class:
                self.capture = "title" if not self.block["title"].strip() else "snippet"

        if self.capture:
            self.capture_depth = self.block_depth

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VOID_TAGS:
            return
        if self.block is None:
            return
        if self.capture and self.block_depth == self.capture_depth:
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
        reason = reject_reason(title=title, url=url, published_at=published_at, snippet=snippet)
        audit_candidate(reason, published_at)
        if reason is None:
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


async def fetch_text(url: str, *, timeout: float = 20.0, retries: int = 0) -> str:
    """Existing providers make one request. One optional transient retry is opt-in.

    No caller enables retries until publisher limits are approved. Never retry
    access denials/challenges; obey long Retry-After by stopping, not polling.
    """
    if retries not in (0, 1):
        raise ValueError("News retries must be zero or one")
    audit = news_audit.get()
    for attempt in range(retries + 1):
        request = {"url": url, "attempted": True, "attempt": attempt + 1}
        if audit is not None:
            audit.setdefault("requests", []).append(request)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": "OilTradingRiskDashboard/1.0", "Cache-Control": "no-cache",
                })
                request.update(status=response.status_code, response_date=response.headers.get("date"),
                               age=response.headers.get("age"), cache=response.headers.get("x-cache"))
                response.raise_for_status()
                if "cf-chl-" in response.text or "<title>Just a moment" in response.text:
                    raise ValueError("Provider returned an access challenge, not news.")
                return response.text
        except Exception as exc:
            request["error"] = type(exc).__name__
            transient = isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))
            delay = 0.5
            if isinstance(exc, httpx.HTTPStatusError):
                transient = exc.response.status_code in {429, 502, 503, 504}
                retry_after = exc.response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        transient = False  # Date-form or unknown allowance: stop safely.
            if attempt >= retries or not transient or delay > 5:
                raise
            await anyio.sleep(delay)
