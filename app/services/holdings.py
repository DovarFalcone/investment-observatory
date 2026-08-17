from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import HoldingAnnotation, ListItem
from app.domain.calculations import derived_holding_values


def get_item(db: Session, item_id: int) -> ListItem | None:
    return db.get(ListItem, item_id)


def annotation_for(db: Session, item: ListItem) -> HoldingAnnotation | None:
    return db.scalar(select(HoldingAnnotation).where(HoldingAnnotation.list_item_id == item.id))


def parse_optional_decimal(raw: str, field: str) -> Decimal | None:
    value = (raw or "").strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{field} must be a number") from None


def save_holding_context(
    db: Session,
    item: ListItem,
    shares: Decimal | None,
    average_cost: Decimal | None,
    cost_currency: str | None,
    note: str | None,
) -> HoldingAnnotation | None:
    """Create or update an annotation; delete it when all values are cleared."""
    if shares is not None and shares < 0:
        raise ValueError("Shares cannot be negative")
    if average_cost is not None and average_cost < 0:
        raise ValueError("Average cost cannot be negative")

    cleared = shares is None and average_cost is None and not (note or "").strip()
    annotation = annotation_for(db, item)
    if cleared:
        if annotation is not None:
            db.delete(annotation)
            db.commit()
        return None

    if annotation is None:
        annotation = HoldingAnnotation(list_item=item)
        db.add(annotation)
    annotation.shares = shares
    annotation.average_cost = average_cost
    annotation.cost_currency = (cost_currency or "").strip().upper() or None
    annotation.note = (note or "").strip() or None
    db.commit()
    db.refresh(annotation)
    return annotation


def context_view(annotation: HoldingAnnotation | None, latest_price: Decimal | None, price_currency: str | None) -> dict[str, object]:
    """Template-ready context: stored inputs plus derived numbers or the reason they are absent."""
    if annotation is None:
        return {
            "has_annotation": False,
            "shares": None,
            "average_cost": None,
            "cost_currency": None,
            "note": None,
            "derived": {"status": "no_annotation"},
        }
    derived = derived_holding_values(
        annotation.shares,
        annotation.average_cost,
        latest_price,
        price_currency,
        annotation.cost_currency,
    )
    return {
        "has_annotation": True,
        "shares": annotation.shares,
        "average_cost": annotation.average_cost,
        "cost_currency": annotation.cost_currency,
        "note": annotation.note,
        "derived": derived,
    }
