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
