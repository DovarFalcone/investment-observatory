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


def derived_holding_values(
    shares: Decimal | None,
    average_cost: Decimal | None,
    latest_price: Decimal | None,
    price_currency: str | None,
    cost_currency: str | None,
) -> dict[str, object]:
    """Derived holding numbers, or an explicit reason why they cannot be computed.

    Nothing here is inferred: if any required input is missing, or currencies do
    not match, the result explains why instead of presenting a misleading value.
    """
    if shares is None or shares <= 0:
        return {"status": "missing_shares"}
    if average_cost is None or average_cost < 0:
        return {"status": "missing_cost"}
    if latest_price is None:
        return {"status": "missing_price"}
    if cost_currency and price_currency and cost_currency != price_currency:
        return {"status": "currency_mismatch"}

    currency = cost_currency or price_currency
    cost_basis = shares * average_cost
    market_value = shares * latest_price
    unrealized_amount = market_value - cost_basis
    unrealized_percent = percent_change(market_value, cost_basis)
    return {
        "status": "ok",
        "currency": currency,
        "cost_basis": cost_basis,
        "market_value": market_value,
        "unrealized_amount": unrealized_amount,
        "unrealized_percent": unrealized_percent,
    }
