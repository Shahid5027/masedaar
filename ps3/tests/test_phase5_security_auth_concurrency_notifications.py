"""Phase 5 security, authentication, RBAC, audit protection, concurrency, and notification tests."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from config import get_settings
from database import apply_additive_migrations
from models.db_models import InterventionHistory, Notification, SecurityAuditLog, UserSession
from models.schemas import UserCreateRequest
from services.auth_service import create_user_account, hash_password
from services.notification_service import get_test_outbox, reset_test_outbox
from tests.conftest import login_test_client, make_test_app


def _make_role_client(
    test_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    username: str,
    role: str,
    password: str = "RolePass!2026Secure",
) -> TestClient:
    create_user_account(
        test_db_session,
        UserCreateRequest(
            username=username,
            email=f"{username}@educore.local",
            full_name=f"{username.title()} User",
            role=role,  # type: ignore[arg-type]
            password=password,
        ),
    )
    app = make_test_app(test_db_session, monkeypatch)
    tc = TestClient(app)
    login_test_client(tc, username, password)
    return tc


def test_authentication_cookies_csrf_rate_limit_and_expiration(
    test_db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify scrypt login, HttpOnly cookies, CSRF guard, rate limiting, refresh, logout, and expiry."""
    create_user_account(
        test_db_session,
        UserCreateRequest(
            username="counsellor.sara",
            email="sara@educore.local",
            full_name="Sara Counsellor",
            role="counsellor",
            password="SaraStrong!2026Pass",
        ),
    )
    app = make_test_app(test_db_session, monkeypatch)

    with TestClient(app) as tc:
        # Health remains public and non-PII
        assert tc.get("/api/ps3/health").status_code == 200

        # Protected endpoints reject unauthenticated requests with 401
        assert tc.get("/api/ps3/data/summary").status_code == 401
        assert tc.get("/api/ps3/students").status_code == 401
        assert tc.get("/api/ps3/interventions").status_code == 401

        # Wrong password & unknown username produce identical non-enumerating 401 message
        bad_known = tc.post(
            "/api/ps3/auth/login",
            json={"username_or_email": "counsellor.sara", "password": "wrong-password"},
        )
        bad_unknown = tc.post(
            "/api/ps3/auth/login",
            json={"username_or_email": "nobody@educore.local", "password": "wrong-password"},
        )
        assert bad_known.status_code == 401
        assert bad_unknown.status_code == 401
        assert bad_known.json()["message"] == bad_unknown.json()["message"]

        # Valid login sets HttpOnly session cookie + CSRF token and excludes password_hash
        ok_resp = tc.post(
            "/api/ps3/auth/login",
            json={"username_or_email": "counsellor.sara", "password": "SaraStrong!2026Pass"},
        )
        assert ok_resp.status_code == 200
        body = ok_resp.json()["data"]
        assert "password_hash" not in body["user"]
        assert "password" not in body["user"]
        set_cookie_header = ok_resp.headers.get("set-cookie", "")
        assert "ps3_session=" in set_cookie_header
        assert "HttpOnly" in set_cookie_header
        csrf_token = body["csrf_token"]

        # State-changing request without CSRF fails with 403
        no_csrf = tc.post("/api/ps3/auth/refresh")
        assert no_csrf.status_code == 403
        assert no_csrf.json()["errors"][0]["code"] == "CSRF_VALIDATION_FAILED"

        # With valid CSRF header, refresh rotates CSRF token & extends session
        refreshed = tc.post("/api/ps3/auth/refresh", headers={"X-CSRF-Token": csrf_token})
        assert refreshed.status_code == 200
        new_csrf = refreshed.json()["data"]["csrf_token"]
        assert new_csrf != csrf_token

        # Logout revokes session server-side
        logged_out = tc.post("/api/ps3/auth/logout", headers={"X-CSRF-Token": new_csrf})
        assert logged_out.status_code == 200
        assert tc.get("/api/ps3/auth/me").status_code == 401

        # Re-login and simulate expired session timestamp -> 401 SESSION_EXPIRED
        relogin = tc.post(
            "/api/ps3/auth/login",
            json={"username_or_email": "counsellor.sara", "password": "SaraStrong!2026Pass"},
        )
        assert relogin.status_code == 200
        sess = test_db_session.scalar(
            select(UserSession).order_by(UserSession.id.desc()).limit(1)
        )
        assert sess is not None
        sess.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        test_db_session.commit()
        expired_resp = tc.get("/api/ps3/auth/me")
        assert expired_resp.status_code == 401
        assert expired_resp.json()["errors"][0]["code"] == "SESSION_EXPIRED"

    # Rate limit after repeated failures locks account -> 429
    with TestClient(app) as brute:
        settings = get_settings()
        for _ in range(settings.login_rate_limit_attempts):
            r = brute.post(
                "/api/ps3/auth/login",
                json={"username_or_email": "counsellor.sara", "password": "Wrong!Password99"},
            )
            assert r.status_code == 401
        locked_resp = brute.post(
            "/api/ps3/auth/login",
            json={"username_or_email": "counsellor.sara", "password": "SaraStrong!2026Pass"},
        )
        assert locked_resp.status_code == 429
        assert locked_resp.json()["errors"][0]["code"] == "RATE_LIMITED"


