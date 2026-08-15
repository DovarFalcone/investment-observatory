from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import Base, NewsItem, NewsSecurityLink, Security
from app.domain.calculations import latest_and_previous, percent_change
from app.domain.news import group_recent_news, news_group_key
from app.domain.types import NewsArticle, PricePoint
from app.services.news import recent_news


def test_percent_change_is_explicit_and_decimal_safe() -> None:
    assert percent_change(Decimal("110"), Decimal("100")) == Decimal("10")
    assert percent_change(Decimal("100"), Decimal("0")) is None
    assert percent_change(None, Decimal("100")) is None


def test_latest_and_previous_uses_observation_time() -> None:
    earlier = PricePoint(datetime(2026, 1, 1, tzinfo=timezone.utc), Decimal("10"))
    later = PricePoint(datetime(2026, 1, 2, tzinfo=timezone.utc), Decimal("11"))
    assert latest_and_previous([later, earlier]) == (later, earlier)


def test_news_group_key_removes_punctuation_and_common_words() -> None:
    assert news_group_key("The Company reports earnings for Q2") == "company reports earnings q2"


def test_news_groups_recent_duplicate_topics() -> None:
    now = datetime.now(timezone.utc)
    first = NewsArticle("a", "Company reports earnings", "Source A", now, None, "ABC", "rss")
    second = NewsArticle("b", "Company reports earnings!", "Source B", now, None, "ABC", "rss")
    assert len(group_recent_news([first, second])) == 1


def test_recent_news_returns_one_representative_and_source_counts() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        security = Security(canonical_symbol="ABC", name="Example", provider="test")
        db.add(security)
        db.flush()
        first = NewsItem(
            canonical_url="https://example.test/first",
            title="Company reports earnings",
            publisher="Source A",
            published_at=now,
            source="rss",
            group_key="company reports earnings",
        )
        second = NewsItem(
            canonical_url="https://example.test/second",
            title="Company reports earnings!",
            publisher="Source B",
            published_at=now,
            source="rss",
            group_key="company reports earnings",
        )
        undated = NewsItem(
            canonical_url="https://example.test/undated",
            title="Background report",
            publisher="Source C",
            published_at=None,
            source="rss",
            group_key="background report",
        )
        db.add_all([first, second, undated])
        db.flush()
        db.add_all(
            [
                NewsSecurityLink(news_item=first, security=security),
                NewsSecurityLink(news_item=second, security=security),
                NewsSecurityLink(news_item=undated, security=security),
            ]
        )
        db.commit()

        groups = recent_news(db, security.id)

    assert [group.representative.title for group in groups] == [
        "Company reports earnings!",
        "Background report",
    ]
    assert groups[0].article_count == 2
    assert groups[0].source_count == 2
