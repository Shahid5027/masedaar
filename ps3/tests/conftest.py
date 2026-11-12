"""Pytest fixtures and CSV builders for EDUCORE AI PS3."""

import csv
import io
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import database
from database import Base, apply_additive_migrations, create_db_engine, get_db
from main import create_app
from models.schemas import UserCreateRequest
from services.auth_service import clear_rate_limit_cache, create_user_account
from services.notification_service import reset_test_outbox


@pytest.fixture()
def test_db_session(tmp_path: Path):
    """Provide an isolated SQLite database session per test with FK and audit triggers."""
    clear_rate_limit_cache()
    reset_test_outbox()
    db_file = tmp_path / "test_ps3.db"
    test_engine = create_db_engine(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(bind=test_engine)
    apply_additive_migrations(test_engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine, class_=Session
    )

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def make_test_app(test_db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Build a FastAPI app wired to the isolated test DB session."""
    monkeypatch.setattr(database, "init_db", lambda target_engine=None: None)
    import main as main_module

    TestingSessionFactory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_session.get_bind(),
        class_=Session,
    )
    monkeypatch.setattr(main_module, "init_db", lambda target_engine=None: None)
    monkeypatch.setattr(main_module, "SessionLocal", TestingSessionFactory)
    app = create_app()

    def _override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = _override_get_db
    return app


def login_test_client(
    test_client: TestClient, username: str, password: str
) -> dict:
    """Authenticate a TestClient through the real /auth/login flow and attach CSRF header."""
    resp = test_client.post(
        "/api/ps3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    csrf_token = resp.json()["data"]["csrf_token"]
    test_client.headers.update({"X-CSRF-Token": csrf_token})
    return resp.json()["data"]


@pytest.fixture()
def unauthenticated_client(test_db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Provide an unauthenticated FastAPI TestClient wired to the isolated test DB session."""
    app = make_test_app(test_db_session, monkeypatch)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def client(test_db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """Provide an authenticated administrator FastAPI TestClient using real cookies & CSRF."""
    create_user_account(
        test_db_session,
        UserCreateRequest(
            username="admin.test",
            email="admin.test@educore.local",
            full_name="Test Administrator",
            role="administrator",
            password="AdminTest!2026Password",
        ),
    )
    app = make_test_app(test_db_session, monkeypatch)
    with TestClient(app) as test_client:
        login_test_client(test_client, "admin.test", "AdminTest!2026Password")
        yield test_client
    app.dependency_overrides.clear()


def build_csv_bytes(
    rows: List[Dict[str, Any]],
    columns: Optional[Iterable[str]] = None,
) -> bytes:
    """Serialize row dicts into UTF-8 CSV bytes."""
    if columns is None:
        if not rows:
            raise ValueError("columns must be supplied when rows is empty")
        col_list = list(rows[0].keys())
    else:
        col_list = list(columns)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=col_list)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def sample_valid_rows(include_dropout_label: bool = False) -> List[Dict[str, Any]]:
    """Return a clean sample of valid student rows."""
    rows: List[Dict[str, Any]] = [
        {
            "student_id": "STU-1001",
            "attendance_rate": 93.5,
            "average_grade": 84.2,
            "late_assignments": 1,
            "missing_assignments": 0,
            "lms_logins_30d": 35,
            "engagement_change_pct": 12.5,
            "previous_failure_count": 0,
        },
        {
            "student_id": "STU-1002",
            "attendance_rate": 58.0,
            "average_grade": 49.5,
            "late_assignments": 4,
            "missing_assignments": 5,
            "lms_logins_30d": 6,
            "engagement_change_pct": -45.0,
            "previous_failure_count": 2,
        },
    ]
    if include_dropout_label:
        rows[0]["dropout_label"] = 0
        rows[1]["dropout_label"] = 1
    return rows

