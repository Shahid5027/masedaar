"""Tests for student list, student detail, shared student_id preservation, and 404 handling."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.db_models import Intervention, Prediction
from tests.conftest import build_csv_bytes, sample_valid_rows


def test_list_and_filter_students(client: TestClient) -> None:
    csv_bytes = build_csv_bytes(sample_valid_rows(include_dropout_label=True))
    client.post(
        "/api/ps3/data/upload",
        files={"file": ("students.csv", csv_bytes, "text/csv")},
    )

    resp = client.get("/api/ps3/students?limit=10&offset=0&sort_by=attendance_rate&sort_order=asc")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["total"] == 2
    items = body["data"]["items"]
    assert [item["student_id"] for item in items] == ["STU-1002", "STU-1001"]
    # Verify dropout_label never leaks into inference feature payload
    assert "dropout_label" not in items[0]["latest_features"]
    assert items[0]["prediction_count"] == 0
    assert items[0]["intervention_count"] == 0

    filtered = client.get("/api/ps3/students?min_failures=2")
    assert filtered.status_code == 200
    assert filtered.json()["data"]["total"] == 1
    assert filtered.json()["data"]["items"][0]["student_id"] == "STU-1002"


def test_get_student_detail_and_not_found(client: TestClient, test_db_session: Session) -> None:
    csv_bytes = build_csv_bytes(sample_valid_rows(include_dropout_label=True))
    client.post(
        "/api/ps3/data/upload",
        files={"file": ("students.csv", csv_bytes, "text/csv")},
    )

    detail_resp = client.get("/api/ps3/students/STU-1002")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["student_id"] == "STU-1002"
    assert detail["is_synthetic"] is False
    assert detail["latest_features"]["attendance_rate"] == 58.0
    assert "dropout_label" not in detail["latest_features"]
    assert detail["has_training_target_record"] is True
    assert detail["predictions"] == []
    assert detail["interventions"] == []

    # Insert real Prediction and Intervention rows and confirm endpoint returns them directly
    now = datetime.now(timezone.utc)
    pred = Prediction(
        student_id="STU-1002",
        snapshot_id=detail["latest_features"]["snapshot_id"],
        risk_score=0.82,
        risk_level="high",
        model_version="rf-test-v1",
        top_risk_factors={"attendance_rate": -0.4},
        is_synthetic_input=False,
        predicted_at=now,
    )
    test_db_session.add(pred)
    test_db_session.flush()
    test_db_session.add(
        Intervention(
            student_id="STU-1002",
            prediction_id=pred.id,
            intervention_type="advisor_outreach",
            recommended_action="Schedule advisor check-in within 48 hours.",
            status="planned",
            created_at=now,
            updated_at=now,
        )
    )
    test_db_session.commit()

    updated_detail = client.get("/api/ps3/students/STU-1002").json()["data"]
    assert len(updated_detail["predictions"]) == 1
    assert updated_detail["predictions"][0]["risk_score"] == 0.82
    assert len(updated_detail["interventions"]) == 1
    assert updated_detail["interventions"][0]["intervention_type"] == "advisor_outreach"

    missing_resp = client.get("/api/ps3/students/NON-EXISTENT-999")
    assert missing_resp.status_code == 404
    missing_body = missing_resp.json()
    assert missing_body["status"] == "error"
    assert missing_body["errors"][0]["code"] == "STUDENT_NOT_FOUND"

