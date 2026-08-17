from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import Base, ListItem, PriceObservation, Security, UserList
from app.services.market import latest_movements, movement
from app.worker import next_sleep_seconds, should_skip_market_sync


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


def test_latest_movements_uses_only_the_latest_two_observations() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        security = Security(canonical_symbol="ABC", name="Example", provider="test")
        db.add(security)
        db.flush()
        for day, price in ((1, "50"), (2, "60"), (3, "100"), (4, "110")):
            db.add(
                PriceObservation(
                    security=security,
                    observed_at=datetime(2026, 1, day, tzinfo=timezone.utc),
                    session_date=datetime(2026, 1, day, tzinfo=timezone.utc).date(),
                    price=Decimal(price),
                    source="test",
                )
            )
        db.commit()

        result = latest_movements(db, [security.id])

    assert result[security.id]["movement"] == {
        "price": Decimal("110.00000000"),
        "daily": Decimal("10.00000000000000000000000000"),
        "period": Decimal("120.00000000000000000000000000"),
    }


def test_weekend_sync_skips_only_after_expected_friday_close() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    saturday = datetime(2026, 1, 3, 12, tzinfo=timezone.utc)
    with Session(engine) as db:
        security = Security(canonical_symbol="ABC", name="Example", provider="test")
        watchlist = UserList(kind="watchlist", name="Watchlist")
        db.add_all([security, watchlist])
        db.flush()
        db.add(ListItem(user_list=watchlist, security=security, sort_order=1))
        db.add(
            PriceObservation(
                security=security,
                observed_at=datetime(2026, 1, 2, 21, tzinfo=timezone.utc),
                session_date=datetime(2026, 1, 2, tzinfo=timezone.utc).date(),
                price=Decimal("100"),
                source="test",
            )
        )
        db.commit()

        assert should_skip_market_sync(db, saturday) is True

        db.add(
            PriceObservation(
                security=security,
                observed_at=datetime(2025, 12, 31, 21, tzinfo=timezone.utc),
                session_date=datetime(2025, 12, 31, tzinfo=timezone.utc).date(),
                price=Decimal("99"),
                source="other",
            )
        )
        db.commit()
        assert should_skip_market_sync(db, datetime(2026, 1, 4, 12, tzinfo=timezone.utc)) is True

        missing_friday = Security(canonical_symbol="DEF", name="Missing Friday", provider="test")
        db.add(missing_friday)
        db.flush()
        db.add(ListItem(user_list=watchlist, security=missing_friday, sort_order=2))
        db.commit()
        assert should_skip_market_sync(db, saturday) is False


def test_sleep_jitter_stays_near_configured_interval(monkeypatch) -> None:
    monkeypatch.setattr("app.worker.settings.market_update_minutes", 60)
    monkeypatch.setattr("app.worker.random.uniform", lambda low, high: 60)
    assert next_sleep_seconds() == 3660


def test_price_points_filters_by_day_window() -> None:
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool

    from app.services.market import price_points

    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        security = Security(canonical_symbol="ABC", name="Example", provider="test")
        db.add(security)
        db.flush()
        db.add_all(
            [
                PriceObservation(
                    security_id=security.id,
                    observed_at=now - timedelta(days=40),
                    session_date=(now - timedelta(days=40)).date(),
                    price=Decimal("100"),
                    source="test",
                ),
                PriceObservation(
                    security_id=security.id,
                    observed_at=now - timedelta(days=5),
                    session_date=(now - timedelta(days=5)).date(),
                    price=Decimal("105"),
                    source="test",
                ),
                PriceObservation(
                    security_id=security.id,
                    observed_at=now,
                    session_date=now.date(),
                    price=Decimal("110"),
                    source="test",
                ),
            ]
        )
        db.commit()

        all_points = price_points(db, security.id, days=None)
        month_points = price_points(db, security.id, days=31)
        day_points = price_points(db, security.id, days=1)

    assert len(all_points) == 3
    assert len(month_points) == 2
    assert len(day_points) == 1
