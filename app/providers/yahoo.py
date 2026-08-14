from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from app.config import settings
from app.domain.types import PricePoint, SecurityCandidate
from app.providers.base import MarketDataProvider


class YahooChartProvider(MarketDataProvider):
    """Low-frequency adapter around Yahoo's public chart/search endpoints.

    This is intentionally isolated because the endpoints are unofficial and may change.
    Do not use it for trading or high-frequency polling.
    """

    name = "yahoo_chart"
    base_url = "https://query1.finance.yahoo.com"

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )

    def search(self, query: str) -> list[SecurityCandidate]:
        query = query.strip()
        if not query:
            return []
        try:
            with self._client() as client:
                response = client.get("/v1/finance/search", params={"q": query, "quotesCount": 12})
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError):
            return []

        candidates: list[SecurityCandidate] = []
        for quote in payload.get("quotes", []):
            quote_type = str(quote.get("quoteType", "")).upper()
            asset_type = {"EQUITY": "stock", "ETF": "etf", "MUTUALFUND": "mutual_fund"}.get(
                quote_type, "other"
            )
            symbol = str(quote.get("symbol", "")).upper()
            if not symbol:
                continue
            candidates.append(
                SecurityCandidate(
                    symbol=symbol,
                    name=str(quote.get("longname") or quote.get("shortname") or symbol),
                    asset_type=asset_type,
                    exchange=quote.get("exchange") or quote.get("exchDisp"),
                    currency=quote.get("currency"),
                    provider_symbol=symbol,
                )
            )
        return candidates

    def history(self, symbol: str, start: datetime | None = None) -> list[PricePoint]:
        period_start = int((start or datetime.now(timezone.utc)).timestamp())
        period_end = int(datetime.now(timezone.utc).timestamp())
        if start is None:
            period_start = period_end - 366 * 86400
        params = {"period1": period_start, "period2": period_end, "interval": "1d", "events": "history"}
        try:
            with self._client() as client:
                response = client.get(f"/v8/finance/chart/{symbol}", params=params)
                response.raise_for_status()
                payload: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError):
            return []

        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            return []
        chart = result[0]
        timestamps = chart.get("timestamp") or []
        quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
        meta = chart.get("meta") or {}
        points: list[PricePoint] = []
        for index, timestamp in enumerate(timestamps):
            close = self._decimal_at(quote.get("close"), index)
            if close is None:
                continue
            observed_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            points.append(
                PricePoint(
                    observed_at=observed_at,
                    price=close,
                    open=self._decimal_at(quote.get("open"), index),
                    high=self._decimal_at(quote.get("high"), index),
                    low=self._decimal_at(quote.get("low"), index),
                    volume=self._int_at(quote.get("volume"), index),
                    currency=meta.get("currency"),
                    source_observed_at=observed_at,
                )
            )
        return points

    @staticmethod
    def _decimal_at(values: list[Any] | None, index: int) -> Decimal | None:
        if not values or index >= len(values) or values[index] is None:
            return None
        return Decimal(str(values[index]))

    @staticmethod
    def _int_at(values: list[Any] | None, index: int) -> int | None:
        if not values or index >= len(values) or values[index] is None:
            return None
        return int(values[index])
