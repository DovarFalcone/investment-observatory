from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Investment Observatory"
    app_env: str = "development"
    app_secret_key: str = "change-me"
    database_url: str = "sqlite:///./data/observatory.db"
    app_timezone: str = "America/New_York"
    market_provider: str = "yahoo_chart"
    news_provider: str = "google_rss"
    news_feeds: str = ""
    market_update_minutes: int = 60
    news_update_hours: int = 4
    http_timeout_seconds: float = 20.0
    user_agent: str = "InvestmentObservatory/0.1 (self-hosted personal use)"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def data_dir(self) -> Path:
        path = Path("data")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def configured_news_feeds(self) -> list[str]:
        return [item.strip() for item in self.news_feeds.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
