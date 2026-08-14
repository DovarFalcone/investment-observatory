from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.providers.yahoo import YahooChartProvider


def test_yahoo_history_normalizes_chart_response(monkeypatch) -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1767225600],
                    "meta": {"currency": "USD"},
                    "indicators": {"quote": [{"close": [123.45], "volume": [10]}]},
                }
            ]
        }
    }

    def fake_get(self, path, **kwargs):
        request = httpx.Request("GET", "https://query1.finance.yahoo.com" + path)
        return httpx.Response(200, request=request, json=payload)

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    points = YahooChartProvider().history("ABC", datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert points[0].price == Decimal("123.45")
    assert points[0].currency == "USD"
