"""Tests for synthetic dataset generation (>=200 records) and ubiquitous synthetic labeling."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import services.synthetic_data as synthetic_data
from services.constants import REQUIRED_CSV_COLUMNS, TRAINING_TARGET_COLUMN
from services.csv_validator import validate_csv_bytes
from services.synthetic_data import generate_synthetic_csv_bytes, generate_synthetic_dataframe


def test_synthetic_dataset_minimum_200_and_realistic_distributions() -> None:
    with pytest.raises(ValueError):
        generate_synthetic_dataframe(num_records=150)

    df = generate_synthetic_dataframe(num_records=220, seed=7)
    assert len(df) == 220
    assert df["student_id"].is_unique
    assert all(sid.startswith("SYNTH-STU-") for sid in df["student_id"])
    assert (df["is_synthetic"] == True).all()  # noqa: E712
    assert (df["data_source"] == "synthetic_demo").all()
    for col in REQUIRED_CSV_COLUMNS:
        assert col in df.columns
    assert TRAINING_TARGET_COLUMN in df.columns
    assert set(df["dropout_label"].unique()).issubset({0, 1})
    assert df["dropout_label"].nunique() == 2

    csv_bytes, _ = generate_synthetic_csv_bytes(num_records=220, seed=7)
    validation = validate_csv_bytes(csv_bytes, filename="synthetic_demo_students.csv")
    assert validation.summary.is_valid is True
    assert validation.summary.is_synthetic_detected is True
    assert validation.summary.has_training_target is True


def test_seed_synthetic_endpoint_labels_everything(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        synthetic_data,
        "DEFAULT_SYNTHETIC_CSV_PATH",
        tmp_path / "test_synthetic_demo_students.csv",
    )
    resp = client.post("/api/ps3/data/seed-synthetic?num_records=210&seed=42")
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["ingested_rows"] == 210
    assert body["data"]["is_synthetic"] is True
    assert body["data"]["data_source"] == "synthetic_demo"
    assert body["data"]["synthetic_label"] == "SYNTHETIC_DEMO_DATA"
    assert body["meta"]["contains_synthetic_data"] is True
    assert "synthetic" in body["meta"]["synthetic_notice"].lower()

    summary_resp = client.get("/api/ps3/data/summary")
    assert summary_resp.status_code == 200
    summary_data = summary_resp.json()["data"]
    assert summary_data["total_students"] == 210
    assert summary_data["synthetic_students"] == 210
    assert summary_data["real_students"] == 0
    assert summary_data["contains_synthetic_data"] is True
    assert "synthetic" in summary_data["synthetic_data_notice"].lower()

    list_resp = client.get("/api/ps3/students?limit=5")
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["meta"]["contains_synthetic_data"] is True
    assert list_body["data"]["synthetic_count_in_page"] == 5
    assert list_body["data"]["items"][0]["is_synthetic"] is True
    assert list_body["data"]["items"][0]["synthetic_label"] == "SYNTHETIC_DEMO_RECORD"

    first_sid = list_body["data"]["items"][0]["student_id"]
    detail_resp = client.get(f"/api/ps3/students/{first_sid}")
    assert detail_resp.status_code == 200
    detail_body = detail_resp.json()
    assert detail_body["data"]["is_synthetic"] is True
    assert detail_body["data"]["synthetic_label"] == "SYNTHETIC_DEMO_RECORD"
    assert "SYNTHETIC DEMO RECORD" in detail_body["message"]

