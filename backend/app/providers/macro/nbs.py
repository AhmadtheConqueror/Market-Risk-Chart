from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import io
import logging
import re
from typing import Any
import zipfile

import httpx
import openpyxl

from app.providers.macro.base import MacroDataProvider, MacroObservation, utc_now

logger = logging.getLogger(__name__)

MONTH_ABBR = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
    "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
    "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec",
    "jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr",
    "jun": "Jun", "jul": "Jul", "aug": "Aug", "sep": "Sep",
    "oct": "Oct", "nov": "Nov", "dec": "Dec",
}


def normalize_month_period(raw_month: str, raw_year: str | int) -> str:
    cleaned_m = str(raw_month).strip().lower()
    m_abbr = MONTH_ABBR.get(cleaned_m, str(raw_month).strip().capitalize()[:3])
    return f"{m_abbr} {str(raw_year).strip()}"


class NBSMacroProvider(MacroDataProvider):
    """
    Provider for official Nigerian National Bureau of Statistics (NBS) macroeconomic reports:
    - Consumer Price Index (CPI): Headline Inflation, Food Inflation, Core Inflation
    - Gross Domestic Product (GDP): Real GDP Growth
    """

    CPI_CATALOG_URL = "https://microdata.nigerianstat.gov.ng/index.php/catalog/154/related-materials"
    GDP_CATALOG_URL = "https://microdata.nigerianstat.gov.ng/index.php/catalog/147/related-materials"
    SOURCE_NAME = "National Bureau of Statistics Nigeria"

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
            headers={"User-Agent": "OilTradingRiskDashboard/1.0 (MacroIngestionService)"},
        )

    def discover_latest_report(self, catalog_html: str, catalog_id: int) -> dict[str, Any]:
        """
        Dynamically discover the latest official report and download link from the NBS catalog page.
        Never hard-codes resource or download IDs like /1435.
        """
        # Match resource cards: <div class="colx resource..."> ... id="(\d+)" ... title="([^"]+)" ... href="([^"]+/download/\d+)"
        # Also extract Date: <td class="caption">Date</td>\s*<td>([^<]+)</td>
        cards = re.split(r'<div class="colx resource', catalog_html)
        if len(cards) <= 1:
            # Fallback search for download links
            d_links = re.findall(rf'href=[\"\'](https?://[^\s\"\']+/catalog/{catalog_id}/download/(\d+))[\"\']', catalog_html)
            if not d_links:
                raise ValueError(f"No official download links discovered for NBS catalog {catalog_id}")
            return {
                "download_url": d_links[0][0],
                "resource_id": d_links[0][1],
                "title": f"NBS Catalog {catalog_id} Report",
                "published_date": None,
            }

        candidates = []
        for card in cards[1:]:
            d_match = re.search(rf'href=[\"\'](https?://[^\s\"\']+/catalog/{catalog_id}/download/(\d+))[\"\']', card)
            if not d_match:
                continue
            download_url = d_match.group(1)
            resource_id = d_match.group(2)

            # Extract title
            title = None
            title_match = re.search(r'<span class="resource-info"[^>]*>(.*?)</span>', card, re.S)
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

            # Extract date
            date_val = None
            date_match = re.search(r'<td\s+class="caption"\s*>Date</td>\s*<td>([^<]+)</td>', card, re.I)
            if date_match:
                raw_d = date_match.group(1).strip()
                try:
                    date_val = datetime.strptime(raw_d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            candidates.append({
                "download_url": download_url,
                "resource_id": resource_id,
                "title": title or f"Report {resource_id}",
                "published_date": date_val,
            })

        if not candidates:
            raise ValueError(f"No valid resource cards with download links discovered for NBS catalog {catalog_id}")

        # Sort by published_date descending (nulls last)
        candidates.sort(key=lambda c: (c["published_date"] is not None, c["published_date"]), reverse=True)
        return candidates[0]

    def extract_xlsx_from_zip(self, zip_bytes: bytes) -> bytes:
        """Find and extract the primary Excel workbook from an NBS report ZIP archive."""
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            xlsx_names = [n for n in zf.namelist() if n.lower().endswith(".xlsx") and not n.startswith("__MACOSX")]
            if not xlsx_names:
                xls_names = [n for n in zf.namelist() if n.lower().endswith(".xls") and not n.startswith("__MACOSX")]
                if not xls_names:
                    raise ValueError(f"NBS ZIP archive contains no Excel workbooks. Files: {zf.namelist()}")
                return zf.read(xls_names[0])
            # Prefer files containing cpi or gdp in the name if multiple
            selected = xlsx_names[0]
            for n in xlsx_names:
                if any(w in n.lower() for w in ["cpi", "gdp", "report"]):
                    selected = n
                    break
            return zf.read(selected)

    def parse_cpi_workbook(self, xlsx_bytes: bytes, source_url: str, published_at: datetime | None = None) -> list[MacroObservation]:
        """
        Extract headline_inflation, food_inflation, and core_inflation from NBS CPI Excel workbook.
        Uses fail-closed label validation rather than static cell references.
        """
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)

        # Locate Table 1 composite consumer price index sheet
        table1_sheet = None
        for name in wb.sheetnames:
            if name.lower() == "table1" or "table 1" in name.lower():
                table1_sheet = wb[name]
                break
        if table1_sheet is None:
            # Fallback to first sheet
            table1_sheet = wb.worksheets[0]

        ws = table1_sheet

        # Header scan to identify columns:
        # Col blocks in Table 1:
        # Row 2 (or 1): Category headers: "All Items Index", "Food", "All Items less Farm Produce and Energy" (CORE)
        # Row 3 (or 2): Sub-headers: "Year-on change (%)" or "Year-on"
        headline_col = None
        food_col = None
        core_col = None

        current_category = None
        for c in range(1, ws.max_column + 1):
            h2 = ws.cell(2, c).value
            h1 = ws.cell(1, c).value
            h3 = ws.cell(3, c).value

            val_top = str(h2 if h2 is not None else h1 or "").strip()
            if val_top:
                current_category = val_top.lower()

            sub_val = str(h3 or "").strip().lower()
            if "year-on" in sub_val or "year on" in sub_val or "yoy" in sub_val:
                if current_category:
                    if "all items index" in current_category or current_category == "all items":
                        if headline_col is None:
                            headline_col = c
                    elif "food" in current_category and "non-alcoholic" not in current_category and "imported" not in current_category:
                        if food_col is None:
                            food_col = c
                    elif "core" in current_category or "all items less farm produce and energy" in current_category:
                        if core_col is None:
                            core_col = c

        if headline_col is None or food_col is None or core_col is None:
            # Try searching all headers row 1 to 5
            for c in range(1, ws.max_column + 1):
                col_text = " ".join(str(ws.cell(r, c).value or "") for r in range(1, 5)).lower()
                if ("year-on" in col_text or "year on" in col_text) and "all items index" in col_text and headline_col is None:
                    headline_col = c
                elif ("year-on" in col_text or "year on" in col_text) and "food" in col_text and food_col is None:
                    food_col = c
                elif ("year-on" in col_text or "year on" in col_text) and "core" in col_text and core_col is None:
                    core_col = c

        # Fail-closed check
        missing = []
        if headline_col is None:
            missing.append("headline_inflation (All Items Index YoY)")
        if food_col is None:
            missing.append("food_inflation (Food Index YoY)")
        if core_col is None:
            missing.append("core_inflation (Core Index YoY)")

        if missing:
            raise ValueError(f"NBS CPI extraction failed: expected labels not found: {', '.join(missing)}")

        # Find the latest observation row (last row with non-empty year-on values)
        latest_row = None
        for r in range(ws.max_row, 3, -1):
            h_val = ws.cell(r, headline_col).value
            f_val = ws.cell(r, food_col).value
            c_val = ws.cell(r, core_col).value
            if isinstance(h_val, (int, float, Decimal)) and isinstance(f_val, (int, float, Decimal)) and isinstance(c_val, (int, float, Decimal)):
                latest_row = r
                break

        if latest_row is None:
            raise ValueError("NBS CPI extraction failed: no valid numeric rows found for inflation rates")

        # Extract reporting period (year and month)
        raw_year = None
        raw_month = None

        # Check col 2 for month
        for c in [2, 1]:
            val = ws.cell(latest_row, c).value
            if val and str(val).strip().lower() in MONTH_ABBR:
                raw_month = str(val).strip()
                break

        # Check for year in col 1 or walk upwards in col 1
        for r in range(latest_row, 3, -1):
            y_cand = ws.cell(r, 1).value
            if isinstance(y_cand, int) and 2000 <= y_cand <= 2100:
                raw_year = y_cand
                break
            elif str(y_cand).strip().isdigit() and 2000 <= int(str(y_cand).strip()) <= 2100:
                raw_year = int(str(y_cand).strip())
                break

        # Check date cell in row (sometimes col 23 has full timestamp like 2026-08-01)
        for c in range(1, ws.max_column + 1):
            cell_val = ws.cell(latest_row, c).value
            if isinstance(cell_val, datetime):
                raw_year = raw_year or cell_val.year
                raw_month = raw_month or cell_val.strftime("%B")
                break

        if not raw_year or not raw_month:
            raise ValueError(f"NBS CPI extraction failed: could not identify reporting period for row {latest_row}")

        reporting_period = normalize_month_period(raw_month, raw_year)

        # Extract decimal values
        headline_val = Decimal(str(round(float(ws.cell(latest_row, headline_col).value), 4)))
        food_val = Decimal(str(round(float(ws.cell(latest_row, food_col).value), 4)))
        core_val = Decimal(str(round(float(ws.cell(latest_row, core_col).value), 4)))

        # Sanity validation
        for name, val in [("headline_inflation", headline_val), ("food_inflation", food_val), ("core_inflation", core_val)]:
            if val < Decimal("-50") or val > Decimal("500"):
                raise ValueError(f"Sanity check failed for {name}: value {val}% out of plausible range")

        now = utc_now()
        metadata_base = {
            "workbook_sheet": ws.title,
            "row_index": latest_row,
            "national_annual_yoy": True,
            "official_collection": "Consumer Price Index and Inflation",
        }

        return [
            MacroObservation(
                indicator_key="headline_inflation",
                display_name="Headline Inflation",
                value=headline_val,
                unit="%",
                reporting_period=reporting_period,
                source=self.SOURCE_NAME,
                source_url=source_url,
                published_at=published_at,
                status="published",
                metadata_json=metadata_base,
                retrieved_at=now,
            ),
            MacroObservation(
                indicator_key="food_inflation",
                display_name="Food Inflation",
                value=food_val,
                unit="%",
                reporting_period=reporting_period,
                source=self.SOURCE_NAME,
                source_url=source_url,
                published_at=published_at,
                status="published",
                metadata_json=metadata_base,
                retrieved_at=now,
            ),
            MacroObservation(
                indicator_key="core_inflation",
                display_name="Core Inflation",
                value=core_val,
                unit="%",
                reporting_period=reporting_period,
                source=self.SOURCE_NAME,
                source_url=source_url,
                published_at=published_at,
                status="published",
                metadata_json=metadata_base,
                retrieved_at=now,
            ),
        ]

    def parse_gdp_workbook(self, xlsx_bytes: bytes, source_url: str, published_at: datetime | None = None) -> list[MacroObservation]:
        """
        Extract real_gdp_growth (Nigeria total real GDP growth YoY %) from NBS GDP Excel workbook.
        Ensures strict real GDP total basic prices is extracted, avoiding nominal or sector subsets.
        """
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)

        # Locate real GDP growth rate sheet
        target_sheet = None
        for name in wb.sheetnames:
            clean_name = name.lower()
            if "real gdp growth rate" in clean_name or "real gdp" in clean_name:
                target_sheet = wb[name]
                break

        if target_sheet is None:
            raise ValueError(f"NBS GDP extraction failed: real gdp growth sheet not found in workbook sheets {wb.sheetnames}")

        ws = target_sheet

        # Identify Total GDP row:
        # Looking for label containing "GDP at" and "constant price" or "Total GDP" or "Gross Domestic Product"
        # Must not contain nominal, oil, non-oil
        total_gdp_row = None
        row_label = None

        for r in range(1, ws.max_row + 1):
            c1_val = str(ws.cell(r, 1).value or "").strip()
            c2_val = str(ws.cell(r, 2).value or "").strip()
            label = c1_val or c2_val
            label_lower = label.lower()

            if ("gdp at" in label_lower and "constant price" in label_lower) or label_lower == "total gdp":
                if "nominal" not in label_lower and "oil" not in label_lower:
                    total_gdp_row = r
                    row_label = label
                    break

        if total_gdp_row is None:
            # Fallback search for any row labeled "Total" at the bottom of the table
            for r in range(ws.max_row, 30, -1):
                label = str(ws.cell(r, 1).value or "").strip()
                if "constant" in label.lower() and "gdp" in label.lower():
                    total_gdp_row = r
                    row_label = label
                    break

        if total_gdp_row is None:
            raise ValueError("NBS GDP extraction failed: total real GDP row label not found")

        # Scan columns for quarters and years
        # NBS GDP format has Year in Row 6 (e.g. 2024, 2025, 2026) and Quarter in Row 7 (Q1, Q2, Q3, Q4)
        latest_col = None
        latest_quarter = None
        latest_year = None
        latest_val = None

        current_year = None
        for c in range(2, ws.max_column + 1):
            # Check row 6 and row 7
            y_val = ws.cell(6, c).value
            q_val = ws.cell(7, c).value

            # Check if year is defined in row 6
            if y_val is not None:
                cleaned_y = str(y_val).strip()
                if cleaned_y.isdigit() and 2000 <= int(cleaned_y) <= 2100:
                    current_year = int(cleaned_y)
                elif re.match(r'^Q[1-4]$', cleaned_y, re.I):
                    # Sometimes quarter was placed in row 6
                    q_val = cleaned_y

            quarter_str = None
            if q_val is not None:
                m = re.search(r'(Q[1-4])', str(q_val), re.I)
                if m:
                    quarter_str = m.group(1).upper()

            # Check value in total_gdp_row
            val = ws.cell(total_gdp_row, c).value
            if isinstance(val, (int, float, Decimal)) and quarter_str:
                latest_col = c
                latest_quarter = quarter_str
                latest_year = current_year
                latest_val = val

        if latest_col is None or latest_val is None or not latest_quarter:
            raise ValueError("NBS GDP extraction failed: could not locate latest quarter with valid real GDP value")

        reporting_period = f"{latest_quarter} {latest_year}" if latest_year else latest_quarter
        gdp_val = Decimal(str(round(float(latest_val), 4)))

        # Sanity check
        if gdp_val < Decimal("-30") or gdp_val > Decimal("50"):
            raise ValueError(f"Sanity check failed for real_gdp_growth: value {gdp_val}% out of plausible range")

        now = utc_now()
        metadata = {
            "workbook_sheet": ws.title,
            "row_label": row_label,
            "row_index": total_gdp_row,
            "column_index": latest_col,
            "definition": "total_real_gdp_growth_yoy",
            "official_collection": "Gross Domestic Product",
        }

        return [
            MacroObservation(
                indicator_key="real_gdp_growth",
                display_name="Real GDP Growth",
                value=gdp_val,
                unit="%",
                reporting_period=reporting_period,
                source=self.SOURCE_NAME,
                source_url=source_url,
                published_at=published_at,
                status="published",
                metadata_json=metadata,
                retrieved_at=now,
            )
        ]

    async def fetch_cpi(self) -> list[MacroObservation]:
        """Fetch and extract latest CPI indicators from NBS."""
        with self._get_http_client() as client:
            resp = client.get(self.CPI_CATALOG_URL)
            resp.raise_for_status()
            report = self.discover_latest_report(resp.text, catalog_id=154)

            logger.info("Discovered latest NBS CPI report: %s (%s)", report["title"], report["download_url"])
            zip_resp = client.get(report["download_url"])
            zip_resp.raise_for_status()

            xlsx_bytes = self.extract_xlsx_from_zip(zip_resp.content)
            return self.parse_cpi_workbook(
                xlsx_bytes,
                source_url=report["download_url"],
                published_at=report["published_date"],
            )

    async def fetch_gdp(self) -> list[MacroObservation]:
        """Fetch and extract latest GDP indicator from NBS."""
        with self._get_http_client() as client:
            resp = client.get(self.GDP_CATALOG_URL)
            resp.raise_for_status()
            report = self.discover_latest_report(resp.text, catalog_id=147)

            logger.info("Discovered latest NBS GDP report: %s (%s)", report["title"], report["download_url"])
            zip_resp = client.get(report["download_url"])
            zip_resp.raise_for_status()

            xlsx_bytes = self.extract_xlsx_from_zip(zip_resp.content)
            return self.parse_gdp_workbook(
                xlsx_bytes,
                source_url=report["download_url"],
                published_at=report["published_date"],
            )

    async def fetch_latest(self) -> list[MacroObservation]:
        """Fetch all 4 NBS indicators: headline_inflation, food_inflation, core_inflation, real_gdp_growth."""
        observations = []
        try:
            observations.extend(await self.fetch_cpi())
        except Exception as e:
            logger.error("Failed to fetch NBS CPI: %s", e)
            raise

        try:
            observations.extend(await self.fetch_gdp())
        except Exception as e:
            logger.error("Failed to fetch NBS GDP: %s", e)
            raise

        return observations
