"""Tests for Scikit-learn Random Forest training, validation, persistence, and metrics."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import config
from models.schemas import TrainModelRequest
from services.ml_pipeline import load_trained_pipeline, train_from_dataframe
from services.response import PS3APIError
from services.synthetic_data import generate_synthetic_dataframe
from tests.conftest import build_csv_bytes


def _isolated_artifacts_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    artifacts_dir = tmp_path / "artifacts" / "models"
    settings = config.get_settings()
    monkeypatch.setattr(settings, "model_artifacts_dir", str(artifacts_dir))
    return artifacts_dir


def test_train_and_metrics_with_synthetic_fallback(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolated_artifacts_dir(monkeypatch, tmp_path)

    # Metrics before training should return 404
    pre_resp = client.get("/api/ps3/model/metrics")
    assert pre_resp.status_code == 404
    assert pre_resp.json()["errors"][0]["code"] == "MODEL_NOT_TRAINED"

    # Train using synthetic fallback when DB has no real labeled records
    train_resp = client.post("/api/ps3/model/train")
    assert train_resp.status_code == 200
    body = train_resp.json()
    assert body["status"] == "success"
    assert body["meta"]["contains_synthetic_data"] is True

    data = body["data"]
    assert data["algorithm"] == "RandomForestClassifier"
    assert data["is_demo_model"] is True
    assert "synthetic" in data["evaluation_disclaimer"].lower()
    assert data["sample_count"] >= 200
    assert data["train_count"] + data["test_count"] == data["sample_count"]

    eval_m = data["evaluation"]
    assert 0.0 <= eval_m["accuracy"] <= 1.0
    assert 0.0 <= eval_m["precision"] <= 1.0
    assert 0.0 <= eval_m["recall"] <= 1.0
    assert 0.0 <= eval_m["f1_score"] <= 1.0
    assert eval_m["roc_auc"] is not None and 0.0 <= eval_m["roc_auc"] <= 1.0
    assert len(eval_m["confusion_matrix"]["matrix"]) == 2
    assert eval_m["class_distribution"]["total_samples"] == data["sample_count"]
    assert set(eval_m["feature_importances"].keys()) == set(data["feature_columns"])

    # GET /model/metrics returns persisted evaluation metrics
    metrics_resp = client.get("/api/ps3/model/metrics")
    assert metrics_resp.status_code == 200
    assert metrics_resp.json()["data"]["model_version"] == data["model_version"]
    assert metrics_resp.json()["data"]["evaluation"]["accuracy"] == eval_m["accuracy"]


def test_train_prefers_real_labeled_data_over_synthetic(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _isolated_artifacts_dir(monkeypatch, tmp_path)

    # Upload 24 real labeled records covering both classes
    rows = []
    for idx in range(24):
        is_drop = 1 if idx % 2 == 1 else 0
        rows.append(
            {
                "student_id": f"REAL-STU-{idx:03d}",
                "attendance_rate": 48.0 + idx if is_drop else 88.0 + (idx % 10),
                "average_grade": 45.0 + idx if is_drop else 80.0 + (idx % 15),
                "late_assignments": 5 if is_drop else 0,
                "missing_assignments": 4 if is_drop else 0,
                "lms_logins_30d": 5 if is_drop else 35,
                "engagement_change_pct": -40.0 if is_drop else 12.0,
                "previous_failure_count": 2 if is_drop else 0,
                "dropout_label": is_drop,
            }
        )
    upload_resp = client.post(
        "/api/ps3/data/upload",
        files={"file": ("real_labeled.csv", build_csv_bytes(rows), "text/csv")},
    )
    assert upload_resp.status_code == 201

    train_resp = client.post("/api/ps3/model/train", json={"dataset_mode": "auto"})
    assert train_resp.status_code == 200
    data = train_resp.json()["data"]
    assert data["is_demo_model"] is False
    assert data["training_source"] == "real_database"
    assert data["sample_count"] == 24


def test_missing_training_data_and_invalid_labels(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts_dir = _isolated_artifacts_dir(monkeypatch, tmp_path)

    # Real-only mode on empty DB fails cleanly
    missing_resp = client.post("/api/ps3/model/train", json={"dataset_mode": "real_only"})
    assert missing_resp.status_code == 422
    assert missing_resp.json()["status"] == "error"
    assert missing_resp.json()["errors"][0]["code"] == "MISSING_TRAINING_DATA"

    # Auto mode with fallback disabled fails cleanly
    no_fb_resp = client.post("/api/ps3/model/train", json={"allow_synthetic_fallback": False})
    assert no_fb_resp.status_code == 422
    assert no_fb_resp.json()["errors"][0]["code"] == "MISSING_TRAINING_DATA"

    base_df = generate_synthetic_dataframe(num_records=200, seed=11).head(20).copy()

    # Empty dataframe
    with pytest.raises(PS3APIError) as exc_empty:
        train_from_dataframe(base_df.iloc[0:0], "test", True, artifacts_dir)
    assert exc_empty.value.errors[0].code == "MISSING_TRAINING_DATA"

    # Too few rows
    with pytest.raises(PS3APIError) as exc_small:
        train_from_dataframe(base_df.head(5), "test", True, artifacts_dir)
    assert exc_small.value.errors[0].code == "INSUFFICIENT_TRAINING_DATA"

    # Invalid non-binary labels
    bad_label_df = base_df.copy()
    bad_label_df.loc[bad_label_df.index[0], "dropout_label"] = 2
    with pytest.raises(PS3APIError) as exc_bad_lbl:
        train_from_dataframe(bad_label_df, "test", True, artifacts_dir)
    assert exc_bad_lbl.value.errors[0].code == "INVALID_TRAINING_LABELS"

    # Missing label
    missing_label_df = base_df.copy()
    missing_label_df.loc[missing_label_df.index[0], "dropout_label"] = np.nan
    with pytest.raises(PS3APIError) as exc_nan_lbl:
        train_from_dataframe(missing_label_df, "test", True, artifacts_dir)
    assert exc_nan_lbl.value.errors[0].code == "INVALID_TRAINING_LABELS"

    # Single class only
    single_class_df = base_df.copy()
    single_class_df["dropout_label"] = 0
    with pytest.raises(PS3APIError) as exc_single:
        train_from_dataframe(single_class_df, "test", True, artifacts_dir)
    assert exc_single.value.errors[0].code == "MISSING_TARGET_CLASS"


def test_model_imputation_and_artifact_persistence(
    client: TestClient,
    test_db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts_dir = _isolated_artifacts_dir(monkeypatch, tmp_path)

    # Verify imputation handles NaN feature values without crashing
    df_with_nans = generate_synthetic_dataframe(num_records=200, seed=17).head(40).copy()
    df_with_nans.loc[df_with_nans.index[0], "attendance_rate"] = np.nan
    df_with_nans.loc[df_with_nans.index[3], "lms_logins_30d"] = np.nan

    version, artifact_path, fitted_pipe, _eval, _hp, _tr, _te = train_from_dataframe(
        df_with_nans, "test_imputation", True, artifacts_dir
    )
    assert artifact_path.exists()

    # Trained via API and reloaded from disk via load_trained_pipeline
    train_resp = client.post("/api/ps3/model/train")
    assert train_resp.status_code == 200
    trained_version = train_resp.json()["data"]["model_version"]

    model_row, loaded_pipe, importances = load_trained_pipeline(test_db_session, trained_version)
    assert model_row.model_version == trained_version
    assert len(importances) == 7

    sample_X = pd.DataFrame(
        [
            {
                "attendance_rate": np.nan,
                "average_grade": 68.0,
                "late_assignments": 2,
                "missing_assignments": 1,
                "lms_logins_30d": 15,
                "engagement_change_pct": -10.0,
                "previous_failure_count": 0,
            }
        ]
    )
    probs = loaded_pipe.predict_proba(sample_X)[0]
    assert np.isclose(float(np.sum(probs)), 1.0)
    assert fitted_pipe is not None and version

