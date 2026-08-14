import time
from datetime import datetime, timezone

from app.config import settings
from app.db import session
from app.db.models import Base
from app.services.market import active_items, sync_security
from app.services.news import sync_news_for_security


def run_market_sync() -> None:
    with session.SessionLocal() as db:
        for item in active_items(db):
            try:
                sync_security(db, item.security)
            except Exception:
                db.rollback()


def run_news_sync() -> None:
    with session.SessionLocal() as db:
        seen: set[int] = set()
        for item in active_items(db):
            if item.security_id in seen:
                continue
            seen.add(item.security_id)
            try:
                sync_news_for_security(db, item.security)
            except Exception:
                db.rollback()


def main() -> None:
    Base.metadata.create_all(bind=session.engine)
    last_news = datetime.min.replace(tzinfo=timezone.utc)
    while True:
        run_market_sync()
        now = datetime.now(timezone.utc)
        if (now - last_news).total_seconds() >= settings.news_update_hours * 3600:
            run_news_sync()
            last_news = now
        time.sleep(max(settings.market_update_minutes, 5) * 60)


if __name__ == "__main__":
    main()
