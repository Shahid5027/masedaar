"""Comprehensive tests for Phase 4 interventions, history, >500 pagination, and safe migrations."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from database import apply_additive_migrations
from models.db_models import Intervention, InterventionHistory, Prediction, Student


def _seed_model_and_predictions(client: TestClient, num_records: int = 220) -> str:
    seed_resp = client.post(f"/api/ps3/data/seed-synthetic?num_records={num_records}&seed=42")
    assert seed_resp.status_code == 201

    train_resp = client.post(
        "/api/ps3/model/train",
        json={"dataset_mode": "auto", "allow_synthetic_fallback": True},
    )
    assert train_resp.status_code == 200

    pred_resp = client.post(
        "/api/ps3/predictions/run",
        json={"include_synthetic": True, "persist_interventions": True},
    )
    assert pred_resp.status_code == 200
    return train_resp.json()["data"]["model_version"]


def test_intervention_full_lifecycle_history_and_student_lookup(
    client: TestClient, test_db_session: Session
) -> None:
    """Verify create, assign, schedule follow-up, notes, complete, reopen, and audit history."""
    _seed_model_and_predictions(client, num_records=220)

    # Pick a high-risk or first scored student
    stu_resp = client.get("/api/ps3/students?sort_by=risk_score&sort_order=desc&page=1&page_size=5")
    assert stu_resp.status_code == 200
    target_student = stu_resp.json()["data"]["items"][0]
    student_id = target_student["student_id"]
    prediction_id = target_student["latest_prediction_id"]

    # 1. Create a manual counselor-reviewed intervention
    create_resp = client.post(
        "/api/ps3/interventions",
        json={
            "student_id": student_id,
            "prediction_id": prediction_id,
            "intervention_type": "advisor_outreach",
            "recommended_action": "Schedule confidential check-in with student advisor.",
            "priority": "high",
            "notes": "Initial advisor review after elevated risk indicators.",
            "actor_id": "advisor.jane",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()["data"]
    intr_id = created["id"]
    assert created["student_id"] == student_id
    assert created["status"] == "PENDING"
    assert created["priority"] == "high"
    assert created["assigned_to"] is None
    assert created["is_demo"] is True
    assert created["version"] == 1

    # Duplicate active intervention check (same student + prediction + intervention_type) -> 409
    dup_resp = client.post(
        "/api/ps3/interventions",
        json={
            "student_id": student_id,
            "prediction_id": prediction_id,
            "intervention_type": "advisor_outreach",
            "recommended_action": "Duplicate check-in.",
            "priority": "high",
        },
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["errors"][0]["code"] == "DUPLICATE_ACTIVE_INTERVENTION"

    # 2. Assign counsellor (PENDING automatically promotes to ASSIGNED)
    assign_resp = client.patch(
        f"/api/ps3/interventions/{intr_id}",
        json={"version": created["version"], "assigned_to": "counsellor.alex", "actor_id": "lead.advisor"},
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["data"]["assigned_to"] == "counsellor.alex"
    assert assign_resp.json()["data"]["status"] == "ASSIGNED"
    assert assign_resp.json()["data"]["version"] == 2

    # 3. Schedule follow-up date & move to IN_PROGRESS
    follow_up_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    progress_resp = client.patch(
        f"/api/ps3/interventions/{intr_id}",
        json={
            "version": 2,
            "status": "IN_PROGRESS",
            "follow_up_date": follow_up_iso,
            "notes": "Student contacted; first advising session booked.",
            "actor_id": "counsellor.alex",
        },
    )
    assert progress_resp.status_code == 200
    prog_data = progress_resp.json()["data"]
    assert prog_data["status"] == "IN_PROGRESS"
    assert prog_data["follow_up_date"] is not None
    assert prog_data["version"] == 3

    # 4. Verify overdue filter picks up past follow-up date and counts follow_ups_due
    overdue_resp = client.get("/api/ps3/interventions?overdue_only=true&student_id=" + student_id)
    assert overdue_resp.status_code == 200
    assert any(item["id"] == intr_id for item in overdue_resp.json()["data"]["items"])
    assert overdue_resp.json()["data"]["status_counts"]["follow_ups_due"] >= 1

    # 5. Complete intervention
    complete_resp = client.patch(
        f"/api/ps3/interventions/{intr_id}",
        json={"version": 3, "status": "COMPLETED", "notes": "Student attended check-in and tutoring plan."},
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["data"]["status"] == "COMPLETED"
    assert complete_resp.json()["data"]["completed_at"] is not None
    assert complete_resp.json()["data"]["version"] == 4

    # 6. Invalid transition from COMPLETED -> CANCELLED must fail with 422 and keep COMPLETED state
    bad_transition = client.patch(
        f"/api/ps3/interventions/{intr_id}",
        json={"version": 4, "status": "CANCELLED"},
    )
    assert bad_transition.status_code == 422
    assert bad_transition.json()["errors"][0]["code"] == "INVALID_STATUS_TRANSITION"

    # 7. Reopen completed intervention -> IN_PROGRESS clears completed_at
    reopen_resp = client.patch(
        f"/api/ps3/interventions/{intr_id}",
        json={"version": 4, "status": "IN_PROGRESS", "notes": "Reopened for mid-semester check-in."},
    )
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["data"]["status"] == "IN_PROGRESS"
    assert reopen_resp.json()["data"]["completed_at"] is None
    assert reopen_resp.json()["data"]["version"] == 5

    # 8. Inspect intervention detail & chronological history timeline
    detail_resp = client.get(f"/api/ps3/interventions/{intr_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["related_prediction"]["id"] == prediction_id
    history_resp = client.get(f"/api/ps3/interventions/{intr_id}/history")
    assert history_resp.status_code == 200
    actions = [entry["action"] for entry in history_resp.json()["data"]["items"]]
    assert "INTERVENTION_CREATED" in actions
    assert "COUNSELLOR_ASSIGNED" in actions
    assert "FOLLOW_UP_SCHEDULED" in actions
    assert "NOTES_UPDATED" in actions
    assert "INTERVENTION_COMPLETED" in actions
    assert "INTERVENTION_REOPENED" in actions

    # 9. Verify GET /api/ps3/students/{student_id}/interventions
    stu_intr_resp = client.get(f"/api/ps3/students/{student_id}/interventions")
    assert stu_intr_resp.status_code == 200
    stu_intr_data = stu_intr_resp.json()["data"]
    assert stu_intr_data["student_id"] == student_id
    assert any(item["id"] == intr_id for item in stu_intr_data["items"])
    assert stu_intr_data["status_counts"]["total"] == stu_intr_data["total"]

    # Confirm history rows remain persisted in SQLite
    hist_count = test_db_session.scalar(
        select(InterventionHistory.id).where(InterventionHistory.intervention_id == intr_id)
    )
    assert hist_count is not None


def test_intervention_validation_and_not_found_errors(client: TestClient) -> None:
    """Validate 404/422 handling on invalid student IDs, prediction IDs, intervention IDs, and status."""
    # Missing student on create
    res_missing_stu = client.post(
        "/api/ps3/interventions",
        json={
            "student_id": "NO-SUCH-STU",
            "intervention_type": "advisor_outreach",
            "recommended_action": "Reach out to student.",
        },
    )
    assert res_missing_stu.status_code == 404
    assert res_missing_stu.json()["errors"][0]["code"] == "STUDENT_NOT_FOUND"

    # Missing intervention on GET/PATCH/history
    assert client.get("/api/ps3/interventions/99999").status_code == 404
    assert (
        client.patch("/api/ps3/interventions/99999", json={"version": 1, "notes": "test"}).status_code
        == 404
    )
    assert client.get("/api/ps3/interventions/99999/history").status_code == 404
    assert client.get("/api/ps3/students/NO-SUCH-STU/interventions").status_code == 404

    # Seed 2 students and check prediction_id mismatch
    client.post("/api/ps3/data/seed-synthetic?num_records=210&seed=7")
    students = client.get("/api/ps3/students?limit=2").json()["data"]["items"]
    s1, s2 = students[0]["student_id"], students[1]["student_id"]

    # Invalid prediction_id
    bad_pred = client.post(
        "/api/ps3/interventions",
        json={
            "student_id": s1,
            "prediction_id": 99999,
            "intervention_type": "tutoring",
            "recommended_action": "Assign tutor.",
        },
    )
    assert bad_pred.status_code == 404
    assert bad_pred.json()["errors"][0]["code"] == "PREDICTION_NOT_FOUND"

    # Invalid status enum on create -> 422
    bad_status = client.post(
        "/api/ps3/interventions",
        json={
            "student_id": s1,
            "intervention_type": "tutoring",
            "recommended_action": "Assign tutor.",
            "status": "BOGUS_STATUS",
        },
    )
    assert bad_status.status_code == 422


def test_pagination_beyond_500_and_combined_search_risk_filters(client: TestClient) -> None:
    """Verify full-cohort summary counts, >500 student pagination, and combined server-side filtering."""
    # Seed 540 synthetic students (>= 500 threshold from Phase 3)
    _seed_model_and_predictions(client, num_records=540)

    # Full-cohort risk distribution in /data/summary covers all 540 students (not capped at 500)
    summary = client.get("/api/ps3/data/summary").json()["data"]
    assert summary["total_students"] == 540
    dist = summary["latest_risk_distribution"]
    assert dist["scored_students"] == 540
    assert dist["low"] + dist["medium"] + dist["high"] == 540

    # Paginate beyond record 500 using page & page_size
    page_27 = client.get("/api/ps3/students?page=27&page_size=20&sort_by=student_id&sort_order=asc")
    assert page_27.status_code == 200
    p27_data = page_27.json()["data"]
    assert p27_data["total"] == 540
    assert p27_data["page"] == 27
    assert p27_data["page_size"] == 20
    assert p27_data["total_pages"] == 27
    assert p27_data["has_previous"] is True
    assert p27_data["has_next"] is False
    assert len(p27_data["items"]) == 20
    assert p27_data["items"][0]["latest_risk_level"] in {"low", "medium", "high"}

    # Combined filters: search substring + risk_level + is_synthetic + sort_by=risk_score
    high_search = client.get(
        "/api/ps3/students?search=SYNTH-STU-05&risk_level=high&is_synthetic=true&sort_by=risk_score&sort_order=desc&page=1&page_size=10"
    )
    assert high_search.status_code == 200
    filtered = high_search.json()["data"]
    for row in filtered["items"]:
        assert "SYNTH-STU-05" in row["student_id"]
        assert row["latest_risk_level"] == "high"
        assert row["is_synthetic"] is True

    # Combined prediction search + risk_level + pagination beyond 500
    pred_page_27 = client.get("/api/ps3/predictions?latest_only=true&page=27&page_size=20")
    assert pred_page_27.status_code == 200
    assert pred_page_27.json()["data"]["total"] == 540
    assert len(pred_page_27.json()["data"]["items"]) == 20


def test_additive_sqlite_migration_on_legacy_schema(tmp_path: Path) -> None:
    """Ensure apply_additive_migrations upgrades legacy Phase 1/2 interventions tables safely."""
    legacy_db = tmp_path / "legacy.db"
    eng = create_engine(f"sqlite:///{legacy_db.as_posix()}", future=True)

    # Create pre-Phase-4 schema without priority, follow_up_date, completed_at, is_demo
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE students (
                    student_id VARCHAR(64) PRIMARY KEY,
                    is_synthetic BOOLEAN NOT NULL DEFAULT 0,
                    data_source VARCHAR(64) NOT NULL DEFAULT 'csv_upload',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE interventions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id VARCHAR(64) NOT NULL,
                    prediction_id INTEGER,
                    intervention_type VARCHAR(64) NOT NULL,
                    recommended_action TEXT NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'planned',
                    assigned_to VARCHAR(128),
                    notes TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO students VALUES ('LEG-1', 0, 'csv_upload', '2026-01-01', '2026-01-01')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO interventions (student_id, intervention_type, recommended_action, status, created_at, updated_at)
                VALUES ('LEG-1', 'advisor_outreach', 'Check in', 'pending_review', '2026-01-01', '2026-01-01')
                """
            )
        )

    apply_additive_migrations(eng)
    cols = {col["name"] for col in inspect(eng).get_columns("interventions")}
    assert {"priority", "follow_up_date", "completed_at", "is_demo"}.issubset(cols)

    # Verify existing row was preserved cleanly
    with eng.connect() as conn:
        row = conn.execute(text("SELECT student_id, status, priority FROM interventions")).first()
        assert row == ("LEG-1", "pending_review", "medium")
    eng.dispose()

