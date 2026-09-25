from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Sequence

import httpx

from app.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)


class OilPriceAPIError(Exception):
    """Custom exception for OilPriceAPI communication or parsing errors."""

    def __init__(self, message: str, status_code: int | None = None, response_body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class OilPriceAPIProvider(MarketDataProvider):
    """Client for OilPriceAPI market data service (https://api.oilpriceapi.com/v1).

    Adheres to MarketDataProvider abstraction.
    Does not convert units during ingestion: preserves raw provider values, units, and timestamps.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 12.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=(base_url or "https://api.oilpriceapi.com/v1").rstrip("/"),
        )
        self.timeout = timeout
        self._external_client = client

    def _get_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise OilPriceAPIError("OilPriceAPI key is not configured.", status_code=401)
        return {
            "Authorization": f"Token {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "DailyOilRiskDashboard/1.0",
        }

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        """Performs authenticated HTTP request with transient retry and no secret logging."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                if self._external_client is not None:
                    response = await self._external_client.get(
                        url, params=params, headers=headers, timeout=self.timeout
                    )
                else:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.get(url, params=params, headers=headers)

                # Check HTTP status
                if response.status_code >= 400:
                    try:
                        err_json = response.json()
                    except Exception:
                        err_json = response.text
                    err_msg = f"OilPriceAPI request to '{endpoint}' failed with status {response.status_code}."
                    logger.warning(
                        "OilPriceAPI error: %s (status=%d)",
                        endpoint,
                        response.status_code,
                    )
                    # Transient server error retry
                    if response.status_code in (502, 503, 504) and attempt < max_retries:
                        continue
                    raise OilPriceAPIError(err_msg, status_code=response.status_code, response_body=err_json)

                try:
                    payload = response.json()
                except Exception as exc:
                    raise OilPriceAPIError(
                        f"Failed to parse JSON response from '{endpoint}': {exc}",
                        status_code=response.status_code,
                    ) from exc

                return payload

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < max_retries:
                    continue
                raise OilPriceAPIError(
                    f"Network error connecting to OilPriceAPI '{endpoint}': {exc}"
                ) from exc
            except OilPriceAPIError:
                raise
            except Exception as exc:
                raise OilPriceAPIError(f"Unexpected error calling OilPriceAPI '{endpoint}': {exc}") from exc

        raise OilPriceAPIError(f"Request failed after retries: {last_error}")

    def normalize_price_item(self, item: dict[str, Any], retrieved_at: datetime) -> dict[str, Any]:
        """Normalizes a raw OilPriceAPI price record without modifying raw values or units."""
        code = item.get("code") or item.get("commodity_code") or ""
        raw_price = item.get("price") or item.get("value")
        currency = item.get("currency") or "USD"
        raw_unit = item.get("unit") or f"{currency}/bbl"

        # Timestamp parsing
        ts_val = item.get("created_at") or item.get("timestamp") or item.get("time") or item.get("updated_at")
        source_ts: datetime | None = None
        assessment_date_str: str | None = None

        if isinstance(ts_val, (int, float)):
            # Epoch timestamp
            source_ts = datetime.fromtimestamp(ts_val, tz=timezone.utc)
            assessment_date_str = source_ts.date().isoformat()
        elif isinstance(ts_val, str) and ts_val.strip():
            try:
                clean_ts = ts_val.strip().replace("Z", "+00:00")
                source_ts = datetime.fromisoformat(clean_ts)
                if source_ts.tzinfo is None:
                    source_ts = source_ts.replace(tzinfo=timezone.utc)
                assessment_date_str = source_ts.date().isoformat()
            except ValueError:
                assessment_date_str = ts_val.strip()[:10]
        else:
            source_ts = retrieved_at
            assessment_date_str = retrieved_at.date().isoformat()

        try:
            val_float = float(raw_price) if raw_price is not None else None
        except (ValueError, TypeError):
            val_float = None

        return {
            "provider": "oilpriceapi",
            "provider_symbol": code,
            "raw_value": val_float,
            "raw_unit": raw_unit,
            "currency": currency,
            "assessment_date": assessment_date_str,
            "source_timestamp": source_ts,
            "retrieved_at": retrieved_at,
            "raw_payload": item,
        }

    async def get_commodities(self) -> list[dict[str, Any]]:
        """Retrieves list of all available commodities/symbols from /v1/commodities."""
        payload = await self._request("commodities")
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("commodities") or [data]
        return []

    async def get_latest(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        """Retrieves latest prices for specified symbols, supporting both single and multi-code query."""
        if not symbols:
            return []

        retrieved_at = datetime.now(timezone.utc)
        results: list[dict[str, Any]] = []

        # Join symbols into comma-separated string for multi-code request
        by_code_param = ",".join(symbols)
        payload = await self._request("prices/latest", params={"by_code": by_code_param})

        data = payload.get("data")
        raw_items: list[dict[str, Any]] = []

        if isinstance(data, list):
            raw_items = data
        elif isinstance(data, dict):
            # Check if it has a list inside or is a single object
            if "prices" in data and isinstance(data["prices"], list):
                raw_items = data["prices"]
            else:
                raw_items = [data]

        for item in raw_items:
            if isinstance(item, dict):
                norm = self.normalize_price_item(item, retrieved_at)
                results.append(norm)

        return results

    async def get_history(self, symbol: str, days: int = 90, endpoint: str = "past_month") -> list[dict[str, Any]]:
        """Retrieves historical prices from /v1/prices/{endpoint}?by_code=...

        Common endpoints on OilPriceAPI: 'past_week', 'past_month', 'past_year'.
        """
        retrieved_at = datetime.now(timezone.utc)
        payload = await self._request(f"prices/{endpoint}", params={"by_code": symbol})

        data = payload.get("data")
        raw_items: list[dict[str, Any]] = []

        if isinstance(data, list):
            raw_items = data
        elif isinstance(data, dict):
            if "prices" in data and isinstance(data["prices"], list):
                raw_items = data["prices"]
            else:
                raw_items = [data]

        results: list[dict[str, Any]] = []
        for item in raw_items:
            if isinstance(item, dict):
                norm = self.normalize_price_item(item, retrieved_at)
                if norm["raw_value"] is not None and norm["assessment_date"]:
                    results.append(norm)

        # Sort ascending by assessment_date
        results.sort(key=lambda x: str(x["assessment_date"]))
        return results
