import logging
import random
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.config import settings
from app.db import session
from app.db.models import Base, ListItem, PriceObservation, UserList
from app.services.market import active_items, sync_security
from app.services.news import sync_news_for_security

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )


def should_skip_market_sync(db, now: datetime | None = None) -> bool:
    """Skip quiet weekend polling only when every item has the expected Friday close."""
    current = now or datetime.now(timezone.utc)
    if current.weekday() < 5:
        return False

    active_security_ids = select(ListItem.security_id).join(UserList).where(ListItem.archived_at.is_(None))
    security_ids = list(db.scalars(active_security_ids).all())
    if not security_ids:
        return True

    expected_session = current.date() - timedelta(days=1 if current.weekday() == 5 else 2)
    latest_sessions = db.execute(
        select(
            PriceObservation.security_id,
            func.max(PriceObservation.session_date),
        )
        .where(PriceObservation.security_id.in_(security_ids))
        .group_by(PriceObservation.security_id)
    ).all()
    latest_by_security = {security_id: session_date for security_id, session_date in latest_sessions}
    return all(
        (latest_session := latest_by_security.get(security_id)) is not None
        and latest_session >= expected_session
        for security_id in security_ids
    )


def next_sleep_seconds() -> float:
    base = max(settings.market_update_minutes, 5) * 60
    return max(5 * 60, base + random.uniform(-60, 60))


def run_market_sync() -> None:
    with session.SessionLocal() as db:
        items = active_items(db)
        if should_skip_market_sync(db):
            logger.info("Skipping weekend market sync; all securities have the expected close")
            return
        for item in items:
            try:
                inserted = sync_security(db, item.security)
                logger.info("Market sync symbol=%s inserted=%d", item.security.canonical_symbol, inserted)
            except Exception:
                db.rollback()
                logger.exception("Market sync failed symbol=%s", item.security.canonical_symbol)


def run_news_sync() -> None:
    with session.SessionLocal() as db:
        seen: set[int] = set()
        for item in active_items(db):
            if item.security_id in seen:
                continue
            seen.add(item.security_id)
            try:
                inserted = sync_news_for_security(db, item.security)
                logger.info("News sync symbol=%s inserted=%d", item.security.canonical_symbol, inserted)
            except Exception:
                db.rollback()
                logger.exception("News sync failed symbol=%s", item.security.canonical_symbol)
            time.sleep(2)


def main() -> None:
    configure_logging()
    Base.metadata.create_all(bind=session.engine)
    last_news = datetime.min.replace(tzinfo=timezone.utc)
    while True:
        run_market_sync()
        now = datetime.now(timezone.utc)
        if (now - last_news).total_seconds() >= settings.news_update_hours * 3600:
            run_news_sync()
            last_news = now
        time.sleep(next_sleep_seconds())


if __name__ == "__main__":
    main()
