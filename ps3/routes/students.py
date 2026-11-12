"""Student listing and detailed profile endpoints preserving shared student_id."""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import User
from models.schemas import (
    APIResponse,
    StudentDetailData,
    StudentExplanationData,
    StudentInterventionsData,
    StudentListData,
)
from services.auth_service import require_roles
from services.data_service import get_student_detail, list_students
from services.intervention_service import list_student_interventions
from services.prediction_service import get_student_explanation
from services.response import success_response

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("", response_model=APIResponse[StudentListData])
def list_students_endpoint(
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of students per page."),
    offset: int = Query(default=0, ge=0, description="Pagination offset."),
    page: Optional[int] = Query(default=None, ge=1, description="Optional 1-based page number."),
    page_size: Optional[int] = Query(
        default=None, ge=1, le=500, description="Optional page size overriding limit."
    ),
    is_synthetic: Optional[bool] = Query(
        default=None,
        description="Filter by synthetic demo flag (true = synthetic only, false = real only).",
    ),
    search: Optional[str] = Query(
        default=None,
        max_length=64,
        description="Case-insensitive substring search on shared student_id.",
    ),
    risk_level: Optional[Literal["low", "medium", "high", "unscored"]] = Query(
        default=None,
        description="Filter by latest predicted risk tier or 'unscored'.",
    ),
    min_attendance: Optional[float] = Query(default=None, ge=0.0, le=100.0),
    max_attendance: Optional[float] = Query(default=None, ge=0.0, le=100.0),
    min_failures: Optional[int] = Query(default=None, ge=0),
    predicted_from: Optional[datetime] = Query(default=None),
    predicted_to: Optional[datetime] = Query(default=None),
    sort_by: Literal[
        "student_id",
        "updated_at",
        "attendance_rate",
        "average_grade",
        "missing_assignments",
        "previous_failure_count",
        "risk_score",
        "predicted_at",
    ] = Query(default="student_id"),
    sort_order: Literal["asc", "desc"] = Query(default="asc"),
    _user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[StudentListData]:
    """Return paginated student records joined with latest features and latest risk score."""
    effective_limit = page_size if page_size is not None else limit
    effective_offset = ((page - 1) * effective_limit) if page is not None else offset

    data, contains_synthetic = list_students(
        db=db,
        limit=effective_limit,
        offset=effective_offset,
        is_synthetic=is_synthetic,
        search=search,
        risk_level=risk_level,
        min_attendance=min_attendance,
        max_attendance=max_attendance,
        min_failures=min_failures,
        predicted_from=predicted_from,
        predicted_to=predicted_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return success_response(
        message=f"Retrieved {len(data.items)} student record(s) (total matching: {data.total}).",
        data=data,
        contains_synthetic_data=contains_synthetic,
    )


@router.get("/{student_id}", response_model=APIResponse[StudentDetailData])
def get_student_endpoint(
    student_id: str,
    _user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[StudentDetailData]:
    """Return full activity snapshot history, predictions, and interventions for a shared student_id."""
    detail, contains_synthetic = get_student_detail(db=db, student_id=student_id)
    synthetic_tag = " [SYNTHETIC DEMO RECORD]" if detail.is_synthetic else ""
    return success_response(
        message=f"Student '{detail.student_id}' retrieved successfully.{synthetic_tag}",
        data=detail,
        contains_synthetic_data=contains_synthetic,
    )


@router.get("/{student_id}/explanation", response_model=APIResponse[StudentExplanationData])
def get_student_explanation_endpoint(
    student_id: str,
    _user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[StudentExplanationData]:
    """Return latest risk prediction, contributing indicators, and advisory recommendations."""
    data, contains_synthetic = get_student_explanation(db=db, student_id=student_id)
    demo_tag = " [DEMO]" if data.prediction.is_demo else ""
    return success_response(
        message=f"Explanation retrieved for student '{data.student_id}'.{demo_tag}",
        data=data,
        contains_synthetic_data=contains_synthetic,
    )


@router.get("/{student_id}/interventions", response_model=APIResponse[StudentInterventionsData])
def get_student_interventions_endpoint(
    student_id: str,
    _user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[StudentInterventionsData]:
    """Return all interventions associated with a shared student_id."""
    data, contains_synthetic = list_student_interventions(db=db, student_id=student_id)
    return success_response(
        message=f"Retrieved {data.total} intervention(s) for student '{data.student_id}'.",
        data=data,
        contains_synthetic_data=contains_synthetic,
    )

