from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import session
from app.db.models import ListItem, Security
from app.services.market import (
    active_items,
    add_security_to_list,
    ensure_default_lists,
    latest_movements,
    movement,
    price_points,
    sync_security,
)
from app.services.news import recent_news, sync_news_for_security
from app.services.securities import get_or_create_security, search_securities


def get_db() -> Session:
    db = session.SessionLocal()
    try:
        yield db
    finally:
        db.close()

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def money(value: object) -> str:
    if value is None:
        return "—"
    return f"{float(value):,.2f}"


def percentage(value: object) -> str:
    if value is None:
        return "—"
    return f"{float(value):+.2f}%"


def status_class(value: object) -> str:
    if value is None:
        return "muted"
    return "positive" if float(value) > 0 else "negative" if float(value) < 0 else "flat"


templates.env.filters["money"] = money
templates.env.filters["percentage"] = percentage
templates.env.filters["status_class"] = status_class


@app.on_event("startup")
def startup() -> None:
    with session.SessionLocal() as db:
        ensure_default_lists(db)


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/", response_class=HTMLResponse)
def home() -> RedirectResponse:
    return RedirectResponse("/overview", status_code=303)


@app.get("/overview", response_class=HTMLResponse)
def overview(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    items = active_items(db)
    snapshots = latest_movements(db, [item.security_id for item in items])
    rows = [
        {
            "item": item,
            "movement": snapshots.get(item.security_id, {}).get(
                "movement", {"price": None, "daily": None, "period": None}
            ),
            "fresh_at": snapshots.get(item.security_id, {}).get("fresh_at"),
        }
        for item in items
    ]
    news = recent_news(db)
    return templates.TemplateResponse(
        request=request,
        name="overview.html",
        context={"request": request, "rows": rows, "news": news, "now": datetime.now(timezone.utc)},
    )


def _render_list(kind: str, request: Request, db: Session) -> HTMLResponse:
    items = active_items(db, kind)
    snapshots = latest_movements(db, [item.security_id for item in items])
    rows = [
        {
            "item": item,
            "movement": snapshots.get(item.security_id, {}).get(
                "movement", {"price": None, "daily": None, "period": None}
            ),
            "fresh_at": snapshots.get(item.security_id, {}).get("fresh_at"),
        }
        for item in items
    ]
    label = "Holdings" if kind == "holdings" else "Watchlist"
    return templates.TemplateResponse(
        request=request,
        name="list.html",
        context={"request": request, "rows": rows, "kind": kind, "label": label},
    )


@app.get("/watchlist", response_class=HTMLResponse)
def watchlist_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return _render_list("watchlist", request, db)


@app.get("/holdings", response_class=HTMLResponse)
def holdings_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return _render_list("holdings", request, db)


@app.get("/security/{security_id}", response_class=HTMLResponse)
def security_detail(security_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    security = db.get(Security, security_id)
    if security is None:
        raise HTTPException(status_code=404, detail="Security not found")
    observations = price_points(db, security_id)
    points = []
    if observations:
        prices = [float(point.price) for point in observations]
        minimum, maximum = min(prices), max(prices)
        spread = maximum - minimum or 1
        for index, observation in enumerate(observations):
            points.append({
                "x": round(index / max(len(observations) - 1, 1) * 720 + 40, 2),
                "y": round(190 - ((float(observation.price) - minimum) / spread * 150), 2),
                "date": observation.observed_at.strftime("%b %-d"),
                "price": observation.price,
            })
    return templates.TemplateResponse(
        request=request,
        name="detail.html",
        context={
            "request": request,
            "security": security,
            "observations": observations,
            "movement": movement(observations),
            "chart_points": points,
            "news": recent_news(db, security_id),
        },
    )


@app.get("/api/securities/search")
def search_api(q: str = Query(min_length=1, max_length=80)) -> list[dict[str, object]]:
    return [candidate.__dict__ for candidate in search_securities(q)]


@app.post("/items")
def add_item(
    symbol: str = Form(...),
    name: str = Form(...),
    asset_type: str = Form("other"),
    exchange: str = Form(""),
    currency: str = Form(""),
    provider_symbol: str = Form(...),
    kind: str = Form("watchlist"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if kind not in {"watchlist", "holdings"}:
        raise HTTPException(status_code=400, detail="Invalid list")
    from app.domain.types import SecurityCandidate

    security = get_or_create_security(
        db,
        SecurityCandidate(symbol, name, asset_type, exchange or None, currency or None, provider_symbol),
    )
    add_security_to_list(db, security, kind)
    try:
        sync_security(db, security, days=370)
        sync_news_for_security(db, security)
    except Exception:
        # Adding the security remains useful even when an external provider is unavailable.
        db.rollback()
    return RedirectResponse(f"/security/{security.id}", status_code=303)


@app.post("/items/{item_id}/archive")
def archive_item(item_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    item = db.get(ListItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="List item not found")
    item.archived_at = datetime.now(timezone.utc)
    db.commit()
    return RedirectResponse(f"/{item.user_list.kind}", status_code=303)


@app.post("/security/{security_id}/refresh")
def refresh_security(security_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    security = db.get(Security, security_id)
    if security is None:
        raise HTTPException(status_code=404, detail="Security not found")
    try:
        sync_security(db, security)
        sync_news_for_security(db, security)
    except Exception:
        db.rollback()
    return RedirectResponse(f"/security/{security_id}", status_code=303)


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="settings.html", context={"request": request})
