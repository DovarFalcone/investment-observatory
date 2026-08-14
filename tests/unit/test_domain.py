from datetime import datetime, timezone
from decimal import Decimal

from app.domain.calculations import latest_and_previous, percent_change
from app.domain.news import group_recent_news, news_group_key
from app.domain.types import NewsArticle, PricePoint


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
