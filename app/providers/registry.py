from functools import lru_cache

from app.config import settings
from app.providers.base import MarketDataProvider, NewsProvider
from app.providers.google_rss import GoogleRssNewsProvider
from app.providers.yahoo import YahooChartProvider


@lru_cache
def market_provider() -> MarketDataProvider:
    if settings.market_provider == "yahoo_chart":
        return YahooChartProvider()
    raise ValueError(f"Unsupported market provider: {settings.market_provider}")


@lru_cache
def news_provider() -> NewsProvider:
    if settings.news_provider == "google_rss":
        return GoogleRssNewsProvider()
    raise ValueError(f"Unsupported news provider: {settings.news_provider}")
