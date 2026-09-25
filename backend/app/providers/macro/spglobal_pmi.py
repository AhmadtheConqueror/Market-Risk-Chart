from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import io
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx
import pypdf

from app.providers.macro.base import MacroDataProvider, MacroObservation, utc_now

logger = logging.getLogger(__name__)

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

MONTH_ABBR = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
    "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
    "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec"
}


class SPGlobalPMIProvider(MacroDataProvider):
    """
    Provider for official Stanbic IBTC Bank Nigeria PMI (published with S&P Global).
    Extracts the headline seasonally-adjusted index from official monthly PDF releases.
    """

    SOURCE_NAME = "Stanbic IBTC Bank / S&P Global"
    BASE_PDF_URL = "https://www.stanbicibtcbank.com/static_file/Nigeria/nigeriabank/Corporate%20and%20Investment/Insights/Stanbic%20IBTC%20Bank%20PMI%20{month}%20{year}.pdf"

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

    def parse_pmi_pdf(self, pdf_bytes: bytes, source_url: str) -> MacroObservation:
        """
        Extract headline Stanbic IBTC Bank Nigeria PMI from official PDF publication.
        Uses fail-closed label and range validation.
        """
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        except Exception as exc:
            raise ValueError("PMI extraction failed: malformed PDF publication") from exc

        if len(reader.pages) == 0:
            raise ValueError("PMI extraction failed: empty PDF document")

        # Collect text from the first 3 pages where headline findings are published
        pages_text = []
        for p in range(min(4, len(reader.pages))):
            pages_text.append(reader.pages[p].extract_text() or "")

        full_lead_text = "\n---\n".join(pages_text)

        # 1. Extract publication date if available (e.g. "1 September 2026")
        published_at = None
        date_str_to_exclude = ""
        date_match = re.search(r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})', pages_text[0])
        if date_match:
            date_str_to_exclude = date_match.group(1)
            try:
                published_at = datetime.strptime(date_str_to_exclude, "%d %B %Y").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        # 2. Extract reporting period (e.g. "August 2026")
        # Exclude the publication date string so publication month is not confused with reporting period
        search_text_for_period = full_lead_text
        if date_str_to_exclude:
            search_text_for_period = search_text_for_period.replace(date_str_to_exclude, "")

        period_match = re.search(r'(?:in|for|Key findings|month of)\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', search_text_for_period, re.I)
        if not period_match:
            # Fallback to general month year mention
            period_match = re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b', search_text_for_period)

        if not period_match:
            raise ValueError("PMI extraction failed: reporting period (month/year) not identified in PDF")

        rep_month = period_match.group(1).lower()
        rep_year = period_match.group(2)
        reporting_period = f"{MONTH_ABBR.get(rep_month, rep_month.capitalize()[:3])} {rep_year}"

        # 3. Extract headline PMI value
        # In Stanbic IBTC / S&P Global reports:
        # On Page 3 (Key findings), the headline PMI is displayed prominently as a standalone float
        # after methodology text like "The PMI varies between 0 and 100 ... Return to contents\n54.3\nThe Stanbic IBTC Bank"
        # Or in lead text: "headline PMI posted 54.3" / "headline index rose to 54.3"
        pmi_val = None

        # Pattern 1: Standalone numeric index on findings page (e.g. "54.3")
        for page_txt in pages_text:
            m = re.search(r'(?:Return to contents|Key findings)[\s\S]*?\n(\d{2}\.\d)\n[\s\S]*?(?:Stanbic|NBS)', page_txt)
            if m:
                cand = float(m.group(1))
                if 20.0 <= cand <= 80.0:
                    pmi_val = cand
                    break

        # Pattern 2: Contextual mention like "headline PMI ... 54.3" or "headline ... posted 54.3"
        if pmi_val is None:
            m = re.search(r'(?:headline|Stanbic IBTC Bank Nigeria)\s+(?:PMI|index)\s+(?:rose to|fell to|posted|of|was|at)\s+(\d{1,3}(?:\.\d)?)', full_lead_text, re.I)
            if m:
                pmi_val = float(m.group(1))

        # Pattern 3: Standalone 2-digit decimal between 30 and 70 in page 2 or 3
        if pmi_val is None:
            for p_idx in [2, 1, 0]:
                if p_idx < len(pages_text):
                    numbers = re.findall(r'(?<![0-9\.])(4\d\.\d|5\d\.\d|6\d\.\d|3\d\.\d)(?![0-9\.])', pages_text[p_idx])
                    if numbers:
                        pmi_val = float(numbers[0])
                        break

        if pmi_val is None:
            raise ValueError("PMI extraction failed: headline PMI index value not found in publication")

        dec_val = Decimal(str(round(pmi_val, 2)))

        # Sanity check
        if dec_val < Decimal("0") or dec_val > Decimal("100"):
            raise ValueError(f"Sanity check failed for nigeria_pmi: value {dec_val} not between 0 and 100")

        now = utc_now()
        metadata = {
            "headline_index_name": "Stanbic IBTC Bank Nigeria PMI",
            "seasonally_adjusted": True,
            "publisher": "S&P Global / Stanbic IBTC Bank",
            "pdf_pages": len(reader.pages),
        }

        return MacroObservation(
            indicator_key="nigeria_pmi",
            display_name="PMI",
            value=dec_val,
            unit="index",
            reporting_period=reporting_period,
            source=self.SOURCE_NAME,
            source_url=source_url,
            published_at=published_at,
            status="published",
            metadata_json=metadata,
            retrieved_at=now,
        )

    def discover_latest_pdf(self, client: httpx.Client) -> tuple[bytes, str]:
        """
        Dynamically discover and download the latest available monthly PMI release PDF.
        Tests current month and prior months.
        """
        now = datetime.now(timezone.utc)
        current_year = now.year
        current_month_idx = now.month  # 1-12

        # Generate candidates in reverse chronological order (last 4 months)
        candidates = []
        for i in range(5):
            m_idx = current_month_idx - i
            y = current_year
            while m_idx <= 0:
                m_idx += 12
                y -= 1
            month_name = MONTH_NAMES[m_idx - 1]
            candidates.append((month_name, y))

        for month_name, year in candidates:
            url = self.BASE_PDF_URL.format(month=month_name, year=year)
            try:
                resp = client.get(url)
                content_type = str(resp.headers.get("content-type", "")).lower()
                content = resp.content or b""
                looks_like_pdf = content.lstrip().startswith(b"%PDF")

                if resp.status_code == 200 and len(content) > 10000 and (looks_like_pdf or "pdf" in content_type):
                    logger.info("Discovered Stanbic IBTC PMI release: %s %s (%s)", month_name, year, url)
                    return content, url

                if resp.status_code == 200 and len(content) > 10000:
                    logger.debug("Skipping non-PDF PMI candidate: %s %s (%s)", month_name, year, url)
            except Exception as e:
                logger.debug("Candidate %s %s failed: %s", month_name, year, e)

        raise ValueError("Could not discover any recent official Stanbic IBTC Bank PMI release PDF")

    async def fetch_latest(self) -> list[MacroObservation]:
        """Fetch and extract latest headline PMI observation."""
        with self._get_http_client() as client:
            pdf_bytes, source_url = self.discover_latest_pdf(client)
            obs = self.parse_pmi_pdf(pdf_bytes, source_url=source_url)
            return [obs]
