"""Persistent intervention workflow, assignment, scheduling, and audit history endpoints."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import User
from models.schemas import (
    APIResponse,
    ErrorDetail,
    InterventionArchiveRequest,
    InterventionCreateRequest,
    InterventionDetailData,
    InterventionHistoryListData,
    InterventionListData,
    InterventionPriority,
    InterventionRecordOut,
    InterventionStatus,
    InterventionUpdateRequest,
)
from services.auth_service import require_roles
from services.intervention_service import (
    archive_intervention,
    create_intervention,
    get_intervention_detail,
    get_intervention_history,
    list_interventions,
    update_intervention,
)
from services.response import PS3APIError, success_response

router = APIRouter(prefix="/interventions", tags=["Interventions"])


@router.get("", response_model=APIResponse[InterventionListData])
def list_interventions_endpoint(
    limit: int = Query(default=50, ge=1, le=500, description="Page size (1–500)."),
    offset: int = Query(default=0, ge=0, description="Pagination offset."),
    page: Optional[int] = Query(default=None, ge=1, description="Optional 1-based page index."),
    page_size: Optional[int] = Query(
        default=None, ge=1, le=500, description="Optional page size overriding limit."
    ),
    student_id: Optional[str] = Query(default=None, max_length=64),
    status_filter: Optional[InterventionStatus] = Query(default=None, alias="status"),
    priority: Optional[InterventionPriority] = Query(default=None),
    assigned_to: Optional[str] = Query(default=None, max_length=128),
    is_demo: Optional[bool] = Query(default=None),
    include_archived: bool = Query(default=False),
    search: Optional[str] = Query(default=None, max_length=128),
    overdue_only: bool = Query(default=False),
    sort_by: Literal[
        "created_at",
        "updated_at",
        "follow_up_date",
        "priority",
        "student_id",
        "status",
    ] = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    current_user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[InterventionListData]:
    """List persisted counselor interventions with server-side filters, sorting, and status counts."""
    if include_archived and current_user.role != "administrator":
        raise PS3APIError(
            status_code=403,
            message="Only administrators may view archived interventions.",
            errors=[ErrorDetail(code="INSUFFICIENT_PERMISSIONS", message="Admin role required.")],
        )
    effective_limit = page_size if page_size is not None else limit
    effective_offset = ((page - 1) * effective_limit) if page is not None else offset

    data, contains_synthetic = list_interventions(
        db=db,
        limit=effective_limit,
        offset=effective_offset,
        student_id=student_id,
        status=status_filter,
        priority=priority,
        assigned_to=assigned_to,
        is_demo=is_demo,
        include_archived=include_archived,
        search=search,
        overdue_only=overdue_only,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return success_response(
        message=f"Retrieved {len(data.items)} intervention(s) (total matching: {data.total}).",
        data=data,
        contains_synthetic_data=contains_synthetic,
    )


@router.post(
    "",
    response_model=APIResponse[InterventionRecordOut],
    status_code=status.HTTP_201_CREATED,
)
def create_intervention_endpoint(
    request: InterventionCreateRequest,
    current_user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[InterventionRecordOut]:
    """Create a counselor-reviewed intervention attributed to the verified backend user."""
    record, contains_synthetic = create_intervention(
        db=db, request=request, current_user=current_user
    )
    return success_response(
        message=f"Intervention #{record.id} created for student '{record.student_id}'.",
        data=record,
        contains_synthetic_data=contains_synthetic,
    )


@router.get("/{intervention_id}", response_model=APIResponse[InterventionDetailData])
def get_intervention_detail_endpoint(
    intervention_id: int,
    _user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[InterventionDetailData]:
    """Return full details, prediction context, allowed status transitions, and history timeline."""
    data, contains_synthetic = get_intervention_detail(db=db, intervention_id=intervention_id)
    return success_response(
        message=f"Intervention #{intervention_id} retrieved successfully.",
        data=data,
        contains_synthetic_data=contains_synthetic,
    )


@router.patch("/{intervention_id}", response_model=APIResponse[InterventionRecordOut])
def update_intervention_endpoint(
    intervention_id: int,
    request: InterventionUpdateRequest,
    current_user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[InterventionRecordOut]:
    """Safely update intervention with RBAC, optimistic concurrency version check, and audit trail."""
    record, contains_synthetic = update_intervention(
        db=db, intervention_id=intervention_id, request=request, current_user=current_user
    )
    return success_response(
        message=f"Intervention #{record.id} updated (status={record.status}, version={record.version}).",
        data=record,
        contains_synthetic_data=contains_synthetic,
    )


@router.post("/{intervention_id}/archive", response_model=APIResponse[InterventionRecordOut])
def archive_intervention_endpoint(
    intervention_id: int,
    request: InterventionArchiveRequest,
    admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[InterventionRecordOut]:
    """Soft-archive an intervention while preserving immutable accountability history (admin only)."""
    record, contains_synthetic = archive_intervention(
        db=db, intervention_id=intervention_id, request=request, current_user=admin
    )
    return success_response(
        message=f"Intervention #{record.id} archived cleanly.",
        data=record,
        contains_synthetic_data=contains_synthetic,
    )


@router.get("/{intervention_id}/history", response_model=APIResponse[InterventionHistoryListData])
def get_intervention_history_endpoint(
    intervention_id: int,
    _user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[InterventionHistoryListData]:
    """Return chronological audit history entries for a single intervention."""
    data, contains_synthetic = get_intervention_history(db=db, intervention_id=intervention_id)
    return success_response(
        message=f"Retrieved {data.total} audit history entry/entries for intervention #{intervention_id}.",
        data=data,
        contains_synthetic_data=contains_synthetic,
    )

