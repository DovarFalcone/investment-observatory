from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Security
from app.domain.types import SecurityCandidate
from app.providers.registry import market_provider


def search_securities(query: str) -> list[SecurityCandidate]:
    return market_provider().search(query)[:12]


def get_or_create_security(db: Session, candidate: SecurityCandidate) -> Security:
    security = db.scalar(
        select(Security).where(
            Security.canonical_symbol == candidate.symbol,
            Security.exchange == candidate.exchange,
        )
    )
    if security is None:
        security = Security(
            canonical_symbol=candidate.symbol,
            name=candidate.name,
            asset_type=candidate.asset_type,
            exchange=candidate.exchange,
            currency=candidate.currency,
            provider=market_provider().name,
            provider_symbol=candidate.provider_symbol,
        )
        db.add(security)
        db.commit()
        db.refresh(security)
    return security
