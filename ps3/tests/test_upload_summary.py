"""Tests for CSV upload, atomic persistence, dropout_label separation, and data summary."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.db_models import ActivitySnapshot, Student, TrainingTarget
from tests.conftest import build_csv_bytes, sample_valid_rows


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/api/ps3/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["database_connected"] is True
    assert body["data"]["database_dialect"] == "sqlite"


def test_upload_valid_csv_and_separate_dropout_label(
    client: TestClient, test_db_session: Session
) -> None:
    csv_bytes = build_csv_bytes(sample_valid_rows(include_dropout_label=True))
    resp = client.post(
        "/api/ps3/data/upload",
        files={"file": ("cohort_fall.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["ingested_rows"] == 2
    assert body["data"]["new_students"] == 2
    assert body["data"]["updated_students"] == 0
    assert body["data"]["snapshots_created"] == 2
    assert body["data"]["training_targets_stored"] == 2
    assert body["data"]["has_training_target"] is True
    assert body["data"]["is_synthetic"] is False

    # Verify dropout_label is stored in training_targets, NOT on ActivitySnapshot
    assert test_db_session.scalar(select(func.count(Student.student_id))) == 2
    assert test_db_session.scalar(select(func.count(ActivitySnapshot.id))) == 2
    assert test_db_session.scalar(select(func.count(TrainingTarget.id))) == 2
    assert not hasattr(ActivitySnapshot, "dropout_label")


def test_upload_invalid_csv_is_atomic(client: TestClient, test_db_session: Session) -> None:
    rows = sample_valid_rows()
    rows[1]["attendance_rate"] = 150.0  # Invalid row 2; row 1 is valid
    csv_bytes = build_csv_bytes(rows)
    resp = client.post(
        "/api/ps3/data/upload",
        files={"file": ("partial_bad.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["status"] == "error"
    assert body["data"] is None
    assert body["errors"][0]["code"] == "INVALID_ATTENDANCE_RATE"

    # Zero partial inserts allowed
    assert test_db_session.scalar(select(func.count(Student.student_id))) == 0
    assert test_db_session.scalar(select(func.count(ActivitySnapshot.id))) == 0


def test_reupload_preserves_shared_student_id_and_appends_snapshot(
    client: TestClient, test_db_session: Session
) -> None:
    rows_v1 = sample_valid_rows()
    resp1 = client.post(
        "/api/ps3/data/upload",
        files={"file": ("week1.csv", build_csv_bytes(rows_v1), "text/csv")},
    )
    assert resp1.status_code == 201

    rows_v2 = sample_valid_rows()
    rows_v2[0]["attendance_rate"] = 88.0
    resp2 = client.post(
        "/api/ps3/data/upload",
        files={"file": ("week2.csv", build_csv_bytes(rows_v2), "text/csv")},
    )
    assert resp2.status_code == 201
    data2 = resp2.json()["data"]
    assert data2["new_students"] == 0
    assert data2["updated_students"] == 2
    assert data2["snapshots_created"] == 2
    assert test_db_session.scalar(select(func.count(Student.student_id))) == 2
    assert test_db_session.scalar(select(func.count(ActivitySnapshot.id))) == 4


def test_summary_endpoint_computes_real_statistics(client: TestClient) -> None:
    empty_summary = client.get("/api/ps3/data/summary")
    assert empty_summary.status_code == 200
    empty_data = empty_summary.json()["data"]
    assert empty_data["total_students"] == 0
    assert empty_data["contains_synthetic_data"] is False
    assert empty_data["feature_statistics"] == {}

    csv_bytes = build_csv_bytes(sample_valid_rows(include_dropout_label=True))
    client.post(
        "/api/ps3/data/upload",
        files={"file": ("real_cohort.csv", csv_bytes, "text/csv")},
    )

    summary_resp = client.get("/api/ps3/data/summary")
    assert summary_resp.status_code == 200
    data = summary_resp.json()["data"]
    assert data["total_students"] == 2
    assert data["real_students"] == 2
    assert data["synthetic_students"] == 0
    assert data["contains_synthetic_data"] is False
    assert data["total_predictions"] == 0
    assert data["total_interventions"] == 0
    assert data["training_targets_summary"]["total_labeled_snapshots"] == 2
    assert data["training_targets_summary"]["dropout_count"] == 1
    assert data["training_targets_summary"]["dropout_rate_pct"] == 50.0
    assert data["feature_statistics"]["attendance_rate"]["min"] == 58.0
    assert data["feature_statistics"]["attendance_rate"]["max"] == 93.5
    assert data["feature_statistics"]["attendance_rate"]["mean"] == 75.75

