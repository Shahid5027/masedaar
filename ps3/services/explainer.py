"""Explainable AI service providing SHAP (when available) or transparent rule-based indicators."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from models.schemas import ExplanationOut, RiskIndicatorOut
from services.constants import CAUSATION_DISCLAIMER, MODEL_FEATURE_COLUMNS

logger = logging.getLogger("educore.ps3.explainer")

RULE_BASED_METHOD = "rule_based_feature_indicators"
RULE_BASED_LABEL = (
    "Rule-based contributing indicators derived from feature thresholds and model importances "
    "(not SHAP explanations)."
)
SHAP_METHOD = "shap_tree_explainer"
SHAP_LABEL = "SHAP TreeExplainer feature attributions (associational, not causal)."


@dataclass(frozen=True)
class FeatureDomainRule:
    """Reference threshold rule describing when a feature increases risk or is protective."""

    feature: str
    direction: str  # "below_is_risk" or "above_is_risk"
    high_risk_cutoff: float
    moderate_risk_cutoff: float
    protective_cutoff: float
    high_risk_msg: str
    moderate_risk_msg: str
    protective_msg: str
    neutral_msg: str


DOMAIN_INDICATOR_RULES: Tuple[FeatureDomainRule, ...] = (
    FeatureDomainRule(
        feature="attendance_rate",
        direction="below_is_risk",
        high_risk_cutoff=65.0,
        moderate_risk_cutoff=75.0,
        protective_cutoff=88.0,
        high_risk_msg="Attendance well below reference level ({val:.1f}% vs 75.0% reference).",
        moderate_risk_msg="Attendance below reference level ({val:.1f}% vs 75.0% reference).",
        protective_msg="Strong attendance above reference level ({val:.1f}%).",
        neutral_msg="Attendance within typical range ({val:.1f}%).",
    ),
    FeatureDomainRule(
        feature="average_grade",
        direction="below_is_risk",
        high_risk_cutoff=55.0,
        moderate_risk_cutoff=65.0,
        protective_cutoff=80.0,
        high_risk_msg="Low average grade well below passing benchmark ({val:.1f} vs 65.0).",
        moderate_risk_msg="Average grade below target benchmark ({val:.1f} vs 65.0).",
        protective_msg="Strong academic average grade ({val:.1f}).",
        neutral_msg="Average grade within standard range ({val:.1f}).",
    ),
    FeatureDomainRule(
        feature="missing_assignments",
        direction="above_is_risk",
        high_risk_cutoff=4.0,
        moderate_risk_cutoff=2.0,
        protective_cutoff=0.0,
        high_risk_msg="Multiple missing assignments ({val:.0f} missing).",
        moderate_risk_msg="Repeated missing assignments ({val:.0f} missing).",
        protective_msg="Zero missing assignments.",
        neutral_msg="Minimal missing assignments ({val:.0f}).",
    ),
    FeatureDomainRule(
        feature="late_assignments",
        direction="above_is_risk",
        high_risk_cutoff=4.0,
        moderate_risk_cutoff=2.0,
        protective_cutoff=0.0,
        high_risk_msg="Frequent late assignment submissions ({val:.0f} late).",
        moderate_risk_msg="Increased late submissions ({val:.0f} late).",
        protective_msg="No late assignment submissions.",
        neutral_msg="Low late assignment count ({val:.0f}).",
    ),
    FeatureDomainRule(
        feature="lms_logins_30d",
        direction="below_is_risk",
        high_risk_cutoff=8.0,
        moderate_risk_cutoff=15.0,
        protective_cutoff=28.0,
        high_risk_msg="Very low 30-day LMS activity ({val:.0f} logins).",
        moderate_risk_msg="Decreased 30-day LMS activity ({val:.0f} logins).",
        protective_msg="Consistent 30-day LMS login engagement ({val:.0f} logins).",
        neutral_msg="Moderate 30-day LMS activity ({val:.0f} logins).",
    ),
    FeatureDomainRule(
        feature="engagement_change_pct",
        direction="below_is_risk",
        high_risk_cutoff=-30.0,
        moderate_risk_cutoff=-15.0,
        protective_cutoff=10.0,
        high_risk_msg="Sharp negative engagement change ({val:+.1f}%).",
        moderate_risk_msg="Negative engagement change ({val:+.1f}%).",
        protective_msg="Positive engagement trend ({val:+.1f}%).",
        neutral_msg="Stable engagement trend ({val:+.1f}%).",
    ),
    FeatureDomainRule(
        feature="previous_failure_count",
        direction="above_is_risk",
        high_risk_cutoff=2.0,
        moderate_risk_cutoff=1.0,
        protective_cutoff=0.0,
        high_risk_msg="Multiple prior course failures ({val:.0f}).",
        moderate_risk_msg="Prior course failure history ({val:.0f}).",
        protective_msg="No prior course failures.",
        neutral_msg="No prior course failures.",
    ),
)

_RULE_BY_FEATURE: Dict[str, FeatureDomainRule] = {r.feature: r for r in DOMAIN_INDICATOR_RULES}


def _evaluate_rule_for_feature(
    rule: FeatureDomainRule,
    raw_value: Any,
    model_importance: float,
) -> tuple[float, RiskIndicatorOut]:
    """Evaluate a single feature against its domain rule and compute ranking priority."""
    if raw_value is None or (isinstance(raw_value, float) and not math.isfinite(raw_value)):
        indicator = RiskIndicatorOut(
            feature=rule.feature,
            value=None,
            direction="neutral",
            importance_weight=round(model_importance, 4),
            summary=f"{rule.feature} value unavailable (handled via pipeline median imputation).",
        )
        return model_importance * 0.1, indicator

    val = float(raw_value)
    if rule.direction == "below_is_risk":
        if val <= rule.high_risk_cutoff:
            direction, severity, template = "increases_risk", 2.0, rule.high_risk_msg
        elif val < rule.moderate_risk_cutoff:
            direction, severity, template = "increases_risk", 1.3, rule.moderate_risk_msg
        elif val >= rule.protective_cutoff:
            direction, severity, template = "protective", 0.6, rule.protective_msg
        else:
            direction, severity, template = "neutral", 0.3, rule.neutral_msg
    else:
        if val >= rule.high_risk_cutoff:
            direction, severity, template = "increases_risk", 2.0, rule.high_risk_msg
        elif val >= rule.moderate_risk_cutoff:
            direction, severity, template = "increases_risk", 1.3, rule.moderate_risk_msg
        elif val <= rule.protective_cutoff:
            direction, severity, template = "protective", 0.6, rule.protective_msg
        else:
            direction, severity, template = "neutral", 0.3, rule.neutral_msg

    formatted_val: float | int = int(round(val)) if isinstance(raw_value, int) else round(val, 2)
    rank_score = severity * (model_importance + 0.05)
    indicator = RiskIndicatorOut(
        feature=rule.feature,
        value=formatted_val,
        direction=direction,
        importance_weight=round(model_importance, 4),
        summary=template.format(val=val),
    )
    return rank_score, indicator


def _try_shap_explanation(
    pipeline: Any,
    features: Dict[str, Any],
    top_k: int,
) -> Optional[ExplanationOut]:
    """Attempt SHAP TreeExplainer when optional `shap` package is available and stable."""
    try:
        import shap  # type: ignore[import-not-found]
    except ImportError:
        return None

    try:
        imputer = pipeline.named_steps["imputer"]
        classifier = pipeline.named_steps["classifier"]
        row_df = pd.DataFrame([{col: features.get(col) for col in MODEL_FEATURE_COLUMNS}])
        transformed = imputer.transform(row_df)

        explainer = shap.TreeExplainer(classifier)
        shap_values = explainer.shap_values(transformed)
        # Handle both list-of-arrays (old SHAP) and 3D ndarray (newer SHAP)
        if isinstance(shap_values, list):
            class_idx = list(classifier.classes_).index(1)
            row_shap = np.asarray(shap_values[class_idx])[0]
        elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
            class_idx = list(classifier.classes_).index(1)
            row_shap = shap_values[0, :, class_idx]
        else:
            row_shap = np.asarray(shap_values)[0]

        indicators: List[RiskIndicatorOut] = []
        for idx, col in enumerate(MODEL_FEATURE_COLUMNS):
            phi = float(row_shap[idx])
            raw_val = features.get(col)
            rule = _RULE_BY_FEATURE[col]
            direction = "increases_risk" if phi > 0.01 else ("protective" if phi < -0.01 else "neutral")
            _, domain_ind = _evaluate_rule_for_feature(rule, raw_val, abs(phi))
            indicators.append(
                RiskIndicatorOut(
                    feature=col,
                    value=domain_ind.value,
                    direction=direction,
                    importance_weight=round(abs(phi), 4),
                    summary=f"{domain_ind.summary} (SHAP contribution {phi:+.4f}).",
                )
            )

        indicators.sort(key=lambda item: item.importance_weight, reverse=True)
        return ExplanationOut(
            method=SHAP_METHOD,
            is_shap=True,
            method_label=SHAP_LABEL,
            causation_disclaimer=CAUSATION_DISCLAIMER,
            indicators=indicators[:top_k],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("SHAP explanation failed; falling back to rule-based indicators: %s", exc)
        return None


def explain_student_prediction(
    features: Dict[str, Any],
    feature_importances: Optional[Dict[str, float]] = None,
    pipeline: Any = None,
    top_k: int = 5,
    prefer_shap: bool = True,
) -> ExplanationOut:
    """Generate transparent student-level indicators (SHAP if stable, else rule-based)."""
    if prefer_shap and pipeline is not None:
        shap_result = _try_shap_explanation(pipeline=pipeline, features=features, top_k=top_k)
        if shap_result is not None:
            return shap_result

    importances = feature_importances or {}
    scored: List[tuple[float, RiskIndicatorOut]] = []
    for rule in DOMAIN_INDICATOR_RULES:
        weight = float(importances.get(rule.feature, 1.0 / len(DOMAIN_INDICATOR_RULES)))
        scored.append(_evaluate_rule_for_feature(rule, features.get(rule.feature), weight))

    # Prioritize risk-increasing indicators first, then strongest weighted signals.
    scored.sort(
        key=lambda pair: (1 if pair[1].direction == "increases_risk" else 0, pair[0]),
        reverse=True,
    )
    risk_indicators = [ind for _, ind in scored if ind.direction == "increases_risk"]
    selected = risk_indicators[:top_k] if len(risk_indicators) >= 3 else [ind for _, ind in scored[:top_k]]

    return ExplanationOut(
        method=RULE_BASED_METHOD,
        is_shap=False,
        method_label=RULE_BASED_LABEL,
        causation_disclaimer=CAUSATION_DISCLAIMER,
        indicators=selected,
    )

