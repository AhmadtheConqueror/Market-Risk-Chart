from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import logging
import re
from typing import Any

import httpx

from app.providers.macro.base import MacroDataProvider, MacroObservation, utc_now

logger = logging.getLogger(__name__)

MONTH_ABBR = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
    "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
    "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec"
}


class NUPRCProductionProvider(MacroDataProvider):
    """
    Provider for official Nigerian Upstream Petroleum Regulatory Commission (NUPRC)
    monthly oil production releases.

    Card requirement: STRICT CRUDE OIL PRODUCTION excluding condensate, monthly daily average, mbpd.
    Preserves combined crude + condensate in metadata.
    """

    SOURCE_NAME = "Nigerian Upstream Petroleum Regulatory Commission"
    API_NEWS_URL = "https://www.nuprc.gov.ng/api/news"
    ARTICLE_PAGE_URL = "https://www.nuprc.gov.ng/media/news/{article_id}"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return self.SOURCE_NAME

    def _get_http_client(self) -> httpx.Client:
        return httpx.Client(
            verify=False,
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OilTradingRiskDashboard/1.0"},
        )

    def parse_article_content(self, article_text: str, source_url: str, published_at: datetime | None = None) -> MacroObservation:
        """
        Extract strict crude-only production and metadata from official NUPRC release.
        Ensures strict crude oil production is used as the card metric, not combined crude + condensate.
        """
        # 1. Clean HTML tags and decode unicode escapes
        text = re.sub(r'<[^>]+>', ' ', article_text)
        text = text.replace('\\u0026nbsp;', ' ').replace('&nbsp;', ' ').replace('\\"', '"')
        text = re.sub(r'\s+', ' ', text)

        # 2. Extract strict crude production:
        # Expected official phrase:
        # "In strict crude oil terms (excluding condensate), Nigeria produced 1,500,190 barrels per day"
        strict_crude_bpd = None

        m_strict = re.search(
            r'(?:strict\s+crude\s+oil(?:\s+terms)?\s*(?:\(excluding\s+condensate\))?|crude\s+only|excluding\s+condensate)[^0-9]*?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{6,8})\s*(?:barrels(?:\s+per\s+day|\s*/\s*day)?|bpd)',
            text,
            re.I
        )
        if m_strict:
            strict_crude_bpd = int(m_strict.group(1).replace(",", "").strip())
        else:
            # Fallback search for context near "excluding condensate"
            m_alt = re.search(r'([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{6,8})\s*barrels\s*per\s*day[\s\S]*?(?:strict|excluding\s+condensate)', text, re.I)
            if m_alt:
                strict_crude_bpd = int(m_alt.group(1).replace(",", "").strip())

        if strict_crude_bpd is None:
            raise ValueError("NUPRC extraction failed: strict crude oil production (excluding condensate) not found")

        # 3. Extract combined crude + condensate if present
        # "Nigeria produced 1, 677,777 barrels of crude oil and condensate per day"
        combined_bpd = None
        m_comb = re.search(
            r'([0-9]{1,3}(?:,\s*[0-9]{3})+|[0-9]{6,8})\s*barrels\s*(?:of\s*)?crude(?:\s*oil)?\s*and\s*condensate',
            text,
            re.I
        )
        if m_comb:
            combined_bpd = int(re.sub(r'[\s,]', '', m_comb.group(1)))

        # 4. Extract reporting period (e.g. "month of August 2026" or "August 2026")
        period_match = re.search(
            r'(?:month\s+of\s+|in\s+)(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
            text,
            re.I
        )
        if not period_match:
            period_match = re.search(
                r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b',
                text,
                re.I
            )

        if not period_match:
            raise ValueError("NUPRC extraction failed: reporting period (month/year) not identified")

        month_name = period_match.group(1).lower()
        year_str = period_match.group(2)
        reporting_period = f"{MONTH_ABBR.get(month_name, month_name.capitalize()[:3])} {year_str}"

        # 5. Unit normalization: bpd to mbpd (million barrels per day)
        # e.g. 1,500,190 bpd -> 1.50019 mbpd
        strict_mbpd = Decimal(str(round(strict_crude_bpd / 1_000_000.0, 5)))

        # Sanity validation
        if strict_mbpd < Decimal("0.2") or strict_mbpd > Decimal("5.0"):
            raise ValueError(f"Sanity check failed for crude_oil_production: value {strict_mbpd} mbpd outside plausible range")

        metadata: dict[str, Any] = {
            "definition": "crude_only_excluding_condensate",
            "raw_value": strict_crude_bpd,
            "raw_unit": "bpd",
            "unit_conversion": "divided_by_1_000_000_to_mbpd",
            "source_publisher": "NUPRC",
        }

        if combined_bpd is not None:
            metadata["crude_plus_condensate_bpd"] = combined_bpd
            metadata["crude_plus_condensate_mbpd"] = float(round(combined_bpd / 1_000_000.0, 6))

        now = utc_now()
        return MacroObservation(
            indicator_key="crude_oil_production",
            display_name="Crude Oil Production",
            value=strict_mbpd,
            unit="mbpd",
            reporting_period=reporting_period,
            source=self.SOURCE_NAME,
            source_url=source_url,
            published_at=published_at,
            status="published",
            metadata_json=metadata,
            retrieved_at=now,
        )

    def discover_latest_article(self, client: httpx.Client) -> dict[str, Any]:
        """
        Dynamically discover the latest official monthly production article from NUPRC news API.
        """
        resp = client.get(self.API_NEWS_URL, params={"status": "published", "limit": 50})
        resp.raise_for_status()
        data = resp.json()

        articles = data.get("data", [])
        if not articles:
            raise ValueError("No published news articles returned by NUPRC API")

        # Find articles concerning monthly production
        candidates = []
        for art in articles:
            title = str(art.get("title") or "")
            excerpt = str(art.get("excerpt") or "")
            combined_txt = f"{title} {excerpt}".lower()

            if any(w in combined_txt for w in ["production", "opec quota", "crude oil and condensate", "strict crude"]):
                # Parse date
                pub_date = None
                date_str = art.get("createdAt") or art.get("publishedAt")
                if date_str:
                    try:
                        pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except ValueError:
                        pass

                candidates.append({
                    "id": art.get("_id"),
                    "title": title,
                    "published_at": pub_date,
                    "url": self.ARTICLE_PAGE_URL.format(article_id=art.get("_id")),
                })

        if not candidates:
            raise ValueError("No NUPRC articles concerning monthly crude oil production discovered")

        # Sort by published date descending (nulls last)
        candidates.sort(key=lambda c: (c["published_at"] is not None, c["published_at"]), reverse=True)
        return candidates[0]

    async def fetch_latest(self) -> list[MacroObservation]:
        """Fetch and extract latest strict crude production observation."""
        with self._get_http_client() as client:
            article_info = self.discover_latest_article(client)
            logger.info("Discovered latest NUPRC production article: %s (%s)", article_info["title"], article_info["url"])

            resp = client.get(article_info["url"])
            resp.raise_for_status()

            obs = self.parse_article_content(
                resp.text,
                source_url=article_info["url"],
                published_at=article_info["published_at"],
            )
            return [obs]
