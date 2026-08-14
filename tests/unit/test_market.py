from datetime import datetime, timezone
from decimal import Decimal

from app.db.models import PriceObservation, Security
from app.services.market import movement


def test_movement_returns_price_and_daily_change() -> None:
    security = Security(canonical_symbol="ABC", name="Example", provider="test")
    observations = [
        PriceObservation(
            security=security,
            observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            session_date=datetime(2026, 1, 1, tzinfo=timezone.utc).date(),
            price=Decimal("100"),
            source="test",
        ),
        PriceObservation(
            security=security,
            observed_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            session_date=datetime(2026, 1, 2, tzinfo=timezone.utc).date(),
            price=Decimal("105"),
            source="test",
        ),
    ]
    result = movement(observations)
    assert result["price"] == Decimal("105")
    assert result["daily"] == Decimal("5")
    assert result["period"] == Decimal("5")


def test_movement_does_not_invent_change() -> None:
    assert movement([]) == {"price": None, "daily": None, "period": None}
