"""Tests for risk classification thresholds, XAI indicators, and intervention recommendations."""

import pytest
from pydantic import ValidationError

from config import Settings, get_settings
from services.explainer import explain_student_prediction
from services.prediction_service import classify_risk_level
from services.recommender import generate_recommendations


def test_risk_classification_and_configurable_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    assert classify_risk_level(0.15) == "low"
    assert classify_risk_level(0.35) == "medium"
    assert classify_risk_level(0.69) == "medium"
    assert classify_risk_level(0.70) == "high"
    assert classify_risk_level(0.95) == "high"

    # Override thresholds on active Settings
    settings = get_settings()
    monkeypatch.setattr(settings, "risk_threshold_medium", 0.25)
    monkeypatch.setattr(settings, "risk_threshold_high", 0.60)
    assert classify_risk_level(0.24) == "low"
    assert classify_risk_level(0.30) == "medium"
    assert classify_risk_level(0.62) == "high"

    with pytest.raises(ValidationError):
        Settings(risk_threshold_medium=0.75, risk_threshold_high=0.50)


def test_explainable_ai_indicators_and_non_causal_labeling() -> None:
    at_risk_features = {
        "attendance_rate": 52.0,
        "average_grade": 49.0,
        "late_assignments": 4,
        "missing_assignments": 5,
        "lms_logins_30d": 5,
        "engagement_change_pct": -48.0,
        "previous_failure_count": 2,
    }
    explanation = explain_student_prediction(
        features=at_risk_features,
        feature_importances={"attendance_rate": 0.30, "missing_assignments": 0.25},
        pipeline=None,
        top_k=5,
        prefer_shap=False,
    )
    assert explanation.is_shap is False
    assert "not SHAP" in explanation.method_label
    assert "causation" in explanation.causation_disclaimer.lower()
    assert len(explanation.indicators) == 5
    assert all(ind.direction == "increases_risk" for ind in explanation.indicators)
    assert any("attendance" in ind.summary.lower() for ind in explanation.indicators)


def test_intervention_recommendation_engine_rules_and_human_review() -> None:
    high_risk_features = {
        "attendance_rate": 58.0,
        "average_grade": 52.0,
        "late_assignments": 4,
        "missing_assignments": 4,
        "lms_logins_30d": 6,
        "engagement_change_pct": -35.0,
        "previous_failure_count": 2,
    }
    recs = generate_recommendations(
        features=high_risk_features,
        risk_level="high",
        risk_probability=0.88,
    )
    rec_types = {r.intervention_type for r in recs}
    assert {
        "counselor_review",
        "faculty_check_in",
        "assignment_planning",
        "subject_tutoring",
        "time_management_coaching",
        "access_and_engagement_check",
        "academic_advising",
    }.issubset(rec_types)
    assert all(r.requires_human_review is True for r in recs)

    low_risk_features = {
        "attendance_rate": 95.0,
        "average_grade": 89.0,
        "late_assignments": 0,
        "missing_assignments": 0,
        "lms_logins_30d": 42,
        "engagement_change_pct": 15.0,
        "previous_failure_count": 0,
    }
    low_recs = generate_recommendations(
        features=low_risk_features,
        risk_level="low",
        risk_probability=0.08,
    )
    assert len(low_recs) == 1
    assert low_recs[0].intervention_type == "routine_monitoring"
    assert low_recs[0].requires_human_review is True