def test_rbac_role_boundaries_across_admin_counsellor_and_viewer(
    test_db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Enforce strict RBAC across administrator, counsellor, and institutional viewer roles."""
    admin_tc = _make_role_client(test_db_session, monkeypatch, "rbac.admin", "administrator")
    counsellor_a = _make_role_client(test_db_session, monkeypatch, "rbac.counsellor.a", "counsellor")
    counsellor_b = _make_role_client(test_db_session, monkeypatch, "rbac.counsellor.b", "counsellor")
    viewer_tc = _make_role_client(test_db_session, monkeypatch, "rbac.viewer", "viewer")

    try:
        # Admin seeds data, trains model, and creates an intervention assigned to counsellor A
        assert admin_tc.post("/api/ps3/data/seed-synthetic?num_records=210&seed=9").status_code == 201
        assert admin_tc.post("/api/ps3/model/train", json={}).status_code == 200
        assert admin_tc.post("/api/ps3/predictions/run", json={}).status_code == 200
        student_id = admin_tc.get("/api/ps3/students?limit=1").json()["data"]["items"][0]["student_id"]

        created = admin_tc.post(
            "/api/ps3/interventions",
            json={
                "student_id": student_id,
                "intervention_type": "advisor_outreach",
                "recommended_action": "Assigned outreach for RBAC check.",
                "priority": "high",
                "assigned_to": "rbac.counsellor.a",
            },
        )
        assert created.status_code == 201
        iv_id = created.json()["data"]["id"]

        # Institutional viewer: allowed analytics/metrics only; blocked from student records, interventions, notes, admin
        assert viewer_tc.get("/api/ps3/data/summary").status_code == 200
        assert viewer_tc.get("/api/ps3/model/metrics").status_code == 200
        assert viewer_tc.get("/api/ps3/students").status_code == 403
        assert viewer_tc.get(f"/api/ps3/students/{student_id}").status_code == 403
        assert viewer_tc.get(f"/api/ps3/students/{student_id}/interventions").status_code == 403
        assert viewer_tc.get("/api/ps3/interventions").status_code == 403
        assert viewer_tc.get(f"/api/ps3/interventions/{iv_id}").status_code == 403
        assert viewer_tc.post(
            "/api/ps3/interventions",
            json={
                "student_id": student_id,
                "intervention_type": "tutoring",
                "recommended_action": "Viewer forbidden",
            },
        ).status_code == 403
        assert viewer_tc.get("/api/ps3/users").status_code == 403
        assert viewer_tc.get("/api/ps3/ops/status").status_code == 403
        assert viewer_tc.post("/api/ps3/data/seed-synthetic?num_records=210").status_code == 403
        assert viewer_tc.post("/api/ps3/model/train", json={}).status_code == 403

        # Counsellor B cannot modify an intervention assigned to Counsellor A
        forbidden_edit = counsellor_b.patch(
            f"/api/ps3/interventions/{iv_id}",
            json={"version": 1, "notes": "Unauthorized cross-counsellor edit"},
        )
        assert forbidden_edit.status_code == 403

        # Counsellor A cannot access admin endpoints or archive interventions
        assert counsellor_a.get("/api/ps3/users").status_code == 403
        assert counsellor_a.get("/api/ps3/ops/status").status_code == 403
        assert counsellor_a.post(
            f"/api/ps3/interventions/{iv_id}/archive", json={"version": 1}
        ).status_code == 403
        assert counsellor_a.post("/api/ps3/model/train", json={}).status_code == 403

        # Counsellor A CAN view students and update their own assigned intervention
        assert counsellor_a.get(f"/api/ps3/students/{student_id}").status_code == 200
        own_edit = counsellor_a.patch(
            f"/api/ps3/interventions/{iv_id}",
            json={"version": 1, "status": "IN_PROGRESS", "notes": "Verified counsellor A edit"},
        )
        assert own_edit.status_code == 200
        assert own_edit.json()["data"]["version"] == 2

        # Deactivating viewer revokes active session immediately
        users_list = admin_tc.get("/api/ps3/users").json()["data"]["items"]
        viewer_id = next(u["id"] for u in users_list if u["username"] == "rbac.viewer")
        deact = admin_tc.patch(f"/api/ps3/users/{viewer_id}", json={"is_active": False})
        assert deact.status_code == 200
        assert viewer_tc.get("/api/ps3/data/summary").status_code == 401
    finally:
        admin_tc.close()
        counsellor_a.close()
        counsellor_b.close()
        viewer_tc.close()


def test_optimistic_concurrency_and_audit_history_protection(
    client: TestClient, test_db_session: Session
) -> None:
    """Verify HTTP 409 version conflict protection, verified actor identity, and immutable history."""
    assert client.post("/api/ps3/data/seed-synthetic?num_records=210&seed=11").status_code == 201
    student_id = client.get("/api/ps3/students?limit=1").json()["data"]["items"][0]["student_id"]

    # Spoofed client actor_id is ignored in favor of authenticated admin.test identity
    created = client.post(
        "/api/ps3/interventions",
        json={
            "student_id": student_id,
            "intervention_type": "counselling_session",
            "recommended_action": "Concurrency & audit protection test.",
            "priority": "medium",
            "actor_id": "spoofed.evil.actor",
        },
    )
    assert created.status_code == 201
    iv_id = created.json()["data"]["id"]
    assert created.json()["data"]["version"] == 1

    # Missing version is rejected with 422
    missing_ver = client.patch(
        f"/api/ps3/interventions/{iv_id}",
        json={"notes": "No version supplied"},
    )
    assert missing_ver.status_code == 422

    # First counsellor saves version=1 -> version becomes 2
    first_save = client.patch(
        f"/api/ps3/interventions/{iv_id}",
        json={"version": 1, "notes": "Counsellor 1 update", "status": "IN_PROGRESS"},
    )
    assert first_save.status_code == 200
    assert first_save.json()["data"]["version"] == 2

    # Second concurrent counsellor tries saving stale version=1 -> 409 conflict without overwrite
    stale_save = client.patch(
        f"/api/ps3/interventions/{iv_id}",
        json={"version": 1, "notes": "Stale overwrite attempt", "status": "COMPLETED"},
    )
    assert stale_save.status_code == 409
    assert stale_save.json()["errors"][0]["code"] == "INTERVENTION_VERSION_CONFLICT"

    detail = client.get(f"/api/ps3/interventions/{iv_id}").json()["data"]
    assert detail["intervention"]["notes"] == "Counsellor 1 update"
    assert detail["intervention"]["status"] == "IN_PROGRESS"
    assert all(h["actor_id"] == "admin.test" for h in detail["history"])
    assert all(h["actor_role"] == "administrator" for h in detail["history"])

    # Database trigger prevents deleting or mutating intervention_history directly
    with pytest.raises((OperationalError, IntegrityError)):
        test_db_session.execute(
            text("DELETE FROM intervention_history WHERE intervention_id = :iid"),
            {"iid": iv_id},
        )
    test_db_session.rollback()

    with pytest.raises((OperationalError, IntegrityError)):
        test_db_session.execute(
            text("UPDATE intervention_history SET summary = 'tampered' WHERE intervention_id = :iid"),
            {"iid": iv_id},
        )
    test_db_session.rollback()

    # Archiving soft-deletes intervention from default queue while preserving history intact
    arch = client.post(
        f"/api/ps3/interventions/{iv_id}/archive",
        json={"version": 2, "reason": "Retention archive test"},
    )
    assert arch.status_code == 200
    assert arch.json()["data"]["is_archived"] is True
    hist = client.get(f"/api/ps3/interventions/{iv_id}/history").json()["data"]
    assert any(h["action"] == "INTERVENTION_ARCHIVED" for h in hist["items"])


def test_notifications_controlled_transport_dedupe_retry_and_privacy(
    test_db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify notifications for assignment, approaching/overdue follow-up, retry, and privacy."""
    monkeypatch.setenv("NOTIFICATION_EMAIL_TRANSPORT", "memory_test")
    get_settings.cache_clear()
    reset_test_outbox()

    try:
        admin_tc = _make_role_client(test_db_session, monkeypatch, "notif.admin", "administrator")
        counsellor_tc = _make_role_client(
            test_db_session, monkeypatch, "notif.counsellor", "counsellor"
        )
        assert admin_tc.post("/api/ps3/data/seed-synthetic?num_records=210&seed=15").status_code == 201
        student_id = admin_tc.get("/api/ps3/students?limit=1").json()["data"]["items"][0]["student_id"]

        # Create intervention with sensitive notes and overdue follow-up
        past_due = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        created = admin_tc.post(
            "/api/ps3/interventions",
            json={
                "student_id": student_id,
                "intervention_type": "advisor_outreach",
                "recommended_action": "Notify assigned counsellor.",
                "priority": "high",
                "assigned_to": "notif.counsellor",
                "follow_up_date": past_due,
                "notes": "SENSITIVE_PRIVATE_NOTE_DO_NOT_EMAIL",
            },
        )
        assert created.status_code == 201
        iv_id = created.json()["data"]["id"]

        # Controlled email outbox received assignment email WITHOUT exposing private counsellor notes
        outbox = get_test_outbox()
        assert len(outbox) == 1
        assert outbox[0]["to"] == "notif.counsellor@educore.local"
        assert "SENSITIVE_PRIVATE_NOTE_DO_NOT_EMAIL" not in outbox[0]["subject"]
        assert "SENSITIVE_PRIVATE_NOTE_DO_NOT_EMAIL" not in outbox[0]["body"]

        # Simulate SMTP failure on status update: core intervention update still commits cleanly
        reset_test_outbox(simulate_failure=True)
        upd = counsellor_tc.patch(
            f"/api/ps3/interventions/{iv_id}",
            json={"version": 1, "status": "IN_PROGRESS"},
        )
        assert upd.status_code == 200
        assert upd.json()["data"]["status"] == "IN_PROGRESS"

        failed_notif = test_db_session.scalar(
            select(Notification).where(
                Notification.intervention_id == iv_id,
                Notification.email_status == "failed",
            )
        )
        assert failed_notif is not None
        assert admin_tc.post(f"/api/ps3/notifications/{failed_notif.id}/retry").json()["data"]["email_status"] == "test_captured"

        # Scan due follow-ups generates overdue alert once (deduped on repeated scan)
        scan1 = admin_tc.post("/api/ps3/notifications/scan-followups")
        assert scan1.status_code == 200
        assert scan1.json()["data"]["overdue_count"] >= 1
        scan2 = admin_tc.post("/api/ps3/notifications/scan-followups")
        assert scan2.status_code == 200
        assert scan2.json()["data"]["created_count"] == 0

        # Counsellor inbox contains alerts and supports mark-read
        inbox = counsellor_tc.get("/api/ps3/notifications").json()["data"]
        assert inbox["unread_count"] >= 1
        first_id = inbox["items"][0]["id"]
        assert counsellor_tc.patch(f"/api/ps3/notifications/{first_id}/read").json()["data"]["is_read"] is True

        # Ops telemetry & security audit logs are accessible to administrator
        ops = admin_tc.get("/api/ps3/ops/status")
        assert ops.status_code == 200
        assert ops.json()["data"]["total_users"] >= 2
        audit_logs = admin_tc.get("/api/ps3/audit/security")
        assert audit_logs.status_code == 200
        assert audit_logs.json()["data"]["total"] >= 1
    finally:
        reset_test_outbox()
        get_settings.cache_clear()


def test_security_headers_and_phase5_additive_migration(
    client: TestClient, tmp_path: Path
) -> None:
    """Verify security headers and Phase 5 additive migration on a legacy Phase 1-3 SQLite DB."""
    health = client.get("/api/ps3/health")
    assert health.headers.get("x-content-type-options") == "nosniff"
    assert health.headers.get("x-frame-options") == "DENY"
    assert "no-store" in health.headers.get("cache-control", "")

    legacy_db = tmp_path / "legacy_phase3.db"
    eng = create_engine(f"sqlite:///{legacy_db.as_posix()}", future=True)
    with eng.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE students ("
                "student_id VARCHAR(64) PRIMARY KEY, "
                "is_synthetic BOOLEAN NOT NULL DEFAULT 0, "
                "data_source VARCHAR(64) NOT NULL DEFAULT 'csv_upload', "
                "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE interventions ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "student_id VARCHAR(64) NOT NULL, "
                "prediction_id INTEGER, "
                "intervention_type VARCHAR(64) NOT NULL, "
                "recommended_action TEXT NOT NULL, "
                "status VARCHAR(32) NOT NULL, "
                "assigned_to VARCHAR(128), "
                "notes TEXT, "
                "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO students VALUES ('LEG-01', 0, 'csv_upload', '2026-01-01', '2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO interventions (student_id, intervention_type, recommended_action, status, created_at, updated_at) "
                "VALUES ('LEG-01', 'outreach', 'Call student', 'planned', '2026-01-01', '2026-01-01')"
            )
        )

    apply_additive_migrations(eng)
    insp = inspect(eng)
    student_cols = {c["name"] for c in insp.get_columns("students")}
    intr_cols = {c["name"] for c in insp.get_columns("interventions")}
    assert {"is_archived", "archived_at"}.issubset(student_cols)
    assert {"priority", "follow_up_date", "completed_at", "is_demo", "version", "is_archived", "archived_at"}.issubset(intr_cols)

    with eng.connect() as conn:
        row = conn.execute(text("SELECT version, is_archived FROM interventions WHERE student_id='LEG-01'")).fetchone()
        assert row == (1, 0)
    eng.dispose()

