"""ML model training and evaluation metrics endpoints for EDUCORE AI PS3."""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import User
from models.schemas import APIResponse, ModelMetricsData, TrainModelRequest
from services.auth_service import require_roles
from services.data_service import has_any_synthetic_students
from services.ml_pipeline import get_model_metrics, train_and_register_model
from services.response import success_response

router = APIRouter(prefix="/model", tags=["ML Model & Evaluation"])


@router.post("/train", response_model=APIResponse[ModelMetricsData])
def train_model_endpoint(
    request: Optional[TrainModelRequest] = Body(default=None),
    _admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[ModelMetricsData]:
    """Train RandomForest pipeline on real labeled DB records or synthetic demo fallback (admin only)."""
    train_req = request or TrainModelRequest()
    metrics_data = train_and_register_model(db=db, request=train_req)
    demo_tag = " [SYNTHETIC DEMO MODEL]" if metrics_data.is_demo_model else ""
    return success_response(
        message=(
            f"Trained model '{metrics_data.model_version}' ({metrics_data.algorithm}) "
            f"on {metrics_data.sample_count} record(s).{demo_tag}"
        ),
        data=metrics_data,
        contains_synthetic_data=metrics_data.is_demo_model or has_any_synthetic_students(db),
    )


@router.get("/metrics", response_model=APIResponse[ModelMetricsData])
def model_metrics_endpoint(
    model_version: Optional[str] = Query(
        default=None,
        description="Optional model version identifier; defaults to the active trained model.",
    ),
    _user: User = Depends(require_roles("administrator", "counsellor", "viewer")),
    db: Session = Depends(get_db),
) -> APIResponse[ModelMetricsData]:
    """Retrieve stored evaluation metrics, confusion matrix, and threshold settings."""
    metrics_data = get_model_metrics(db=db, model_version=model_version)
    return success_response(
        message=f"Evaluation metrics retrieved for model '{metrics_data.model_version}'.",
        data=metrics_data,
        contains_synthetic_data=metrics_data.is_demo_model or has_any_synthetic_students(db),
    )

