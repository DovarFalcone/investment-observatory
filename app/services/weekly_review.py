from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import ListItem, NewsItem, NewsSecurityLink, PriceObservation, UserList
from app.domain.calculations import percent_change


def previous_calendar_week(today: date | None = None) -> tuple[date, date]:
    """Return the previous Monday-Sunday calendar week."""
    current = today or datetime.now(timezone.utc).date()
    this_monday = current - timedelta(days=current.weekday())
    return this_monday - timedelta(days=7), this_monday - timedelta(days=1)


def _period_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(start, time.min, tzinfo=timezone.utc),
        datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc),
    )


def _money(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _security_items(db: Session) -> list[ListItem]:
    query = (
        select(ListItem)
        .join(ListItem.user_list)
        .options(joinedload(ListItem.security), joinedload(ListItem.holding))
        .where(ListItem.archived_at.is_(None))
        .order_by(UserList.kind, ListItem.sort_order, ListItem.id)
    )
    return list(db.scalars(query).unique().all())


def weekly_review_data(db: Session, start: date, end: date) -> dict[str, object]:
    """Build deterministic facts for an external weekly review generator."""
    if end < start:
        raise ValueError("Review end date must not precede start date")
    start_at, end_at = _period_bounds(start, end)
    items = _security_items(db)
    security_ids = [item.security_id for item in items]

    observations = list(
        db.scalars(
            select(PriceObservation)
            .where(
                PriceObservation.security_id.in_(security_ids or [-1]),
                PriceObservation.observed_at >= start_at,
                PriceObservation.observed_at < end_at,
            )
            .order_by(PriceObservation.security_id, PriceObservation.observed_at)
        ).all()
    )
    observations_by_security: dict[int, list[PriceObservation]] = {}
    for observation in observations:
        observations_by_security.setdefault(observation.security_id, []).append(observation)

    links = list(
        db.scalars(
            select(NewsSecurityLink)
            .join(NewsSecurityLink.news_item)
            .options(joinedload(NewsSecurityLink.news_item))
            .where(
                NewsSecurityLink.security_id.in_(security_ids or [-1]),
                NewsItem.published_at >= start_at,
                NewsItem.published_at < end_at,
            )
            .order_by(NewsItem.published_at.desc(), NewsItem.id.desc())
        ).all()
    )
    grouped_items: dict[tuple[int, str], list[NewsItem]] = {}
    for link in links:
        article = link.news_item
        key = (link.security_id, article.group_key or f"article:{article.id}")
        grouped_items.setdefault(key, []).append(article)

    grouped_news: dict[int, list[dict[str, object]]] = {}
    for (security_id, _), articles in grouped_items.items():
        articles.sort(
            key=lambda article: (
                article.published_at.timestamp() if article.published_at else float("-inf"),
                article.id,
            ),
            reverse=True,
        )
        representative = articles[0]
        publishers = sorted({article.publisher or article.source for article in articles})
        grouped_news.setdefault(security_id, []).append(
            {
                "headline": representative.title,
                "publisher": representative.publisher or representative.source,
                "published_at": representative.published_at.isoformat()
                if representative.published_at
                else None,
                "url": representative.canonical_url,
                "related_article_count": len(articles),
                "source_count": len(publishers),
                "publishers": publishers,
            }
        )
    for security_news in grouped_news.values():
        security_news.sort(
            key=lambda article: str(article["published_at"] or ""), reverse=True
        )

    serialized_items: list[dict[str, object]] = []
    for item in items:
        security = item.security
        points = observations_by_security.get(item.security_id, [])
        first = points[0] if points else None
        last = points[-1] if points else None
        holding = item.holding if item.user_list.kind == "holdings" else None
        cost_basis = holding.shares * holding.average_cost if holding and holding.shares and holding.average_cost else None
        market_value = holding.shares * last.price if holding and holding.shares and last else None
        serialized_items.append(
            {
                "list": item.user_list.kind,
                "symbol": security.canonical_symbol,
                "name": security.name,
                "asset_type": security.asset_type,
                "currency": security.currency,
                "period": {
                    "first_observed_at": first.observed_at.isoformat() if first else None,
                    "first_price": _money(first.price) if first else None,
                    "last_observed_at": last.observed_at.isoformat() if last else None,
                    "last_price": _money(last.price) if last else None,
                    "change_percent": str(percent_change(last.price, first.price))
                    if first and last
                    else None,
                    "observation_count": len(points),
                },
                "holding_context": {
                    "shares": _money(holding.shares) if holding else None,
                    "average_cost": _money(holding.average_cost) if holding else None,
                    "cost_currency": holding.cost_currency if holding else None,
                    "cost_basis": _money(cost_basis),
                    "market_value": _money(market_value),
                    "note": holding.note if holding else None,
                },
                "news": grouped_news.get(item.security_id, []),
            }
        )

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "holdings": [item for item in serialized_items if item["list"] == "holdings"],
        "watchlist": [item for item in serialized_items if item["list"] == "watchlist"],
        "notes": [
            "Prices and changes are derived from locally stored observations.",
            "Missing values mean the stored data was insufficient; no values are inferred.",
            "This payload is factual input for an external review generator, not financial advice.",
        ],
    }
