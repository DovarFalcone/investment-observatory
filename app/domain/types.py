from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class SecurityCandidate:
    symbol: str
    name: str
    asset_type: str
    exchange: Optional[str]
    currency: Optional[str]
    provider_symbol: str


@dataclass(frozen=True)
class PricePoint:
    observed_at: datetime
    price: Decimal
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    volume: Optional[int] = None
    currency: Optional[str] = None
    source_observed_at: Optional[datetime] = None
    observation_type: str = "close"


@dataclass(frozen=True)
class NewsArticle:
    url: str
    title: str
    publisher: Optional[str]
    published_at: Optional[datetime]
    excerpt: Optional[str]
    security_symbol: str
    source: str


@dataclass(frozen=True)
class ProviderResult:
    status: str
    source: str
    points: tuple[PricePoint, ...] = ()
    error: Optional[str] = None
