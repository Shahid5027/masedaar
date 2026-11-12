"""Auditable rule-based intervention recommendation service (human review only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Tuple

from models.schemas import RecommendedInterventionOut


@dataclass(frozen=True)
class InterventionRule:
    """Single auditable intervention suggestion rule."""

    intervention_type: str
    priority: Literal["high", "medium", "low"]
    recommended_action: str
    condition: Callable[[Dict[str, Any]], bool]
    reason_builder: Callable[[Dict[str, Any]], str]


def _num(features: Dict[str, Any], key: str, default: float) -> float:
    val = features.get(key)
    return float(val) if val is not None else default


INTERVENTION_RULES: Tuple[InterventionRule, ...] = (
    InterventionRule(
        intervention_type="faculty_check_in",
        priority="high",
        recommended_action=(
            "Recommend a supportive faculty attendance check-in to discuss barriers and attendance recovery."
        ),
        condition=lambda f: _num(f, "attendance_rate", 100.0) < 75.0,
        reason_builder=lambda f: f"Attendance rate at {_num(f, 'attendance_rate', 0.0):.1f}% (< 75.0% threshold).",
    ),
    InterventionRule(
        intervention_type="assignment_planning",
        priority="medium",
        recommended_action=(
            "Suggest structured assignment planning support and deadline triage with academic coaching."
        ),
        condition=lambda f: _num(f, "missing_assignments", 0.0) >= 2.0,
        reason_builder=lambda f: f"{int(_num(f, 'missing_assignments', 0.0))} missing assignments recorded (>= 2 threshold).",
    ),
    InterventionRule(
        intervention_type="subject_tutoring",
        priority="high",
        recommended_action=(
            "Recommend targeted subject tutoring or peer-assisted study sessions for core coursework."
        ),
        condition=lambda f: _num(f, "average_grade", 100.0) < 65.0,
        reason_builder=lambda f: f"Average grade at {_num(f, 'average_grade', 0.0):.1f} (< 65.0 threshold).",
    ),
    InterventionRule(
        intervention_type="time_management_coaching",
        priority="medium",
        recommended_action=(
            "Suggest workflow and submission pacing coaching to reduce late coursework turn-ins."
        ),
        condition=lambda f: _num(f, "late_assignments", 0.0) >= 3.0,
        reason_builder=lambda f: f"{int(_num(f, 'late_assignments', 0.0))} late assignments recorded (>= 3 threshold).",
    ),
    InterventionRule(
        intervention_type="access_and_engagement_check",
        priority="medium",
        recommended_action=(
            "Verify LMS connectivity, platform access difficulties, or personal scheduling constraints."
        ),
        condition=lambda f: (
            _num(f, "lms_logins_30d", 99.0) <= 15.0
            or _num(f, "engagement_change_pct", 0.0) <= -15.0
        ),
        reason_builder=lambda f: (
            f"Reduced digital engagement (30d logins: {int(_num(f, 'lms_logins_30d', 0.0))}, "
            f"engagement change: {_num(f, 'engagement_change_pct', 0.0):+.1f}%)."
        ),
    ),
    InterventionRule(
        intervention_type="academic_advising",
        priority="medium",
        recommended_action=(
            "Schedule academic advising check-in to review course load and prerequisite support."
        ),
        condition=lambda f: _num(f, "previous_failure_count", 0.0) >= 1.0,
        reason_builder=lambda f: (
            f"Prior course failure history ({int(_num(f, 'previous_failure_count', 0.0))} prior failure(s))."
        ),
    ),
)


def generate_recommendations(
    features: Dict[str, Any],
    risk_level: Literal["low", "medium", "high"],
    risk_probability: float,
) -> List[RecommendedInterventionOut]:
    """Generate auditable intervention suggestions for human review (never automatic decisions)."""
    suggestions: List[RecommendedInterventionOut] = []

    for rule in INTERVENTION_RULES:
        if rule.condition(features):
            suggestions.append(
                RecommendedInterventionOut(
                    intervention_type=rule.intervention_type,
                    priority=rule.priority,
                    recommended_action=rule.recommended_action,
                    trigger_reason=rule.reason_builder(features),
                    status="pending_review",
                    requires_human_review=True,
                )
            )

    # Escalate to holistic counselor review when multiple indicators co-occur or overall risk is high.
    if len(suggestions) >= 2 or risk_level == "high":
        suggestions.insert(
            0,
            RecommendedInterventionOut(
                intervention_type="counselor_review",
                priority="high" if risk_level == "high" else "medium",
                recommended_action=(
                    "Recommend holistic academic counselor review to coordinate outreach across triggered indicators."
                ),
                trigger_reason=(
                    f"Risk level '{risk_level}' (probability {risk_probability:.3f}) with "
                    f"{len(suggestions)} active indicator trigger(s)."
                ),
                status="pending_review",
                requires_human_review=True,
            ),
        )

    if not suggestions:
        suggestions.append(
            RecommendedInterventionOut(
                intervention_type="routine_monitoring",
                priority="low",
                recommended_action=(
                    "Continue routine academic monitoring; no immediate intervention outreach indicated."
                ),
                trigger_reason=(
                    f"Risk level '{risk_level}' (probability {risk_probability:.3f}) with zero risk triggers."
                ),
                status="no_action_needed",
                requires_human_review=True,
            )
        )

    return suggestions

