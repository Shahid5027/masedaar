"""End-to-end API and DB persistence tests for Phase 2 predictions and explanations."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import config
from models.db_models import Intervention, Prediction, Student
from tests.conftest import build_csv_bytes


def _setup_model_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = config.get_settings()
    monkeypatch.setattr(settings, "model_artifacts_dir", str(tmp_path / "artifacts" / "models"))


def test_predictions_run_query_and_explanation_end_to_end(
    client: TestClient,
    test_db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_model_dir(monkeypatch, tmp_path)

    # Running predictions before training a model returns 404
    no_model_resp = client.post("/api/ps3/predictions/run")
    assert no_model_resp.status_code == 404
    assert no_model_resp.json()["errors"][0]["code"] == "MODEL_NOT_TRAINED"

    # Train demo model (uses synthetic fallback)
    train_resp = client.post("/api/ps3/model/train")
    assert train_resp.status_code == 200
    model_version = train_resp.json()["data"]["model_version"]

    # Upload 2 distinct real student profiles (without dropout_label)
    rows = [
        {
            "student_id": "PRED-LOW-001",
            "attendance_rate": 96.0,
            "average_grade": 91.0,
            "late_assignments": 0,
            "missing_assignments": 0,
            "lms_logins_30d": 48,
            "engagement_change_pct": 18.0,
            "previous_failure_count": 0,
        },
        {
            "student_id": "PRED-HIGH-002",
            "attendance_rate": 38.0,
            "average_grade": 39.0,
            "late_assignments": 6,
            "missing_assignments": 7,
            "lms_logins_30d": 3,
            "engagement_change_pct": -70.0,
            "previous_failure_count": 3,
        },
    ]
    upload_resp = client.post(
        "/api/ps3/data/upload",
        files={"file": ("infer_students.csv", build_csv_bytes(rows), "text/csv")},
    )
    assert upload_resp.status_code == 201

    # Explanation before prediction run returns 404 PREDICTION_NOT_FOUND
    pre_exp = client.get("/api/ps3/students/PRED-HIGH-002/explanation")
    assert pre_exp.status_code == 404
    assert pre_exp.json()["errors"][0]["code"] == "PREDICTION_NOT_FOUND"

    # Run predictions across uploaded students
    run_resp = client.post("/api/ps3/predictions/run")
    assert run_resp.status_code == 200
    run_body = run_resp.json()
    assert run_body["status"] == "success"
    run_data = run_body["data"]
    assert run_data["model_version"] == model_version
    assert run_data["total_predicted"] == 2
    assert run_data["interventions_persisted"] > 0

    by_sid = {item["student_id"]: item for item in run_data["predictions"]}
    low_pred = by_sid["PRED-LOW-001"]
    high_pred = by_sid["PRED-HIGH-002"]

    # Verify required Task 3 fields and genuine feature-driven probability spread
    for item in (low_pred, high_pred):
        assert item["prediction_id"] > 0
        assert 0.0 <= item["risk_probability"] <= 1.0
        assert item["risk_level"] in {"low", "medium", "high"}
        assert item["model_version"] == model_version
        assert "prediction_timestamp" in item
        assert item["is_demo"] is True  # Demo model trained on synthetic data
        assert item["threshold_profile"] == "demo_default"

    assert high_pred["risk_probability"] > low_pred["risk_probability"]
    assert high_pred["risk_level"] == "high"
    assert low_pred["risk_level"] == "low"

    # Verify DB persistence & preserved shared student_id (no duplicate students)
    assert test_db_session.scalar(select(func.count(Student.student_id))) == 2
    assert test_db_session.scalar(select(func.count(Prediction.id))) == 2
    assert test_db_session.scalar(select(func.count(Intervention.id))) > 0

    # Query GET /api/ps3/predictions
    list_resp = client.get("/api/ps3/predictions?risk_level=high")
    assert list_resp.status_code == 200
    list_data = list_resp.json()["data"]
    assert list_data["total"] == 1
    assert list_data["items"][0]["student_id"] == "PRED-HIGH-002"

    # Query GET /api/ps3/students/{student_id}/explanation
    exp_resp = client.get("/api/ps3/students/PRED-HIGH-002/explanation")
    assert exp_resp.status_code == 200
    exp_data = exp_resp.json()["data"]
    assert exp_data["student_id"] == "PRED-HIGH-002"
    assert exp_data["prediction"]["risk_level"] == "high"
    assert len(exp_data["prediction"]["explanation"]["indicators"]) >= 3
    assert "causation" in exp_data["prediction"]["explanation"]["causation_disclaimer"].lower()
    assert len(exp_data["prediction"]["recommended_interventions"]) >= 2
    assert "human" in exp_data["human_review_notice"].lower()

    # Verify Phase 1 student detail endpoint also exposes the newly persisted prediction & interventions
    detail_resp = client.get("/api/ps3/students/PRED-HIGH-002")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()["data"]
    assert len(detail_data["predictions"]) == 1
    assert len(detail_data["interventions"]) >= 2

    # Unknown student returns 404 STUDENT_NOT_FOUND
    missing_student_resp = client.get("/api/ps3/students/UNKNOWN-999/explanation")
    assert missing_student_resp.status_code == 404
    assert missing_student_resp.json()["errors"][0]["code"] == "STUDENT_NOT_FOUND"

