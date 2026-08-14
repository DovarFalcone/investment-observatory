from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from app.domain.types import PricePoint


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def percent_change(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous * Decimal("100")


def latest_and_previous(points: Iterable[PricePoint]) -> tuple[PricePoint | None, PricePoint | None]:
    ordered = sorted(points, key=lambda point: point.observed_at)
    if not ordered:
        return None, None
    return ordered[-1], ordered[-2] if len(ordered) > 1 else None
