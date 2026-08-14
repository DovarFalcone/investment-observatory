from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.types import NewsArticle, PricePoint, SecurityCandidate


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def search(self, query: str) -> list[SecurityCandidate]: ...

    @abstractmethod
    def history(self, symbol: str, start: datetime | None = None) -> list[PricePoint]: ...


class NewsProvider(ABC):
    name: str

    @abstractmethod
    def recent(self, symbol: str, name: str) -> list[NewsArticle]: ...
