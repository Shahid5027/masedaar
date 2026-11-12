"""Scikit-learn Random Forest training, evaluation, and artifact persistence service."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from config import get_settings
from models.db_models import ActivitySnapshot, TrainedModel, TrainingTarget
from models.schemas import (
    ClassDistributionOut,
    ConfusionMatrixOut,
    ErrorDetail,
    ModelEvaluationMetrics,
    ModelMetricsData,
    TrainModelRequest,
)
from services.constants import (
    MODEL_FEATURE_COLUMNS,
    REAL_METRICS_DISCLAIMER,
    SYNTHETIC_METRICS_DISCLAIMER,
    TRAINING_TARGET_COLUMN,
)
from services.response import PS3APIError
from services.synthetic_data import DEFAULT_SYNTHETIC_CSV_PATH

MIN_STRATIFIED_DATASET_ROWS = 10


def _query_labeled_snapshots_df(
    db: Session,
    is_synthetic: Optional[bool] = None,
) -> pd.DataFrame:
    """Load labeled training snapshots from DB without touching unlabelled records."""
    stmt = (
        select(
            ActivitySnapshot.attendance_rate,
            ActivitySnapshot.average_grade,
            ActivitySnapshot.late_assignments,
            ActivitySnapshot.missing_assignments,
            ActivitySnapshot.lms_logins_30d,
            ActivitySnapshot.engagement_change_pct,
            ActivitySnapshot.previous_failure_count,
            TrainingTarget.dropout_label,
        )
        .join(TrainingTarget, TrainingTarget.snapshot_id == ActivitySnapshot.id)
    )
    if is_synthetic is not None:
        stmt = stmt.where(TrainingTarget.is_synthetic.is_(is_synthetic))

    rows = db.execute(stmt).all()
    cols = [*MODEL_FEATURE_COLUMNS, TRAINING_TARGET_COLUMN]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


def _validate_and_prepare_training_df(
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.Series]:
    """Validate training dataframe columns, missing/invalid labels, and class balance."""
    if df is None or df.empty:
        raise PS3APIError(
            status_code=422,
            message="No training data available to fit the model.",
            errors=[
                ErrorDetail(
                    code="MISSING_TRAINING_DATA",
                    message="Training dataset is empty. Upload labeled data or seed synthetic demo records.",
                )
            ],
        )

    missing_cols = [
        col for col in (*MODEL_FEATURE_COLUMNS, TRAINING_TARGET_COLUMN) if col not in df.columns
    ]
    if missing_cols:
        raise PS3APIError(
            status_code=422,
            message=f"Training dataset is missing required column(s): {', '.join(missing_cols)}.",
            errors=[
                ErrorDetail(
                    code="MISSING_TRAINING_COLUMNS",
                    message=f"Missing required column(s): {', '.join(missing_cols)}.",
                )
            ],
        )

    if len(df) < MIN_STRATIFIED_DATASET_ROWS:
        raise PS3APIError(
            status_code=422,
            message=(
                f"Insufficient training data: found {len(df)} labeled row(s), "
                f"require at least {MIN_STRATIFIED_DATASET_ROWS}."
            ),
            errors=[
                ErrorDetail(
                    code="INSUFFICIENT_TRAINING_DATA",
                    message=f"Need at least {MIN_STRATIFIED_DATASET_ROWS} labeled rows; found {len(df)}.",
                )
            ],
        )

    raw_labels = df[TRAINING_TARGET_COLUMN]
    if raw_labels.isna().any():
        raise PS3APIError(
            status_code=422,
            message="Training target 'dropout_label' contains missing values.",
            errors=[
                ErrorDetail(
                    code="INVALID_TRAINING_LABELS",
                    column=TRAINING_TARGET_COLUMN,
                    message="dropout_label must not contain null/missing values.",
                )
            ],
        )

    numeric_labels = pd.to_numeric(raw_labels, errors="coerce")
    if numeric_labels.isna().any() or not np.all(np.isin(numeric_labels.to_numpy(), [0, 1])):
        raise PS3APIError(
            status_code=422,
            message="Training target 'dropout_label' must contain only binary values 0 and 1.",
            errors=[
                ErrorDetail(
                    code="INVALID_TRAINING_LABELS",
                    column=TRAINING_TARGET_COLUMN,
                    message="Invalid non-binary values detected in dropout_label.",
                )
            ],
        )

    y = numeric_labels.astype(int)
    class_counts = y.value_counts().to_dict()
    if 0 not in class_counts or 1 not in class_counts:
        raise PS3APIError(
            status_code=422,
            message="Training dataset must include both classes (0 = retained, 1 = dropout).",
            errors=[
                ErrorDetail(
                    code="MISSING_TARGET_CLASS",
                    column=TRAINING_TARGET_COLUMN,
                    message=f"Found class counts {class_counts}; both 0 and 1 are required.",
                )
            ],
        )

    if min(class_counts.values()) < 2:
        raise PS3APIError(
            status_code=422,
            message="Each target class (0 and 1) needs at least 2 samples for stratified evaluation.",
            errors=[
                ErrorDetail(
                    code="INSUFFICIENT_CLASS_SAMPLES",
                    column=TRAINING_TARGET_COLUMN,
                    message=f"Class counts {class_counts} too small for stratified train/test split.",
                )
            ],
        )

    # Strictly select ONLY model input features (prevents target leakage).
    X = df[list(MODEL_FEATURE_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    return X, y


def select_training_dataset(
    db: Session,
    dataset_mode: str = "auto",
    allow_synthetic_fallback: bool = True,
) -> Tuple[pd.DataFrame, str, bool]:
    """Load real or synthetic labeled training data according to policy."""
    settings = get_settings()

    if dataset_mode == "real_only":
        real_df = _query_labeled_snapshots_df(db, is_synthetic=False)
        return real_df, "real_database", False

    if dataset_mode == "synthetic_only":
        synth_df = _query_labeled_snapshots_df(db, is_synthetic=True)
        if not synth_df.empty:
            return synth_df, "synthetic_demo_database", True
        if allow_synthetic_fallback and DEFAULT_SYNTHETIC_CSV_PATH.exists():
            return pd.read_csv(DEFAULT_SYNTHETIC_CSV_PATH), "synthetic_demo_csv", True
        raise PS3APIError(
            status_code=422,
            message="No synthetic labeled training dataset found in database or CSV fallback.",
            errors=[
                ErrorDetail(
                    code="MISSING_TRAINING_DATA",
                    message="Seed synthetic demo data or generate synthetic_demo_students.csv first.",
                )
            ],
        )

    # Auto mode: prefer approved real labeled records if sufficient and two-class.
    real_df = _query_labeled_snapshots_df(db, is_synthetic=False)
    if len(real_df) >= settings.min_training_samples:
        counts = real_df[TRAINING_TARGET_COLUMN].value_counts().to_dict()
        if 0 in counts and 1 in counts and min(counts.values()) >= 2:
            return real_df, "real_database", False

    if not allow_synthetic_fallback:
        return real_df, "real_database", False

    synth_df = _query_labeled_snapshots_df(db, is_synthetic=True)
    if not synth_df.empty:
        return synth_df, "synthetic_demo_database", True

    if DEFAULT_SYNTHETIC_CSV_PATH.exists():
        return pd.read_csv(DEFAULT_SYNTHETIC_CSV_PATH), "synthetic_demo_csv", True

    raise PS3APIError(
        status_code=422,
        message="No labeled training records available in database and synthetic CSV fallback was not found.",
        errors=[
            ErrorDetail(
                code="MISSING_TRAINING_DATA",
                message="Upload labeled CSV records or seed synthetic demo data before training.",
            )
        ],
    )


def train_from_dataframe(
    df: pd.DataFrame,
    training_source: str,
    is_demo_model: bool,
    artifacts_dir: Path,
    test_size: Optional[float] = None,
    n_estimators: Optional[int] = None,
    max_depth: Optional[int] = None,
    random_state: Optional[int] = None,
) -> Tuple[str, Path, Pipeline, ModelEvaluationMetrics, Dict[str, Any], int, int]:
    """Fit an imputer + RandomForestClassifier pipeline with strict train/test isolation."""
    settings = get_settings()
    resolved_test_size = test_size if test_size is not None else settings.default_test_size
    resolved_estimators = n_estimators if n_estimators is not None else settings.rf_n_estimators
    resolved_max_depth = max_depth if max_depth is not None else settings.rf_max_depth
    resolved_seed = random_state if random_state is not None else settings.rf_random_state

    X, y = _validate_and_prepare_training_df(df)

    # Guarantee stratified split feasibility even for small datasets (e.g. 10-12 rows).
    n_samples = len(X)
    effective_test_size: float | int = resolved_test_size
    if int(round(n_samples * resolved_test_size)) < 2:
        effective_test_size = max(2, int(np.ceil(0.2 * n_samples)))

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=effective_test_size,
        random_state=resolved_seed,
        stratify=y,
    )

    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=resolved_estimators,
                    max_depth=resolved_max_depth,
                    min_samples_leaf=2,
                    class_weight="balanced",
                    random_state=resolved_seed,
                    n_jobs=1,
                ),
            ),
        ]
    )
    pipeline.fit(X_train, y_train)

    classifier: RandomForestClassifier = pipeline.named_steps["classifier"]
    classes = list(classifier.classes_)
    pos_idx = classes.index(1)

    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, pos_idx]

    roc_auc_val: Optional[float] = None
    roc_auc_note: Optional[str] = None
    if len(np.unique(y_test)) == 2:
        roc_auc_val = round(float(roc_auc_score(y_test, y_prob)), 4)
    else:
        roc_auc_note = "ROC-AUC undefined because holdout test split contained only one target class."

    cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
    tn, fp, fn, tp = (int(cm[0, 0]), int(cm[0, 1]), int(cm[1, 0]), int(cm[1, 1]))

    full_counts = y.value_counts().to_dict()
    train_counts = y_train.value_counts().to_dict()
    test_counts = y_test.value_counts().to_dict()
    retained_0 = int(full_counts.get(0, 0))
    dropout_1 = int(full_counts.get(1, 0))

    importances = {
        col: round(float(imp), 4)
        for col, imp in zip(MODEL_FEATURE_COLUMNS, classifier.feature_importances_)
    }

    evaluation = ModelEvaluationMetrics(
        accuracy=round(float(accuracy_score(y_test, y_pred)), 4),
        precision=round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        recall=round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        f1_score=round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        roc_auc=roc_auc_val,
        roc_auc_note=roc_auc_note,
        confusion_matrix=ConfusionMatrixOut(
            matrix=[[tn, fp], [fn, tp]],
            tn=tn,
            fp=fp,
            fn=fn,
            tp=tp,
        ),
        class_distribution=ClassDistributionOut(
            total_samples=n_samples,
            retained_0=retained_0,
            dropout_1=dropout_1,
            dropout_rate_pct=round((dropout_1 / n_samples) * 100.0, 2),
            train_distribution={"0": int(train_counts.get(0, 0)), "1": int(train_counts.get(1, 0))},
            test_distribution={"0": int(test_counts.get(0, 0)), "1": int(test_counts.get(1, 0))},
        ),
        feature_importances=importances,
    )

    model_version = f"rf-ps3-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifacts_dir / f"{model_version}.joblib"

    hyperparameters = {
        "n_estimators": resolved_estimators,
        "max_depth": resolved_max_depth,
        "min_samples_leaf": 2,
        "class_weight": "balanced",
        "imputer_strategy": "median",
        "test_size": resolved_test_size,
        "random_state": resolved_seed,
    }

    joblib.dump(
        {
            "pipeline": pipeline,
            "model_version": model_version,
            "feature_columns": list(MODEL_FEATURE_COLUMNS),
            "feature_importances": importances,
            "is_demo_model": is_demo_model,
            "training_source": training_source,
        },
        artifact_path,
    )

    return (
        model_version,
        artifact_path,
        pipeline,
        evaluation,
        hyperparameters,
        len(X_train),
        len(X_test),
    )


def train_and_register_model(
    db: Session,
    request: TrainModelRequest,
) -> ModelMetricsData:
    """Train Random Forest pipeline from DB/synthetic data, save artifact, and persist metrics."""
    settings = get_settings()
    df, training_source, is_demo_model = select_training_dataset(
        db=db,
        dataset_mode=request.dataset_mode,
        allow_synthetic_fallback=request.allow_synthetic_fallback,
    )

    (
        model_version,
        artifact_path,
        _pipeline,
        evaluation,
        hyperparameters,
        train_count,
        test_count,
    ) = train_from_dataframe(
        df=df,
        training_source=training_source,
        is_demo_model=is_demo_model,
        artifacts_dir=settings.resolved_model_artifacts_dir,
        test_size=request.test_size,
        n_estimators=request.n_estimators,
        max_depth=request.max_depth,
        random_state=request.random_state,
    )

    trained_at = datetime.now(timezone.utc)
    metrics_payload = evaluation.model_dump(mode="json")

    try:
        db.execute(update(TrainedModel).values(is_active=False))
        model_row = TrainedModel(
            model_version=model_version,
            algorithm="RandomForestClassifier",
            artifact_path=str(artifact_path),
            feature_columns=list(MODEL_FEATURE_COLUMNS),
            training_source=training_source,
            is_demo_model=is_demo_model,
            sample_count=train_count + test_count,
            train_count=train_count,
            test_count=test_count,
            metrics=metrics_payload,
            hyperparameters=hyperparameters,
            is_active=True,
            trained_at=trained_at,
        )
        db.add(model_row)
        db.commit()
        db.refresh(model_row)
    except Exception:
        db.rollback()
        if artifact_path.exists():
            artifact_path.unlink(missing_ok=True)
        raise

    return _to_model_metrics_data(model_row)


def _to_model_metrics_data(model_row: TrainedModel) -> ModelMetricsData:
    """Convert TrainedModel ORM entity into ModelMetricsData response schema."""
    settings = get_settings()
    disclaimer = (
        SYNTHETIC_METRICS_DISCLAIMER if model_row.is_demo_model else REAL_METRICS_DISCLAIMER
    )
    return ModelMetricsData(
        model_version=model_row.model_version,
        algorithm=model_row.algorithm,
        trained_at=model_row.trained_at,
        feature_columns=list(model_row.feature_columns),
        training_source=model_row.training_source,
        is_demo_model=model_row.is_demo_model,
        evaluation_disclaimer=disclaimer,
        sample_count=model_row.sample_count,
        train_count=model_row.train_count,
        test_count=model_row.test_count,
        threshold_profile=settings.threshold_profile,
        thresholds={
            "low_max": settings.risk_threshold_medium,
            "medium_min": settings.risk_threshold_medium,
            "medium_max": settings.risk_threshold_high,
            "high_min": settings.risk_threshold_high,
        },
        hyperparameters=dict(model_row.hyperparameters),
        evaluation=ModelEvaluationMetrics(**model_row.metrics),
    )


def get_model_metrics(db: Session, model_version: Optional[str] = None) -> ModelMetricsData:
    """Fetch stored evaluation metrics for the active or requested trained model."""
    model_row = get_trained_model_record(db, model_version=model_version)
    return _to_model_metrics_data(model_row)


def get_trained_model_record(db: Session, model_version: Optional[str] = None) -> TrainedModel:
    """Retrieve a TrainedModel record or raise 404 when no model has been trained."""
    if model_version:
        stmt = select(TrainedModel).where(TrainedModel.model_version == model_version.strip())
    else:
        stmt = (
            select(TrainedModel)
            .where(TrainedModel.is_active.is_(True))
            .order_by(TrainedModel.trained_at.desc(), TrainedModel.id.desc())
        )
    model_row = db.scalars(stmt).first()
    if model_row is None:
        raise PS3APIError(
            status_code=404,
            message="No trained dropout prediction model found. Train a model via POST /api/ps3/model/train first.",
            errors=[
                ErrorDetail(
                    code="MODEL_NOT_TRAINED",
                    message="No trained model artifact exists for the requested version.",
                )
            ],
        )
    return model_row


def load_trained_pipeline(
    db: Session,
    model_version: Optional[str] = None,
) -> Tuple[TrainedModel, Pipeline, Dict[str, float]]:
    """Load persisted Scikit-learn Pipeline artifact and feature importances from disk."""
    model_row = get_trained_model_record(db, model_version=model_version)
    artifact_file = Path(model_row.artifact_path)
    if not artifact_file.exists():
        raise PS3APIError(
            status_code=404,
            message=f"Model artifact file for '{model_row.model_version}' was not found on disk.",
            errors=[
                ErrorDetail(
                    code="MODEL_ARTIFACT_MISSING",
                    message=f"Expected artifact at '{artifact_file}'. Retrain via POST /api/ps3/model/train.",
                )
            ],
        )

    bundle = joblib.load(artifact_file)
    pipeline: Pipeline = bundle["pipeline"]
    importances: Dict[str, float] = bundle.get(
        "feature_importances",
        model_row.metrics.get("feature_importances", {}),
    )
    return model_row, pipeline, importances

