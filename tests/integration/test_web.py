import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from app import main
from app.db import session as session_module
from app.db.models import Base


@pytest.fixture
def client(monkeypatch):
    local_engine = session_module.create_engine(
        "sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=local_engine)
    session_module.engine = local_engine
    session_module.SessionLocal = session_module.sessionmaker(
        bind=local_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    from app.services.market import ensure_default_lists

    with session_module.SessionLocal() as db:
        ensure_default_lists(db)
    with TestClient(main.app) as test_client:
        yield test_client


def test_health_live(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_empty_overview_does_not_show_fake_values(client: TestClient) -> None:
    response = client.get("/overview")
    assert response.status_code == 200
    assert "Start with one security" in response.text
    assert "12,345" not in response.text


def test_watchlist_page_is_reachable(client: TestClient) -> None:
    response = client.get("/watchlist")
    assert response.status_code == 200
    assert "Watchlist" in response.text


def test_holdings_page_is_reachable(client: TestClient) -> None:
    response = client.get("/holdings")
    assert response.status_code == 200
    assert "Holdings" in response.text


def test_manual_refresh_redirects_when_provider_fails(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "sync_security", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "sync_news_for_security", lambda *args, **kwargs: None)
    add_response = client.post(
        "/items",
        data={
            "symbol": "TEST",
            "name": "Test Security",
            "asset_type": "stock",
            "provider_symbol": "TEST",
            "kind": "watchlist",
        },
        follow_redirects=False,
    )
    assert add_response.status_code == 303
    security_path = add_response.headers["location"]

    def fail_sync(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(main, "sync_security", fail_sync)
    refresh_response = client.post(f"{security_path}/refresh", follow_redirects=False)

    assert refresh_response.status_code == 303
    assert refresh_response.headers["location"] == security_path


def test_overview_renders_grouped_news_counts(client: TestClient) -> None:
    from datetime import datetime, timezone

    from app.db.models import ListItem, NewsItem, NewsSecurityLink, Security, UserList

    with session_module.SessionLocal() as db:
        security = Security(canonical_symbol="ABC", name="Example", provider="test")
        watchlist = db.query(UserList).filter_by(kind="watchlist").one()
        db.add(security)
        db.flush()
        db.add(ListItem(user_list=watchlist, security=security, sort_order=1))
        db.flush()
        first = NewsItem(
            canonical_url="https://example.test/a",
            title="Example reports earnings",
            publisher="Source A",
            published_at=datetime.now(timezone.utc),
            source="rss",
            group_key="example reports earnings",
        )
        second = NewsItem(
            canonical_url="https://example.test/b",
            title="Example reports earnings — follow-up",
            publisher="Source B",
            published_at=datetime.now(timezone.utc),
            source="rss",
            group_key="example reports earnings",
        )
        db.add_all([first, second])
        db.flush()
        db.add_all(
            [
                NewsSecurityLink(news_item=first, security=security),
                NewsSecurityLink(news_item=second, security=security),
            ]
        )
        db.commit()

    response = client.get("/overview")

    assert response.status_code == 200
    assert "2 related reports from 2 sources" in response.text


def test_weekly_review_endpoint_defaults_to_previous_calendar_week(client: TestClient) -> None:
    response = client.get("/api/reviews/weekly-data")

    assert response.status_code == 200
    assert set(response.json()) == {"period", "generated_at", "holdings", "watchlist", "notes"}
    assert response.json()["holdings"] == []
    assert response.json()["watchlist"] == []


def test_weekly_review_endpoint_requires_both_dates(client: TestClient) -> None:
    response = client.get("/api/reviews/weekly-data?start=2026-08-10")

    assert response.status_code == 400
    assert response.json()["detail"] == "start and end must be provided together"


def test_holding_context_save_and_display(client: TestClient) -> None:
    from app.db.models import ListItem, Security, UserList

    with session_module.SessionLocal() as db:
        security = Security(canonical_symbol="ABC", name="Example", provider="test")
        user_list = db.query(UserList).filter_by(kind="holdings").one()
        db.add(security)
        db.flush()
        item = ListItem(user_list=user_list, security=security, sort_order=1)
        db.add(item)
        db.commit()
        item_id = item.id

    save_response = client.post(
        f"/items/{item_id}/holding",
        data={
            "shares": "12.5",
            "average_cost": "178.40",
            "cost_currency": "USD",
            "note": "Core position",
        },
        follow_redirects=False,
    )
    assert save_response.status_code == 303
    assert save_response.headers["location"] == "/holdings"

    holdings_page = client.get("/holdings")
    assert holdings_page.status_code == 200
    assert "Core position" in holdings_page.text
    assert "Edit context" in holdings_page.text


def test_holding_context_rejects_negative_shares(client: TestClient) -> None:
    from app.db.models import ListItem, Security, UserList

    with session_module.SessionLocal() as db:
        security = Security(canonical_symbol="DEF", name="Another", provider="test")
        user_list = db.query(UserList).filter_by(kind="holdings").one()
        db.add(security)
        db.flush()
        item = ListItem(user_list=user_list, security=security, sort_order=2)
        db.add(item)
        db.commit()
        item_id = item.id

    response = client.post(
        f"/items/{item_id}/holding",
        data={"shares": "-5", "average_cost": "", "cost_currency": "", "note": ""},
    )

    assert response.status_code == 400
    assert "negative" in response.json()["detail"]


def test_security_detail_chart_range_toggles(client: TestClient) -> None:
    from datetime import datetime, timedelta, timezone
    from decimal import Decimal

    from app.db.models import PriceObservation, Security

    with session_module.SessionLocal() as db:
        security = Security(canonical_symbol="RNG", name="Range Test", provider="test")
        db.add(security)
        db.flush()
        now = datetime.now(timezone.utc)
        db.add_all(
            [
                PriceObservation(
                    security_id=security.id,
                    observed_at=now - timedelta(days=200),
                    session_date=(now - timedelta(days=200)).date(),
                    price=Decimal("100"),
                    source="test",
                ),
                PriceObservation(
                    security_id=security.id,
                    observed_at=now - timedelta(days=10),
                    session_date=(now - timedelta(days=10)).date(),
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
        security_id = security.id

    all_page = client.get(f"/security/{security_id}")
    assert all_page.status_code == 200
    assert "3 points" in all_page.text
    assert "range=6m" in all_page.text
    assert 'class="chart-range active"' in all_page.text
    assert ">1Y</a>" in all_page.text
    assert ">ALL</a>" not in all_page.text
    assert ">5Y</a>" not in all_page.text

    month_page = client.get(f"/security/{security_id}?range=1m")
    assert month_page.status_code == 200
    assert "2 points" in month_page.text
    assert 'class="chart-range active"' in month_page.text
    assert ">1M</a>" in month_page.text

    day_page = client.get(f"/security/{security_id}?range=1d")
    assert day_page.status_code == 200
    assert "1 points" in day_page.text
    assert "intraday movement is not tracked" in day_page.text

    invalid = client.get(f"/security/{security_id}?range=3y")
    assert invalid.status_code == 400
