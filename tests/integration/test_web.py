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
