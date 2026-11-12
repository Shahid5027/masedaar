"""Dropout risk prediction execution and query endpoints."""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import User
from models.schemas import (
    APIResponse,
    PredictionListData,
    PredictionRunData,
    PredictionRunRequest,
)
from services.auth_service import require_roles
from services.data_service import has_any_synthetic_students
from services.prediction_service import list_predictions, run_predictions
from services.response import success_response

router = APIRouter(prefix="/predictions", tags=["Predictions & Risk Scoring"])


@router.post("/run", response_model=APIResponse[PredictionRunData])
def run_predictions_endpoint(
    request: Optional[PredictionRunRequest] = Body(default=None),
    _admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[PredictionRunData]:
    """Score students' latest snapshots with the trained pipeline and persist results."""
    pred_req = request or PredictionRunRequest()
    result = run_predictions(db=db, request=pred_req)
    demo_tag = " [DEMO]" if result.is_demo_model else ""
    return success_response(
        message=(
            f"Generated and stored {result.total_predicted} prediction(s) using "
            f"'{result.model_version}'.{demo_tag}"
        ),
        data=result,
        contains_synthetic_data=result.is_demo_model or has_any_synthetic_students(db),
    )


@router.get("", response_model=APIResponse[PredictionListData])
def list_predictions_endpoint(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    page: Optional[int] = Query(default=None, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1, le=500),
    student_id: Optional[str] = Query(default=None, max_length=64),
    search: Optional[str] = Query(default=None, max_length=64),
    risk_level: Optional[Literal["low", "medium", "high"]] = Query(default=None),
    model_version: Optional[str] = Query(default=None, max_length=64),
    is_demo: Optional[bool] = Query(default=None),
    predicted_from: Optional[datetime] = Query(default=None),
    predicted_to: Optional[datetime] = Query(default=None),
    latest_only: bool = Query(
        default=True,
        description="When true, return only the latest prediction per student.",
    ),
    sort_by: Literal["risk_score", "predicted_at", "student_id"] = Query(default="risk_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    _user: User = Depends(require_roles("administrator", "counsellor", "viewer")),
    db: Session = Depends(get_db),
) -> APIResponse[PredictionListData]:
    """Query persisted predictions with explanations, combined filters, and pagination."""
    effective_limit = page_size if page_size is not None else limit
    effective_offset = ((page - 1) * effective_limit) if page is not None else offset

    data, contains_synthetic = list_predictions(
        db=db,
        limit=effective_limit,
        offset=effective_offset,
        student_id=student_id,
        search=search,
        risk_level=risk_level,
        model_version=model_version,
        is_demo=is_demo,
        predicted_from=predicted_from,
        predicted_to=predicted_to,
        latest_only=latest_only,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return success_response(
        message=f"Retrieved {len(data.items)} prediction(s) (total matching: {data.total}).",
        data=data,
        contains_synthetic_data=contains_synthetic,
    )

