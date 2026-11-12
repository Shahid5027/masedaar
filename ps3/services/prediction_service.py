"""Risk scoring, threshold classification, DB persistence, and explanation queries."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from config import get_settings
from models.db_models import (
    ActivitySnapshot,
    Intervention,
    InterventionHistory,
    Prediction,
    Student,
)
from models.schemas import (
    ActivityFeaturesOut,
    ErrorDetail,
    ExplanationOut,
    PredictionListData,
    PredictionRecordOut,
    PredictionRunData,
    PredictionRunRequest,
    RecommendedInterventionOut,
    RiskIndicatorOut,
    StudentExplanationData,
)
from services.constants import CAUSATION_DISCLAIMER, HUMAN_REVIEW_NOTICE, MODEL_FEATURE_COLUMNS
from services.data_service import has_any_synthetic_students
from services.explainer import RULE_BASED_LABEL, RULE_BASED_METHOD, explain_student_prediction
from services.ml_pipeline import load_trained_pipeline
from services.recommender import generate_recommendations
from services.response import PS3APIError


def classify_risk_level(
    risk_probability: float,
    medium_threshold: Optional[float] = None,
    high_threshold: Optional[float] = None,
) -> Literal["low", "medium", "high"]:
    """Map predicted dropout probability in [0, 1] to configurable risk tier."""
    settings = get_settings()
    med = medium_threshold if medium_threshold is not None else settings.risk_threshold_medium
    high = high_threshold if high_threshold is not None else settings.risk_threshold_high

    if risk_probability >= high:
        return "high"
    if risk_probability >= med:
        return "medium"
    return "low"


def _snapshot_to_feature_dict(snap: ActivitySnapshot) -> Dict[str, Any]:
    """Extract strictly the 7 numeric model features from an ActivitySnapshot."""
    return {
        "attendance_rate": snap.attendance_rate,
        "average_grade": snap.average_grade,
        "late_assignments": snap.late_assignments,
        "missing_assignments": snap.missing_assignments,
        "lms_logins_30d": snap.lms_logins_30d,
        "engagement_change_pct": snap.engagement_change_pct,
        "previous_failure_count": snap.previous_failure_count,
    }


def _reconstruct_explanation(pred: Prediction) -> Tuple[ExplanationOut, str, Dict[str, float], bool]:
    """Build ExplanationOut and metadata from stored Prediction.top_risk_factors JSON."""
    settings = get_settings()
    stored = pred.top_risk_factors or {}

    raw_indicators = stored.get("indicators", [])
    indicators = [RiskIndicatorOut(**item) for item in raw_indicators] if raw_indicators else []
    explanation = ExplanationOut(
        method=stored.get("method", RULE_BASED_METHOD),
        is_shap=bool(stored.get("is_shap", False)),
        method_label=stored.get("method_label", RULE_BASED_LABEL),
        causation_disclaimer=stored.get("causation_disclaimer", CAUSATION_DISCLAIMER),
        indicators=indicators,
    )
    threshold_profile = stored.get("threshold_profile", settings.threshold_profile)
    thresholds = stored.get(
        "thresholds",
        {
            "low_max": settings.risk_threshold_medium,
            "medium_min": settings.risk_threshold_medium,
            "medium_max": settings.risk_threshold_high,
            "high_min": settings.risk_threshold_high,
        },
    )
    is_demo = bool(stored.get("is_demo", pred.is_synthetic_input))
    return explanation, threshold_profile, thresholds, is_demo


def _build_prediction_record_out(
    pred: Prediction,
    interventions: List[Intervention],
    fallback_features: Optional[Dict[str, Any]] = None,
) -> PredictionRecordOut:
    """Hydrate full PredictionRecordOut from persisted Prediction and Intervention rows."""
    explanation, threshold_profile, thresholds, is_demo = _reconstruct_explanation(pred)

    rec_list: List[RecommendedInterventionOut] = []
    if interventions:
        for item in interventions:
            priority: Literal["high", "medium", "low"] = (
                "high"
                if item.intervention_type in {"faculty_check_in", "subject_tutoring", "counselor_review"}
                and pred.risk_level == "high"
                else ("low" if item.intervention_type == "routine_monitoring" else "medium")
            )
            rec_list.append(
                RecommendedInterventionOut(
                    intervention_id=item.id,
                    intervention_type=item.intervention_type,
                    priority=priority,
                    recommended_action=item.recommended_action,
                    trigger_reason=item.notes or "Derived from student risk indicators.",
                    status=item.status,
                    requires_human_review=True,
                )
            )
    elif fallback_features is not None:
        rec_list = generate_recommendations(
            features=fallback_features,
            risk_level=pred.risk_level,  # type: ignore[arg-type]
            risk_probability=pred.risk_score,
        )

    return PredictionRecordOut(
        prediction_id=pred.id,
        student_id=pred.student_id,
        snapshot_id=pred.snapshot_id,
        risk_probability=round(float(pred.risk_score), 4),
        risk_level=pred.risk_level,  # type: ignore[arg-type]
        model_version=pred.model_version,
        prediction_timestamp=pred.predicted_at,
        is_demo=is_demo,
        threshold_profile=threshold_profile,
        thresholds_used=thresholds,
        explanation=explanation,
        recommended_interventions=rec_list,
        human_review_notice=HUMAN_REVIEW_NOTICE,
    )


def run_predictions(db: Session, request: PredictionRunRequest) -> PredictionRunData:
    """Score students' latest snapshots using the trained ML pipeline and persist results."""
    settings = get_settings()
    model_row, pipeline, feature_importances = load_trained_pipeline(
        db, model_version=request.model_version
    )

    latest_sq = (
        select(
            ActivitySnapshot.student_id.label("student_id"),
            func.max(ActivitySnapshot.id).label("latest_snapshot_id"),
        )
        .group_by(ActivitySnapshot.student_id)
        .subquery()
    )

    stmt = (
        select(Student, ActivitySnapshot)
        .join(latest_sq, Student.student_id == latest_sq.c.student_id)
        .join(ActivitySnapshot, ActivitySnapshot.id == latest_sq.c.latest_snapshot_id)
    )

    conditions = []
    if request.student_ids:
        clean_ids = [sid.strip() for sid in request.student_ids if sid.strip()]
        if not clean_ids:
            raise PS3APIError(
                status_code=422,
                message="student_ids list cannot contain only empty values.",
                errors=[ErrorDetail(code="INVALID_STUDENT_IDS", message="Provide valid student_id values.")],
            )
        conditions.append(Student.student_id.in_(clean_ids))
    if not request.include_synthetic:
        conditions.append(Student.is_synthetic.is_(False))
    if conditions:
        stmt = stmt.where(and_(*conditions))

    rows = db.execute(stmt.order_by(Student.student_id.asc())).all()
    if not rows:
        raise PS3APIError(
            status_code=404,
            message="No eligible students with activity snapshots found to run predictions.",
            errors=[
                ErrorDetail(
                    code="NO_STUDENTS_FOR_PREDICTION",
                    message="Upload student CSV data or adjust student_ids/include_synthetic filters.",
                )
            ],
            contains_synthetic_data=has_any_synthetic_students(db),
        )

    feature_dicts = [_snapshot_to_feature_dict(snap) for _, snap in rows]
    X_infer = pd.DataFrame(feature_dicts)[list(MODEL_FEATURE_COLUMNS)]

    classifier = pipeline.named_steps["classifier"]
    pos_idx = list(classifier.classes_).index(1)
    probabilities = np.clip(pipeline.predict_proba(X_infer)[:, pos_idx], 0.0, 1.0)

    thresholds_map = {
        "low_max": settings.risk_threshold_medium,
        "medium_min": settings.risk_threshold_medium,
        "medium_max": settings.risk_threshold_high,
        "high_min": settings.risk_threshold_high,
    }
    now = datetime.now(timezone.utc)
    risk_breakdown = {"low": 0, "medium": 0, "high": 0}
    interventions_persisted = 0
    created_outputs: List[PredictionRecordOut] = []

    try:
        for (student, snap), feat_dict, raw_prob in zip(rows, feature_dicts, probabilities):
            prob = round(float(raw_prob), 4)
            risk_level = classify_risk_level(prob)
            risk_breakdown[risk_level] += 1

            is_demo = bool(model_row.is_demo_model or student.is_synthetic or snap.is_synthetic)
            explanation = explain_student_prediction(
                features=feat_dict,
                feature_importances=feature_importances,
                pipeline=pipeline,
                top_k=5,
            )
            recommendations = generate_recommendations(
                features=feat_dict,
                risk_level=risk_level,
                risk_probability=prob,
            )

            stored_explanation_payload = {
                "method": explanation.method,
                "is_shap": explanation.is_shap,
                "method_label": explanation.method_label,
                "causation_disclaimer": explanation.causation_disclaimer,
                "threshold_profile": settings.threshold_profile,
                "thresholds": thresholds_map,
                "is_demo": is_demo,
                "indicators": [ind.model_dump(mode="json") for ind in explanation.indicators],
            }

            pred_row = Prediction(
                student_id=student.student_id,
                snapshot_id=snap.id,
                risk_score=prob,
                risk_level=risk_level,
                model_version=model_row.model_version,
                top_risk_factors=stored_explanation_payload,
                is_synthetic_input=bool(student.is_synthetic or snap.is_synthetic),
                predicted_at=now,
            )
            db.add(pred_row)
            db.flush()

            persisted_interventions: List[Intervention] = []
            if request.persist_interventions:
                for rec in recommendations:
                    if rec.intervention_type == "routine_monitoring":
                        continue
                    intr = Intervention(
                        student_id=student.student_id,
                        prediction_id=pred_row.id,
                        intervention_type=rec.intervention_type,
                        recommended_action=rec.recommended_action,
                        priority=rec.priority,
                        status="PENDING",
                        notes=f"{rec.trigger_reason} ({HUMAN_REVIEW_NOTICE})",
                        is_demo=is_demo,
                        version=1,
                        is_archived=False,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(intr)
                    persisted_interventions.append(intr)
                    interventions_persisted += 1
                db.flush()
                for intr in persisted_interventions:
                    db.add(
                        InterventionHistory(
                            intervention_id=intr.id,
                            student_id=student.student_id,
                            action="INTERVENTION_RECOMMENDED",
                            actor_id="ml_prediction_pipeline",
                            actor_role="system",
                            previous_value=None,
                            new_value={
                                "status": intr.status,
                                "priority": intr.priority,
                                "prediction_id": pred_row.id,
                                "intervention_type": intr.intervention_type,
                            },
                            summary=(
                                f"AI recommendation persisted for human review "
                                f"({intr.intervention_type}, priority={intr.priority})."
                            ),
                            created_at=now,
                        )
                    )

            # Map back intervention IDs into response recommendations cleanly
            id_by_type = {intr.intervention_type: intr.id for intr in persisted_interventions}
            hydrated_recs = [
                rec.model_copy(
                    update={
                        "intervention_id": id_by_type.get(rec.intervention_type),
                        "status": "PENDING"
                        if rec.intervention_type in id_by_type
                        else rec.status,
                    }
                )
                for rec in recommendations
            ]

            created_outputs.append(
                PredictionRecordOut(
                    prediction_id=pred_row.id,
                    student_id=student.student_id,
                    snapshot_id=snap.id,
                    risk_probability=prob,
                    risk_level=risk_level,
                    model_version=model_row.model_version,
                    prediction_timestamp=now,
                    is_demo=is_demo,
                    threshold_profile=settings.threshold_profile,
                    thresholds_used=thresholds_map,
                    explanation=explanation,
                    recommended_interventions=hydrated_recs,
                    human_review_notice=HUMAN_REVIEW_NOTICE,
                )
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return PredictionRunData(
        model_version=model_row.model_version,
        is_demo_model=model_row.is_demo_model,
        threshold_profile=settings.threshold_profile,
        thresholds=thresholds_map,
        total_predicted=len(created_outputs),
        risk_breakdown=risk_breakdown,
        interventions_persisted=interventions_persisted,
        predictions=created_outputs,
    )


def list_predictions(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    student_id: Optional[str] = None,
    search: Optional[str] = None,
    risk_level: Optional[Literal["low", "medium", "high"]] = None,
    model_version: Optional[str] = None,
    is_demo: Optional[bool] = None,
    predicted_from: Optional[datetime] = None,
    predicted_to: Optional[datetime] = None,
    latest_only: bool = True,
    sort_by: Literal["risk_score", "predicted_at", "student_id"] = "risk_score",
    sort_order: Literal["asc", "desc"] = "desc",
) -> Tuple[PredictionListData, bool]:
    """Query persisted predictions with linked recommendations, filters, and scalable pagination."""
    stmt = select(Prediction)
    conditions = []

    if latest_only:
        latest_pred_sq = (
            select(
                Prediction.student_id.label("student_id"),
                func.max(Prediction.id).label("latest_id"),
            )
            .group_by(Prediction.student_id)
            .subquery()
        )
        stmt = stmt.join(latest_pred_sq, Prediction.id == latest_pred_sq.c.latest_id)

    if student_id:
        conditions.append(Prediction.student_id == student_id.strip())
    if search and search.strip():
        conditions.append(Prediction.student_id.ilike(f"%{search.strip()}%"))
    if risk_level:
        conditions.append(Prediction.risk_level == risk_level)
    if model_version:
        conditions.append(Prediction.model_version == model_version.strip())
    if is_demo is not None:
        conditions.append(Prediction.is_synthetic_input.is_(is_demo))
    if predicted_from is not None:
        conditions.append(Prediction.predicted_at >= predicted_from)
    if predicted_to is not None:
        conditions.append(Prediction.predicted_at <= predicted_to)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    sort_map = {
        "risk_score": Prediction.risk_score,
        "predicted_at": Prediction.predicted_at,
        "student_id": Prediction.student_id,
    }
    sort_col = sort_map.get(sort_by, Prediction.risk_score)
    order_expr = sort_col.desc() if sort_order == "desc" else sort_col.asc()

    rows = db.scalars(
        stmt.order_by(order_expr, Prediction.id.desc()).limit(limit).offset(offset)
    ).all()

    pred_ids = [p.id for p in rows]
    snap_ids = [p.snapshot_id for p in rows if p.snapshot_id is not None]

    interventions_by_pred: Dict[int, List[Intervention]] = {}
    if pred_ids:
        for intr in db.scalars(
            select(Intervention).where(Intervention.prediction_id.in_(pred_ids))
        ).all():
            if intr.prediction_id is not None:
                interventions_by_pred.setdefault(intr.prediction_id, []).append(intr)

    snaps_by_id: Dict[int, ActivitySnapshot] = {}
    if snap_ids:
        snaps_by_id = {
            s.id: s
            for s in db.scalars(
                select(ActivitySnapshot).where(ActivitySnapshot.id.in_(snap_ids))
            ).all()
        }

    items: List[PredictionRecordOut] = []
    breakdown = {"low": 0, "medium": 0, "high": 0}
    for pred in rows:
        if pred.risk_level in breakdown:
            breakdown[pred.risk_level] += 1
        snap = snaps_by_id.get(pred.snapshot_id) if pred.snapshot_id else None
        fallback_feats = _snapshot_to_feature_dict(snap) if snap else None
        items.append(
            _build_prediction_record_out(
                pred=pred,
                interventions=interventions_by_pred.get(pred.id, []),
                fallback_features=fallback_feats,
            )
        )

    page_size = max(1, limit)
    page = (offset // page_size) + 1
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    contains_synthetic = has_any_synthetic_students(db) or any(item.is_demo for item in items)
    return (
        PredictionListData(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=(offset + page_size) < total,
            has_previous=offset > 0,
            risk_breakdown_in_page=breakdown,
        ),
        contains_synthetic,
    )


def get_student_explanation(db: Session, student_id: str) -> Tuple[StudentExplanationData, bool]:
    """Return latest stored prediction, explanation, and recommendations for a shared student_id."""
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
                    message=f"No student exists for shared student_id '{clean_id}'.",
                )
            ],
            contains_synthetic_data=has_any_synthetic_students(db),
        )

    latest_pred = db.scalars(
        select(Prediction)
        .where(Prediction.student_id == clean_id)
        .order_by(Prediction.predicted_at.desc(), Prediction.id.desc())
        .limit(1)
    ).first()
    if latest_pred is None:
        raise PS3APIError(
            status_code=404,
            message=f"No prediction found for student '{clean_id}'. Run POST /api/ps3/predictions/run first.",
            errors=[
                ErrorDetail(
                    code="PREDICTION_NOT_FOUND",
                    student_id=clean_id,
                    message=f"Student '{clean_id}' has not been scored by a trained model yet.",
                )
            ],
            contains_synthetic_data=student.is_synthetic or has_any_synthetic_students(db),
        )

    linked_interventions = db.scalars(
        select(Intervention)
        .where(Intervention.prediction_id == latest_pred.id)
        .order_by(Intervention.id.asc())
    ).all()

    latest_snap = (
        db.get(ActivitySnapshot, latest_pred.snapshot_id)
        if latest_pred.snapshot_id is not None
        else db.scalars(
            select(ActivitySnapshot)
            .where(ActivitySnapshot.student_id == clean_id)
            .order_by(ActivitySnapshot.recorded_at.desc(), ActivitySnapshot.id.desc())
            .limit(1)
        ).first()
    )

    latest_features_out = (
        ActivityFeaturesOut(
            snapshot_id=latest_snap.id,
            attendance_rate=latest_snap.attendance_rate,
            average_grade=latest_snap.average_grade,
            late_assignments=latest_snap.late_assignments,
            missing_assignments=latest_snap.missing_assignments,
            lms_logins_30d=latest_snap.lms_logins_30d,
            engagement_change_pct=latest_snap.engagement_change_pct,
            previous_failure_count=latest_snap.previous_failure_count,
            is_synthetic=latest_snap.is_synthetic,
            data_source=latest_snap.data_source,
            recorded_at=latest_snap.recorded_at,
        )
        if latest_snap is not None
        else None
    )

    fallback_feats = _snapshot_to_feature_dict(latest_snap) if latest_snap is not None else None
    pred_out = _build_prediction_record_out(
        pred=latest_pred,
        interventions=list(linked_interventions),
        fallback_features=fallback_feats,
    )

    data = StudentExplanationData(
        student_id=student.student_id,
        is_synthetic=student.is_synthetic,
        data_source=student.data_source,
        latest_features=latest_features_out,
        prediction=pred_out,
        human_review_notice=HUMAN_REVIEW_NOTICE,
    )
    return data, student.is_synthetic or pred_out.is_demo or has_any_synthetic_students(db)

