from datetime import date, datetime, timezone
from decimal import Decimal
from typing import cast

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import (
    Base,
    ListItem,
    NewsItem,
    NewsSecurityLink,
    PriceObservation,
    Security,
    UserList,
)
from app.services.weekly_review import previous_calendar_week, weekly_review_data


def test_previous_calendar_week_returns_monday_to_sunday() -> None:
    assert previous_calendar_week(date(2026, 8, 19)) == (date(2026, 8, 10), date(2026, 8, 16))


def test_weekly_review_data_prioritizes_holdings_and_groups_news() -> None:
    engine = create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        holdings = UserList(kind="holdings", name="Holdings")
        watchlist = UserList(kind="watchlist", name="Watchlist")
        owned = Security(canonical_symbol="OWN", name="Owned Security", provider="test")
        watched = Security(canonical_symbol="WATCH", name="Watched Security", provider="test")
        db.add_all([holdings, watchlist, owned, watched])
        db.flush()
        db.add_all(
            [
                ListItem(user_list=holdings, security=owned, sort_order=1),
                ListItem(user_list=watchlist, security=watched, sort_order=1),
            ]
        )
        db.flush()
        db.add_all(
            [
                PriceObservation(
                    security=owned,
                    observed_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
                    session_date=date(2026, 8, 10),
                    price=Decimal("100"),
                    source="test",
                ),
                PriceObservation(
                    security=owned,
                    observed_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
                    session_date=date(2026, 8, 14),
                    price=Decimal("110"),
                    source="test",
                ),
            ]
        )
        first = NewsItem(
            canonical_url="https://example.test/one",
            title="Owned earnings report",
            publisher="Source A",
            published_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
            source="rss",
            group_key="owned earnings",
        )
        second = NewsItem(
            canonical_url="https://example.test/two",
            title="Owned earnings follow-up",
            publisher="Source B",
            published_at=datetime(2026, 8, 13, tzinfo=timezone.utc),
            source="rss",
            group_key="owned earnings",
        )
        db.add_all([first, second])
        db.flush()
        db.add_all(
            [
                NewsSecurityLink(news_item=first, security=owned),
                NewsSecurityLink(news_item=second, security=owned),
            ]
        )
        db.commit()

        payload = weekly_review_data(db, date(2026, 8, 10), date(2026, 8, 16))

    holdings = cast(list[dict[str, object]], payload["holdings"])
    watchlist = cast(list[dict[str, object]], payload["watchlist"])
    assert [item["symbol"] for item in holdings] == ["OWN"]
    assert watchlist == [
        {
            "list": "watchlist",
            "symbol": "WATCH",
            "name": "Watched Security",
            "asset_type": "stock",
            "currency": None,
            "period": {
                "first_observed_at": None,
                "first_price": None,
                "last_observed_at": None,
                "last_price": None,
                "change_percent": None,
                "observation_count": 0,
            },
            "holding_context": {
                "shares": None,
                "average_cost": None,
                "cost_currency": None,
                "cost_basis": None,
                "market_value": None,
                "note": None,
            },
            "news": [],
        }
    ]
    period = cast(dict[str, object], holdings[0]["period"])
    news = cast(list[dict[str, object]], holdings[0]["news"])
    assert period["change_percent"] == "10.0"
    assert news[0]["related_article_count"] == 2
    assert news[0]["source_count"] == 2
