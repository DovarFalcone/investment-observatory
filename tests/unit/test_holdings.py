from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import Base, HoldingAnnotation, ListItem, Security, UserList
from app.domain.calculations import derived_holding_values
from app.services.holdings import context_view, save_holding_context


def test_derived_holding_values_math_and_currency_guard() -> None:
    result = derived_holding_values(
        Decimal("10"), Decimal("100"), Decimal("110"), "USD", "USD"
    )
    assert result["status"] == "ok"
    assert result["cost_basis"] == Decimal("1000")
    assert result["market_value"] == Decimal("1100")
    assert result["unrealized_amount"] == Decimal("100")
    assert result["unrealized_percent"] == Decimal("10")

    mismatch = derived_holding_values(
        Decimal("10"), Decimal("100"), Decimal("110"), "USD", "EUR"
    )
    assert mismatch["status"] == "currency_mismatch"

    missing = derived_holding_values(None, Decimal("100"), Decimal("110"), "USD", "USD")
    assert missing["status"] == "missing_shares"


def test_save_holding_context_creates_updates_and_clears() -> None:
    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        security = Security(canonical_symbol="ABC", name="Example", provider="test")
        user_list = UserList(kind="holdings", name="Holdings")
        db.add_all([security, user_list])
        db.flush()
        item = ListItem(user_list=user_list, security=security, sort_order=1)
        db.add(item)
        db.commit()

        annotation = save_holding_context(
            db, item, Decimal("12.5"), Decimal("178.40"), "USD", "Core position"
        )
        assert annotation is not None
        assert annotation.shares == Decimal("12.5")

        view = context_view(annotation, Decimal("200"), "USD")
        assert view["derived"]["status"] == "ok"
        assert view["derived"]["market_value"] == Decimal("2500.0000")

        save_holding_context(db, item, None, None, "", "")
        assert db.get(HoldingAnnotation, annotation.id) is None


def test_save_holding_context_rejects_negative_values() -> None:
    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        security = Security(canonical_symbol="ABC", name="Example", provider="test")
        user_list = UserList(kind="holdings", name="Holdings")
        db.add_all([security, user_list])
        db.flush()
        item = ListItem(user_list=user_list, security=security, sort_order=1)
        db.add(item)
        db.commit()

        try:
            save_holding_context(db, item, Decimal("-1"), None, "", "")
        except ValueError as exc:
            assert "negative" in str(exc)
        else:
            raise AssertionError("expected ValueError")


def test_context_view_without_annotation() -> None:
    assert context_view(None, Decimal("200"), "USD")["derived"]["status"] == "no_annotation"


def test_holding_context_flows_into_weekly_review_payload() -> None:
    from app.services.weekly_review import weekly_review_data

    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        security = Security(canonical_symbol="ABC", name="Example", provider="test")
        user_list = UserList(kind="holdings", name="Holdings")
        db.add_all([security, user_list])
        db.flush()
        item = ListItem(user_list=user_list, security=security, sort_order=1)
        db.add(item)
        db.commit()
        save_holding_context(
            db, item, Decimal("10"), Decimal("100"), "USD", "note"
        )

        payload = weekly_review_data(db, date(2026, 8, 10), date(2026, 8, 16))

    holdings = cast(list[dict[str, object]], payload["holdings"])
    context = cast(dict[str, object], holdings[0]["holding_context"])
    assert context["shares"] == "10.00000000"
    assert context["average_cost"] == "100.00000000"
    assert context["note"] == "note"
