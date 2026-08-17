from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import ListItem, PriceObservation, Security, SyncRun, UserList
from app.domain.calculations import percent_change
from app.providers.registry import market_provider


def ensure_default_lists(db: Session) -> tuple[UserList, UserList]:
    watchlist = db.scalar(select(UserList).where(UserList.kind == "watchlist"))
    holdings = db.scalar(select(UserList).where(UserList.kind == "holdings"))
    if watchlist is None:
        watchlist = UserList(kind="watchlist", name="Watchlist")
        db.add(watchlist)
    if holdings is None:
        holdings = UserList(kind="holdings", name="Holdings")
        db.add(holdings)
    db.commit()
    return watchlist, holdings


def active_items(db: Session, kind: str | None = None) -> list[ListItem]:
    query = (
        select(ListItem)
        .join(ListItem.user_list)
        .options(joinedload(ListItem.security), joinedload(ListItem.holding))
        .where(ListItem.archived_at.is_(None))
        .order_by(UserList.kind, ListItem.sort_order, ListItem.id)
    )
    if kind:
        query = query.where(UserList.kind == kind)
    return list(db.scalars(query).unique().all())


def add_security_to_list(db: Session, security: Security, kind: str) -> ListItem:
    user_list = db.scalar(select(UserList).where(UserList.kind == kind))
    if user_list is None:
        ensure_default_lists(db)
        user_list = db.scalar(select(UserList).where(UserList.kind == kind))
    existing = db.scalar(
        select(ListItem).where(ListItem.list_id == user_list.id, ListItem.security_id == security.id)
    )
    if existing:
        existing.archived_at = None
        db.commit()
        return existing
    max_order = db.scalar(select(ListItem.sort_order).where(ListItem.list_id == user_list.id).order_by(ListItem.sort_order.desc()))
    item = ListItem(user_list=user_list, security=security, sort_order=(max_order or 0) + 1)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def sync_security(db: Session, security: Security, days: int = 370) -> int:
    provider = market_provider()
    started = datetime.now(timezone.utc)
    run = SyncRun(job_name="market", provider=provider.name, requested_count=1)
    db.add(run)
    db.commit()
    points = provider.history(security.provider_symbol or security.canonical_symbol, started - timedelta(days=days))
    inserted = 0
    for point in points:
        exists = db.scalar(
            select(PriceObservation).where(
                PriceObservation.security_id == security.id,
                PriceObservation.observed_at == point.observed_at,
                PriceObservation.source == provider.name,
            )
        )
        if exists:
            continue
        db.add(
            PriceObservation(
                security_id=security.id,
                observed_at=point.observed_at,
                session_date=point.observed_at.date(),
                price=point.price,
                open=point.open,
                high=point.high,
                low=point.low,
                volume=point.volume,
                currency=point.currency or security.currency,
                source=provider.name,
                observation_type=point.observation_type,
                source_observed_at=point.source_observed_at,
            )
        )
        inserted += 1
    run.completed_count = 1 if points else 0
    run.failed_count = 0 if points else 1
    run.status = "success" if points else "partial"
    run.finished_at = datetime.now(timezone.utc)
    if not points:
        run.error_summary = "No price data returned by provider"
    db.commit()
    return inserted


def price_points(db: Session, security_id: int, days: int | None = 370) -> list[PriceObservation]:
    query = (
        select(PriceObservation)
        .where(PriceObservation.security_id == security_id)
        .order_by(PriceObservation.observed_at.asc(), PriceObservation.id.asc())
    )
    if days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.where(PriceObservation.observed_at >= since)
    return list(db.scalars(query).all())


def latest_movements(
    db: Session, security_ids: list[int], days: int = 370
) -> dict[int, dict[str, object]]:
    """Return movement anchors without loading each security's full history."""
    unique_ids = list(dict.fromkeys(security_ids))
    if not unique_ids:
        return {}

    since = datetime.now(timezone.utc) - timedelta(days=days)
    ranked = (
        select(
            PriceObservation.id.label("observation_id"),
            func.row_number().over(
                partition_by=PriceObservation.security_id,
                order_by=PriceObservation.observed_at.desc(),
            )
            .label("latest_rank"),
            func.row_number().over(
                partition_by=PriceObservation.security_id,
                order_by=PriceObservation.observed_at,
            ).label("earliest_rank"),
        )
        .where(
            PriceObservation.security_id.in_(unique_ids),
            PriceObservation.observed_at >= since,
        )
        .subquery()
    )
    observations = db.scalars(
        select(PriceObservation)
        .join(ranked, PriceObservation.id == ranked.c.observation_id)
        .where((ranked.c.latest_rank <= 2) | (ranked.c.earliest_rank == 1))
        .order_by(PriceObservation.security_id, PriceObservation.observed_at)
    ).all()

    grouped: dict[int, list[PriceObservation]] = {}
    for observation in observations:
        grouped.setdefault(observation.security_id, []).append(observation)
    return {
        security_id: {
            "movement": movement(points),
            "fresh_at": points[-1].retrieved_at,
        }
        for security_id, points in grouped.items()
    }


def movement(observations: list[PriceObservation]) -> dict[str, Decimal | None]:
    if not observations:
        return {"price": None, "daily": None, "period": None}
    latest = observations[-1]
    previous = observations[-2] if len(observations) > 1 else None
    period_start = observations[0]
    return {
        "price": latest.price,
        "daily": percent_change(latest.price, previous.price if previous else None),
        "period": percent_change(latest.price, period_start.price),
    }
