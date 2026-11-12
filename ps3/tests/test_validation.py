"""Tests for CSV validation rules and consistent error reporting."""

from fastapi.testclient import TestClient

from tests.conftest import build_csv_bytes, sample_valid_rows


def _assert_consistent_envelope(payload: dict, expected_status: str) -> None:
    assert payload["status"] == expected_status
    assert "message" in payload and isinstance(payload["message"], str)
    assert "data" in payload
    assert "errors" in payload and isinstance(payload["errors"], list)
    assert payload["meta"]["module"] == "ps3"
    assert "timestamp" in payload["meta"]


def test_validate_valid_csv_without_target(client: TestClient) -> None:
    csv_bytes = build_csv_bytes(sample_valid_rows(include_dropout_label=False))
    resp = client.post(
        "/api/ps3/data/validate",
        files={"file": ("students.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    _assert_consistent_envelope(body, "success")
    assert body["data"]["is_valid"] is True
    assert body["data"]["total_rows"] == 2
    assert body["data"]["valid_rows"] == 2
    assert body["data"]["invalid_rows"] == 0
    assert body["data"]["has_training_target"] is False
    assert body["errors"] == []


def test_validate_valid_csv_with_training_target(client: TestClient) -> None:
    csv_bytes = build_csv_bytes(sample_valid_rows(include_dropout_label=True))
    resp = client.post(
        "/api/ps3/data/validate",
        files={"file": ("train.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    _assert_consistent_envelope(body, "success")
    assert body["data"]["is_valid"] is True
    assert body["data"]["has_training_target"] is True
    assert body["data"]["training_target_column"] == "dropout_label"


def test_validate_missing_required_columns(client: TestClient) -> None:
    rows = [{"student_id": "STU-1", "attendance_rate": 90.0}]
    csv_bytes = build_csv_bytes(rows)
    resp = client.post(
        "/api/ps3/data/validate",
        files={"file": ("missing_cols.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["is_valid"] is False
    assert "average_grade" in body["data"]["missing_columns"]
    assert body["errors"][0]["code"] == "MISSING_REQUIRED_COLUMNS"


def test_validate_duplicate_student_ids(client: TestClient) -> None:
    rows = sample_valid_rows()
    rows[1]["student_id"] = "STU-1001"
    csv_bytes = build_csv_bytes(rows)
    resp = client.post(
        "/api/ps3/data/validate",
        files={"file": ("dups.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["is_valid"] is False
    codes = [err["code"] for err in body["errors"]]
    assert "DUPLICATE_STUDENT_ID" in codes
    assert body["errors"][0]["row"] == 2
    assert "STU-1001" in body["errors"][0]["message"]


def test_validate_missing_values(client: TestClient) -> None:
    rows = sample_valid_rows()
    rows[0]["attendance_rate"] = ""
    rows[1]["average_grade"] = "N/A"
    csv_bytes = build_csv_bytes(rows)
    resp = client.post(
        "/api/ps3/data/validate",
        files={"file": ("missing_vals.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["is_valid"] is False
    assert body["data"]["invalid_rows"] == 2
    assert all(err["code"] == "MISSING_VALUE" for err in body["errors"])


def test_validate_invalid_attendance_percentages(client: TestClient) -> None:
    rows = sample_valid_rows()
    rows[0]["attendance_rate"] = -5.0
    rows[1]["attendance_rate"] = 104.2
    csv_bytes = build_csv_bytes(rows)
    resp = client.post(
        "/api/ps3/data/validate",
        files={"file": ("bad_att.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["is_valid"] is False
    assert [err["code"] for err in body["errors"]] == [
        "INVALID_ATTENDANCE_RATE",
        "INVALID_ATTENDANCE_RATE",
    ]


def test_validate_negative_and_fractional_assignment_counts(client: TestClient) -> None:
    rows = sample_valid_rows()
    rows[0]["late_assignments"] = -1
    rows[0]["missing_assignments"] = -3
    rows[1]["lms_logins_30d"] = -10
    rows[1]["previous_failure_count"] = 1.5
    csv_bytes = build_csv_bytes(rows)
    resp = client.post(
        "/api/ps3/data/validate",
        files={"file": ("bad_counts.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["is_valid"] is False
    codes = {err["column"]: err["code"] for err in body["errors"]}
    assert codes["late_assignments"] == "NEGATIVE_ASSIGNMENT_COUNT"
    assert codes["missing_assignments"] == "NEGATIVE_ASSIGNMENT_COUNT"
    assert codes["lms_logins_30d"] == "NEGATIVE_COUNT"
    assert codes["previous_failure_count"] == "INVALID_INTEGER_COUNT"


def test_validate_invalid_grades_and_engagement_and_dropout_label(client: TestClient) -> None:
    rows = sample_valid_rows(include_dropout_label=True)
    rows[0]["average_grade"] = 110.0
    rows[0]["engagement_change_pct"] = -125.0
    rows[1]["average_grade"] = -1.0
    rows[1]["dropout_label"] = 2
    csv_bytes = build_csv_bytes(rows)
    resp = client.post(
        "/api/ps3/data/validate",
        files={"file": ("bad_grades.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["is_valid"] is False
    codes = [err["code"] for err in body["errors"]]
    assert "INVALID_GRADE" in codes
    assert "INVALID_ENGAGEMENT_CHANGE" in codes
    assert "INVALID_DROPOUT_LABEL" in codes


def test_validate_empty_and_non_csv_files(client: TestClient) -> None:
    empty_resp = client.post(
        "/api/ps3/data/validate",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert empty_resp.status_code == 200
    assert empty_resp.json()["data"]["is_valid"] is False
    assert empty_resp.json()["errors"][0]["code"] == "EMPTY_FILE"

    bad_ext_resp = client.post(
        "/api/ps3/data/validate",
        files={"file": ("payload.json", b"{}", "application/json")},
    )
    assert bad_ext_resp.status_code == 400
    _assert_consistent_envelope(bad_ext_resp.json(), "error")
    assert bad_ext_resp.json()["errors"][0]["code"] == "INVALID_FILE_TYPE"


def test_validate_duplicate_header_columns(client: TestClient) -> None:
    raw = (
        b"student_id,attendance_rate,attendance_rate,average_grade,late_assignments,"
        b"missing_assignments,lms_logins_30d,engagement_change_pct,previous_failure_count\n"
        b"STU-1,90,90,80,0,0,10,0,0\n"
    )
    resp = client.post(
        "/api/ps3/data/validate",
        files={"file": ("dup_header.csv", raw, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["is_valid"] is False
    assert body["errors"][0]["code"] == "DUPLICATE_OR_BLANK_COLUMN"

