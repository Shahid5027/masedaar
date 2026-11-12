"""Database ingestion, aggregation, and student query services for EDUCORE AI PS3."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from models.db_models import (
    ActivitySnapshot,
    IngestionBatch,
    Intervention,
    Prediction,
    Student,
    TrainingTarget,
)
from models.schemas import (
    ActivityFeaturesOut,
    DataSummaryData,
    ErrorDetail,
    FeatureStat,
    InterventionOut,
    PredictionOut,
    StudentDetailData,
    StudentListData,
    StudentListItem,
    TrainingTargetsSummary,
    UploadData,
)
from services.constants import MODEL_FEATURE_COLUMNS, SYNTHETIC_DATA_SOURCE, SYNTHETIC_NOTICE_MESSAGE
from services.csv_validator import CSVValidationResult
from services.response import PS3APIError


def has_any_synthetic_students(db: Session) -> bool:
    """Return True if the database currently contains any synthetic student records."""
    stmt = select(Student.student_id).where(Student.is_synthetic.is_(True)).limit(1)
    return db.execute(stmt).first() is not None


def ingest_validated_csv(
    db: Session,
    validation: CSVValidationResult,
    filename: str,
    force_synthetic: bool = False,
) -> UploadData:
    """Persist validated CSV rows atomically across students, snapshots, and training targets."""
    if not validation.summary.is_valid:
        raise PS3APIError(
            status_code=422,
            message="CSV validation failed. Fix the reported errors before uploading.",
            errors=validation.summary.errors,
        )

    records = validation.cleaned_features
    if not records:
        raise PS3APIError(
            status_code=422,
            message="No valid student records found to ingest.",
            errors=[
                ErrorDetail(
                    code="NO_VALID_RECORDS",
                    message="CSV yielded zero valid student rows.",
                )
            ],
        )

    now = datetime.now(timezone.utc)
    has_targets = bool(validation.cleaned_training_targets)
    batch_is_synthetic = force_synthetic or validation.summary.is_synthetic_detected
    batch_source = SYNTHETIC_DATA_SOURCE if batch_is_synthetic else "csv_upload"

    student_ids = [row["student_id"] for row in records]
    existing_students_map: Dict[str, Student] = {
        s.student_id: s
        for s in db.scalars(select(Student).where(Student.student_id.in_(student_ids))).all()
    }

    new_students_count = 0
    updated_students_count = 0
    training_targets_stored = 0

    try:
        batch = IngestionBatch(
            filename=filename,
            record_count=len(records),
            has_training_labels=has_targets,
            is_synthetic=batch_is_synthetic,
            data_source=batch_source,
            uploaded_at=now,
        )
        db.add(batch)
        db.flush()

        for row in records:
            sid = row["student_id"]
            row_is_synthetic = force_synthetic or validation.row_synthetic_flags.get(sid, False)
            row_source = (
                SYNTHETIC_DATA_SOURCE
                if row_is_synthetic
                else validation.row_data_sources.get(sid, "csv_upload")
            )

            existing = existing_students_map.get(sid)
            if existing is None:
                student = Student(
                    student_id=sid,
                    is_synthetic=row_is_synthetic,
                    data_source=row_source,
                    created_at=now,
                    updated_at=now,
                )
                db.add(student)
                new_students_count += 1
            else:
                existing.is_synthetic = row_is_synthetic
                existing.data_source = row_source
                existing.updated_at = now
                updated_students_count += 1

            snapshot = ActivitySnapshot(
                student_id=sid,
                batch_id=batch.id,
                attendance_rate=row["attendance_rate"],
                average_grade=row["average_grade"],
                late_assignments=row["late_assignments"],
                missing_assignments=row["missing_assignments"],
                lms_logins_30d=row["lms_logins_30d"],
                engagement_change_pct=row["engagement_change_pct"],
                previous_failure_count=row["previous_failure_count"],
                is_synthetic=row_is_synthetic,
                data_source=row_source,
                recorded_at=now,
            )
            db.add(snapshot)
            db.flush()

            # Keep dropout_label strictly isolated in training_targets.
            if has_targets and sid in validation.cleaned_training_targets:
                target = TrainingTarget(
                    student_id=sid,
                    snapshot_id=snapshot.id,
                    dropout_label=validation.cleaned_training_targets[sid],
                    is_synthetic=row_is_synthetic,
                    recorded_at=now,
                )
                db.add(target)
                training_targets_stored += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    return UploadData(
        batch_id=batch.id,
        filename=filename,
        ingested_rows=len(records),
        new_students=new_students_count,
        updated_students=updated_students_count,
        snapshots_created=len(records),
        training_targets_stored=training_targets_stored,
        has_training_target=has_targets,
        is_synthetic=batch_is_synthetic,
        data_source=batch_source,
        synthetic_label="SYNTHETIC_DEMO_DATA" if batch_is_synthetic else None,
        uploaded_at=now,
    )


def _latest_snapshot_subquery():
    """Return a subquery selecting the latest snapshot ID per student."""
    return (
        select(
            ActivitySnapshot.student_id.label("student_id"),
            func.max(ActivitySnapshot.id).label("latest_snapshot_id"),
        )
        .group_by(ActivitySnapshot.student_id)
        .subquery()
    )


def _latest_prediction_subquery():
    """Return a subquery selecting the latest prediction ID per student."""
    return (
        select(
            Prediction.student_id.label("student_id"),
            func.max(Prediction.id).label("latest_prediction_id"),
        )
        .group_by(Prediction.student_id)
        .subquery()
    )


def get_data_summary(db: Session) -> DataSummaryData:
    """Compute real database counts, full-cohort risk distribution, and Pandas/NumPy feature statistics."""
    total_students = db.scalar(select(func.count(Student.student_id))) or 0
    synthetic_students = (
        db.scalar(select(func.count(Student.student_id)).where(Student.is_synthetic.is_(True))) or 0
    )
    real_students = total_students - synthetic_students
    contains_synthetic = synthetic_students > 0

    total_snapshots = db.scalar(select(func.count(ActivitySnapshot.id))) or 0
    total_batches = db.scalar(select(func.count(IngestionBatch.id))) or 0
    total_predictions = db.scalar(select(func.count(Prediction.id))) or 0
    total_interventions = db.scalar(select(func.count(Intervention.id))) or 0

    latest_pred_sq = _latest_prediction_subquery()
    risk_rows = db.execute(
        select(Prediction.risk_level, func.count(Prediction.id))
        .join(latest_pred_sq, Prediction.id == latest_pred_sq.c.latest_prediction_id)
        .group_by(Prediction.risk_level)
    ).all()
    risk_dist = {"low": 0, "medium": 0, "high": 0}
    for level, cnt in risk_rows:
        if level in risk_dist:
            risk_dist[level] = int(cnt)
    scored_students = sum(risk_dist.values())
    latest_risk_distribution = {
        **risk_dist,
        "scored_students": scored_students,
        "unscored_students": max(0, total_students - scored_students),
    }

    total_targets = db.scalar(select(func.count(TrainingTarget.id))) or 0
    dropout_count = (
        db.scalar(
            select(func.count(TrainingTarget.id)).where(TrainingTarget.dropout_label == 1)
        )
        or 0
    )
    retained_count = total_targets - dropout_count
    dropout_rate_pct = round((dropout_count / total_targets) * 100.0, 2) if total_targets > 0 else 0.0

    # Compute descriptive stats over each student's latest snapshot using Pandas & NumPy.
    latest_sq = _latest_snapshot_subquery()
    latest_rows = db.execute(
        select(
            ActivitySnapshot.attendance_rate,
            ActivitySnapshot.average_grade,
            ActivitySnapshot.late_assignments,
            ActivitySnapshot.missing_assignments,
            ActivitySnapshot.lms_logins_30d,
            ActivitySnapshot.engagement_change_pct,
            ActivitySnapshot.previous_failure_count,
        ).join(latest_sq, ActivitySnapshot.id == latest_sq.c.latest_snapshot_id)
    ).all()

    feature_stats: Dict[str, FeatureStat] = {}
    if latest_rows:
        df = pd.DataFrame(latest_rows, columns=list(MODEL_FEATURE_COLUMNS))
        for col in MODEL_FEATURE_COLUMNS:
            arr = df[col].to_numpy(dtype=float)
            feature_stats[col] = FeatureStat(
                min=round(float(np.min(arr)), 4),
                max=round(float(np.max(arr)), 4),
                mean=round(float(np.mean(arr)), 4),
                median=round(float(np.median(arr)), 4),
                std=round(float(np.std(arr, ddof=0)), 4),
            )

    return DataSummaryData(
        total_students=total_students,
        real_students=real_students,
        synthetic_students=synthetic_students,
        contains_synthetic_data=contains_synthetic,
        synthetic_data_notice=SYNTHETIC_NOTICE_MESSAGE if contains_synthetic else None,
        total_activity_snapshots=total_snapshots,
        total_ingestion_batches=total_batches,
        total_predictions=total_predictions,
        total_interventions=total_interventions,
        latest_risk_distribution=latest_risk_distribution,
        training_targets_summary=TrainingTargetsSummary(
            total_labeled_snapshots=total_targets,
            dropout_count=dropout_count,
            retained_count=retained_count,
            dropout_rate_pct=dropout_rate_pct,
        ),
        feature_statistics=feature_stats,
    )


def _to_activity_features_out(snap: ActivitySnapshot) -> ActivityFeaturesOut:
    """Map ActivitySnapshot ORM entity to ActivityFeaturesOut (excluding dropout_label)."""
    return ActivityFeaturesOut(
        snapshot_id=snap.id,
        attendance_rate=snap.attendance_rate,
        average_grade=snap.average_grade,
        late_assignments=snap.late_assignments,
        missing_assignments=snap.missing_assignments,
        lms_logins_30d=snap.lms_logins_30d,
        engagement_change_pct=snap.engagement_change_pct,
        previous_failure_count=snap.previous_failure_count,
        is_synthetic=snap.is_synthetic,
        data_source=snap.data_source,
        recorded_at=snap.recorded_at,
    )


def list_students(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    is_synthetic: Optional[bool] = None,
    search: Optional[str] = None,
    risk_level: Optional[str] = None,
    min_attendance: Optional[float] = None,
    max_attendance: Optional[float] = None,
    min_failures: Optional[int] = None,
    predicted_from: Optional[datetime] = None,
    predicted_to: Optional[datetime] = None,
    sort_by: str = "student_id",
    sort_order: str = "asc",
) -> Tuple[StudentListData, bool]:
    """Return paginated students joined with latest snapshot and latest prediction across any cohort size."""
    latest_sq = _latest_snapshot_subquery()
    latest_pred_sq = _latest_prediction_subquery()

    base_stmt: Select = (
        select(Student, ActivitySnapshot, Prediction)
        .outerjoin(latest_sq, Student.student_id == latest_sq.c.student_id)
        .outerjoin(ActivitySnapshot, ActivitySnapshot.id == latest_sq.c.latest_snapshot_id)
        .outerjoin(latest_pred_sq, Student.student_id == latest_pred_sq.c.student_id)
        .outerjoin(Prediction, Prediction.id == latest_pred_sq.c.latest_prediction_id)
    )

    conditions = []
    if is_synthetic is not None:
        conditions.append(Student.is_synthetic.is_(is_synthetic))
    if search and search.strip():
        conditions.append(Student.student_id.ilike(f"%{search.strip()}%"))
    if risk_level:
        clean_risk = risk_level.strip().lower()
        if clean_risk == "unscored":
            conditions.append(Prediction.id.is_(None))
        else:
            conditions.append(Prediction.risk_level == clean_risk)
    if min_attendance is not None:
        conditions.append(ActivitySnapshot.attendance_rate >= min_attendance)
    if max_attendance is not None:
        conditions.append(ActivitySnapshot.attendance_rate <= max_attendance)
    if min_failures is not None:
        conditions.append(ActivitySnapshot.previous_failure_count >= min_failures)
    if predicted_from is not None:
        conditions.append(Prediction.predicted_at >= predicted_from)
    if predicted_to is not None:
        conditions.append(Prediction.predicted_at <= predicted_to)

    if conditions:
        base_stmt = base_stmt.where(and_(*conditions))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = db.scalar(count_stmt) or 0

    sort_column_map = {
        "student_id": Student.student_id,
        "updated_at": Student.updated_at,
        "attendance_rate": ActivitySnapshot.attendance_rate,
        "average_grade": ActivitySnapshot.average_grade,
        "missing_assignments": ActivitySnapshot.missing_assignments,
        "previous_failure_count": ActivitySnapshot.previous_failure_count,
        "risk_score": Prediction.risk_score,
        "predicted_at": Prediction.predicted_at,
    }
    sort_col = sort_column_map.get(sort_by, Student.student_id)
    if sort_by in {"risk_score", "predicted_at", "attendance_rate", "average_grade", "missing_assignments", "previous_failure_count"}:
        order_expr = (
            sort_col.desc().nulls_last()
            if sort_order.lower() == "desc"
            else sort_col.asc().nulls_last()
        )
    else:
        order_expr = sort_col.desc() if sort_order.lower() == "desc" else sort_col.asc()

    paged_stmt = base_stmt.order_by(order_expr, Student.student_id.asc()).limit(limit).offset(offset)
    rows = db.execute(paged_stmt).all()

    page_student_ids = [student.student_id for student, _, _ in rows]
    snapshot_counts: Dict[str, int] = {}
    prediction_counts: Dict[str, int] = {}
    intervention_counts: Dict[str, int] = {}

    if page_student_ids:
        snapshot_counts = dict(
            db.execute(
                select(ActivitySnapshot.student_id, func.count(ActivitySnapshot.id))
                .where(ActivitySnapshot.student_id.in_(page_student_ids))
                .group_by(ActivitySnapshot.student_id)
            ).all()
        )
        prediction_counts = dict(
            db.execute(
                select(Prediction.student_id, func.count(Prediction.id))
                .where(Prediction.student_id.in_(page_student_ids))
                .group_by(Prediction.student_id)
            ).all()
        )
        intervention_counts = dict(
            db.execute(
                select(Intervention.student_id, func.count(Intervention.id))
                .where(Intervention.student_id.in_(page_student_ids))
                .group_by(Intervention.student_id)
            ).all()
        )

    items: List[StudentListItem] = []
    synthetic_in_page = 0
    for student, latest_snap, latest_pred in rows:
        if student.is_synthetic:
            synthetic_in_page += 1
        items.append(
            StudentListItem(
                student_id=student.student_id,
                is_synthetic=student.is_synthetic,
                data_source=student.data_source,
                synthetic_label="SYNTHETIC_DEMO_RECORD" if student.is_synthetic else None,
                created_at=student.created_at,
                updated_at=student.updated_at,
                latest_features=_to_activity_features_out(latest_snap) if latest_snap else None,
                latest_risk_probability=(
                    round(float(latest_pred.risk_score), 4) if latest_pred else None
                ),
                latest_risk_level=latest_pred.risk_level if latest_pred else None,  # type: ignore[arg-type]
                latest_prediction_id=latest_pred.id if latest_pred else None,
                latest_prediction_timestamp=latest_pred.predicted_at if latest_pred else None,
                snapshot_count=snapshot_counts.get(student.student_id, 0),
                prediction_count=prediction_counts.get(student.student_id, 0),
                intervention_count=intervention_counts.get(student.student_id, 0),
            )
        )

    page_size = max(1, limit)
    page = (offset // page_size) + 1
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    contains_synthetic = has_any_synthetic_students(db)
    data = StudentListData(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=(offset + page_size) < total,
        has_previous=offset > 0,
        synthetic_count_in_page=synthetic_in_page,
        real_count_in_page=len(items) - synthetic_in_page,
    )
    return data, contains_synthetic


def get_student_detail(db: Session, student_id: str) -> Tuple[StudentDetailData, bool]:
    """Return full history for a single shared student_id or raise 404."""
    clean_id = student_id.strip()
    student = db.get(Student, clean_id)
    if student is None:
        raise PS3APIError(
            status_code=404,
            message=f"Student '{clean_id}' not found.",
            errors=[
                ErrorDetail(
                    code="STUDENT_NOT_FOUND",
                    student_id=clean_id,
                    message=f"No student record exists for shared student_id '{clean_id}'.",
                )
            ],
            contains_synthetic_data=has_any_synthetic_students(db),
        )

    snapshots = db.scalars(
        select(ActivitySnapshot)
        .where(ActivitySnapshot.student_id == clean_id)
        .order_by(ActivitySnapshot.recorded_at.desc(), ActivitySnapshot.id.desc())
    ).all()

    predictions = db.scalars(
        select(Prediction)
        .where(Prediction.student_id == clean_id)
        .order_by(Prediction.predicted_at.desc(), Prediction.id.desc())
    ).all()

    interventions = db.scalars(
        select(Intervention)
        .where(Intervention.student_id == clean_id)
        .order_by(Intervention.created_at.desc(), Intervention.id.desc())
    ).all()

    has_target = (
        db.scalar(
            select(TrainingTarget.id).where(TrainingTarget.student_id == clean_id).limit(1)
        )
        is not None
    )

    history_out = [_to_activity_features_out(s) for s in snapshots]
    detail = StudentDetailData(
        student_id=student.student_id,
        is_synthetic=student.is_synthetic,
        data_source=student.data_source,
        synthetic_label="SYNTHETIC_DEMO_RECORD" if student.is_synthetic else None,
        created_at=student.created_at,
        updated_at=student.updated_at,
        latest_features=history_out[0] if history_out else None,
        activity_history=history_out,
        predictions=[PredictionOut.model_validate(p) for p in predictions],
        interventions=[InterventionOut.model_validate(i) for i in interventions],
        has_training_target_record=has_target,
    )
    return detail, student.is_synthetic or has_any_synthetic_students(db)

