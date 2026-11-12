"""Persistent intervention lifecycle workflow, state transitions, and audit history."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.orm import Session

from models.db_models import Intervention, InterventionHistory, Prediction, Student, User
from models.schemas import (
    ErrorDetail,
    InterventionArchiveRequest,
    InterventionCreateRequest,
    InterventionDetailData,
    InterventionHistoryListData,
    InterventionHistoryOut,
    InterventionListData,
    InterventionPriority,
    InterventionRecordOut,
    InterventionStatus,
    InterventionSummaryCounts,
    InterventionUpdateRequest,
    PredictionOut,
    StudentInterventionsData,
)
from services.auth_service import record_security_event
from services.constants import HUMAN_REVIEW_NOTICE
from services.data_service import has_any_synthetic_students
from services.notification_service import notify_intervention_lifecycle_change
from services.response import PS3APIError

AUTH_ENFORCED_NOTICE = (
    "Authenticated actor identity verified via server-side session and role-based access control."
)

TERMINAL_STATUSES = {"COMPLETED", "CANCELLED"}
PENDING_EQUIVALENTS = {"PENDING", "pending_review", "planned"}

ALLOWED_TRANSITIONS: Dict[str, Tuple[InterventionStatus, ...]] = {
    "PENDING": ("PENDING", "ASSIGNED", "IN_PROGRESS", "FOLLOW_UP_REQUIRED", "COMPLETED", "CANCELLED"),
    "ASSIGNED": ("ASSIGNED", "IN_PROGRESS", "FOLLOW_UP_REQUIRED", "COMPLETED", "CANCELLED", "PENDING"),
    "IN_PROGRESS": ("IN_PROGRESS", "ASSIGNED", "FOLLOW_UP_REQUIRED", "COMPLETED", "CANCELLED"),
    "FOLLOW_UP_REQUIRED": ("FOLLOW_UP_REQUIRED", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CANCELLED"),
    "COMPLETED": ("COMPLETED", "IN_PROGRESS", "FOLLOW_UP_REQUIRED"),
    "CANCELLED": ("CANCELLED", "PENDING", "ASSIGNED"),
}


def normalize_intervention_status(raw_status: str) -> InterventionStatus:
    """Map persisted status values (including Phase 1/2 legacy names) to canonical statuses."""
    cleaned = (raw_status or "").strip()
    upper = cleaned.upper()
    if cleaned in {"pending_review", "planned"} or upper in {"PENDING", "PENDING_REVIEW", "PLANNED"}:
        return "PENDING"
    if upper in {"ASSIGNED", "IN_PROGRESS", "FOLLOW_UP_REQUIRED", "COMPLETED", "CANCELLED"}:
        return upper  # type: ignore[return-value]
    return "PENDING"


def _normalize_priority(raw_priority: Optional[str]) -> InterventionPriority:
    """Normalize persisted priority strings cleanly."""
    low = (raw_priority or "medium").strip().lower()
    if low in {"high", "medium", "low"}:
        return low  # type: ignore[return-value]
    return "medium"


def _iso_or_none(dt: Optional[datetime]) -> Optional[str]:
    """Serialize datetimes cleanly for JSON audit history snapshots."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def compute_pagination_meta(total: int, limit: int, offset: int) -> Tuple[int, int, int, bool, bool]:
    """Return (page, page_size, total_pages, has_next, has_previous)."""
    page_size = max(1, limit)
    page = (offset // page_size) + 1
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    has_previous = offset > 0
    has_next = (offset + page_size) < total
    return page, page_size, total_pages, has_next, has_previous


def compute_status_counts(
    db: Session,
    student_id: Optional[str] = None,
    include_archived: bool = False,
) -> InterventionSummaryCounts:
    """Compute real database status breakdown and due follow-up counts."""
    now = datetime.now(timezone.utc)
    stmt = select(Intervention)
    if not include_archived:
        stmt = stmt.where(Intervention.is_archived.is_(False))
    if student_id:
        stmt = stmt.where(Intervention.student_id == student_id.strip())
    rows = db.scalars(stmt).all()

    counts = {
        "total": len(rows),
        "pending": 0,
        "assigned": 0,
        "in_progress": 0,
        "follow_up_required": 0,
        "follow_ups_due": 0,
        "completed": 0,
        "cancelled": 0,
    }
    for intr in rows:
        canon = normalize_intervention_status(intr.status)
        if canon == "PENDING":
            counts["pending"] += 1
        elif canon == "ASSIGNED":
            counts["assigned"] += 1
        elif canon == "IN_PROGRESS":
            counts["in_progress"] += 1
        elif canon == "FOLLOW_UP_REQUIRED":
            counts["follow_up_required"] += 1
        elif canon == "COMPLETED":
            counts["completed"] += 1
        elif canon == "CANCELLED":
            counts["cancelled"] += 1

        if intr.follow_up_date is not None and canon not in TERMINAL_STATUSES:
            fup = intr.follow_up_date
            if fup.tzinfo is None:
                fup = fup.replace(tzinfo=timezone.utc)
            if fup <= now:
                counts["follow_ups_due"] += 1

    return InterventionSummaryCounts(**counts)


def _hydrate_interventions(
    db: Session,
    interventions: List[Intervention],
) -> List[InterventionRecordOut]:
    """Enrich Intervention ORM rows with latest student prediction context and history counts."""
    if not interventions:
        return []

    student_ids = list({i.student_id for i in interventions})
    intr_ids = [i.id for i in interventions]

    # Latest prediction per student_id
    latest_pred_sq = (
        select(
            Prediction.student_id.label("student_id"),
            func.max(Prediction.id).label("latest_id"),
        )
        .where(Prediction.student_id.in_(student_ids))
        .group_by(Prediction.student_id)
        .subquery()
    )
    latest_preds = {
        p.student_id: p
        for p in db.scalars(
            select(Prediction).join(latest_pred_sq, Prediction.id == latest_pred_sq.c.latest_id)
        ).all()
    }

    history_counts = dict(
        db.execute(
            select(InterventionHistory.intervention_id, func.count(InterventionHistory.id))
            .where(InterventionHistory.intervention_id.in_(intr_ids))
            .group_by(InterventionHistory.intervention_id)
        ).all()
    )

    records: List[InterventionRecordOut] = []
    for item in interventions:
        pred = latest_preds.get(item.student_id)
        records.append(
            InterventionRecordOut(
                id=item.id,
                student_id=item.student_id,
                prediction_id=item.prediction_id,
                intervention_type=item.intervention_type,
                recommended_action=item.recommended_action,
                priority=_normalize_priority(item.priority),
                status=normalize_intervention_status(item.status),
                raw_status=item.status,
                assigned_to=item.assigned_to,
                follow_up_date=item.follow_up_date,
                completed_at=item.completed_at,
                notes=item.notes,
                is_demo=bool(item.is_demo),
                version=int(item.version),
                is_archived=bool(item.is_archived),
                archived_at=item.archived_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
                latest_risk_level=pred.risk_level if pred else None,  # type: ignore[arg-type]
                latest_risk_probability=round(float(pred.risk_score), 4) if pred else None,
                history_count=int(history_counts.get(item.id, 0)),
                human_review_notice=HUMAN_REVIEW_NOTICE,
            )
        )
    return records


def _get_intervention_or_404(db: Session, intervention_id: int) -> Intervention:
    """Fetch an Intervention row or raise 404 INTERVENTION_NOT_FOUND."""
    item = db.get(Intervention, intervention_id)
    if item is None:
        raise PS3APIError(
            status_code=404,
            message=f"Intervention #{intervention_id} was not found.",
            errors=[
                ErrorDetail(
                    code="INTERVENTION_NOT_FOUND",
                    message=f"No intervention record exists with id={intervention_id}.",
                )
            ],
            contains_synthetic_data=has_any_synthetic_students(db),
        )
    return item


def _record_history(
    db: Session,
    intervention: Intervention,
    action: str,
    previous_value: Optional[Dict[str, Any]],
    new_value: Optional[Dict[str, Any]],
    summary: str,
    created_at: datetime,
    actor: Optional[User] = None,
    system_actor_id: Optional[str] = None,
) -> InterventionHistory:
    """Append an immutable audit entry using verified backend actor identity."""
    verified_actor_id = actor.username if actor is not None else system_actor_id
    entry = InterventionHistory(
        intervention_id=intervention.id,
        student_id=intervention.student_id,
        action=action,
        actor_id=verified_actor_id,
        actor_user_id=actor.id if actor is not None else None,
        actor_role=actor.role if actor is not None else ("system" if system_actor_id else None),
        previous_value=previous_value,
        new_value=new_value,
        summary=summary,
        created_at=created_at,
    )
    db.add(entry)
    return entry


def _user_matches_assignee(user: User, assigned_to: Optional[str]) -> bool:
    """Check whether assigned_to refers to the authenticated counsellor."""
    if not assigned_to or not assigned_to.strip():
        return False
    target = assigned_to.strip().lower()
    return target in {
        user.username.lower(),
        user.full_name.lower(),
        user.email.lower(),
    }


def _assert_user_can_modify_intervention(
    intr: Intervention,
    current_user: User,
    requested_assignee: Optional[str] = None,
    assignee_supplied: bool = False,
) -> None:
    """Enforce counsellor vs administrator ownership boundaries on intervention edits."""
    if current_user.role == "administrator":
        return
    if current_user.role != "counsellor":
        raise PS3APIError(
            status_code=403,
            message="You do not have permission to modify interventions.",
            errors=[
                ErrorDetail(
                    code="INSUFFICIENT_PERMISSIONS",
                    message="Only administrators and authorized counsellors can modify interventions.",
                )
            ],
        )

    if intr.assigned_to is not None and not _user_matches_assignee(current_user, intr.assigned_to):
        raise PS3APIError(
            status_code=403,
            message="You cannot modify an intervention assigned to another counsellor.",
            errors=[
                ErrorDetail(
                    code="INSUFFICIENT_PERMISSIONS",
                    message=(
                        f"Intervention #{intr.id} is assigned to '{intr.assigned_to}'. "
                        "Counsellors may only update unassigned cases or cases assigned to them."
                    ),
                )
            ],
        )

    if assignee_supplied and requested_assignee is not None and requested_assignee.strip():
        if not _user_matches_assignee(current_user, requested_assignee):
            raise PS3APIError(
                status_code=403,
                message="Counsellors cannot reassign interventions to another counsellor.",
                errors=[
                    ErrorDetail(
                        code="INSUFFICIENT_PERMISSIONS",
                        column="assigned_to",
                        message="Only administrators can assign or reassign cases to other staff members.",
                    )
                ],
            )


def list_interventions(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    student_id: Optional[str] = None,
    status: Optional[InterventionStatus] = None,
    priority: Optional[InterventionPriority] = None,
    assigned_to: Optional[str] = None,
    is_demo: Optional[bool] = None,
    include_archived: bool = False,
    search: Optional[str] = None,
    overdue_only: bool = False,
    sort_by: Literal["created_at", "updated_at", "follow_up_date", "priority", "student_id", "status"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> Tuple[InterventionListData, bool]:
    """List interventions with server-side filters, sorting, pagination, and real status counts."""
    stmt = select(Intervention)
    conditions = []

    if not include_archived:
        conditions.append(Intervention.is_archived.is_(False))
    if student_id and student_id.strip():
        conditions.append(Intervention.student_id == student_id.strip())
    if status:
        if status == "PENDING":
            conditions.append(Intervention.status.in_(list(PENDING_EQUIVALENTS)))
        else:
            conditions.append(Intervention.status == status)
    if priority:
        conditions.append(Intervention.priority == priority)
    if assigned_to and assigned_to.strip():
        conditions.append(Intervention.assigned_to.ilike(f"%{assigned_to.strip()}%"))
    if is_demo is not None:
        conditions.append(Intervention.is_demo.is_(is_demo))
    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append(
            or_(
                Intervention.student_id.ilike(term),
                Intervention.intervention_type.ilike(term),
                Intervention.recommended_action.ilike(term),
                Intervention.assigned_to.ilike(term),
            )
        )
    if overdue_only:
        now = datetime.now(timezone.utc)
        conditions.append(Intervention.follow_up_date.is_not(None))
        conditions.append(Intervention.follow_up_date <= now)
        conditions.append(~Intervention.status.in_(list(TERMINAL_STATUSES)))

    if conditions:
        stmt = stmt.where(and_(*conditions))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    priority_rank = case(
        (Intervention.priority == "high", 3),
        (Intervention.priority == "medium", 2),
        (Intervention.priority == "low", 1),
        else_=0,
    )
    sort_map = {
        "created_at": Intervention.created_at,
        "updated_at": Intervention.updated_at,
        "follow_up_date": Intervention.follow_up_date,
        "priority": priority_rank,
        "student_id": Intervention.student_id,
        "status": Intervention.status,
    }
    sort_col = sort_map.get(sort_by, Intervention.created_at)
    order_expr = sort_col.desc() if sort_order == "desc" else sort_col.asc()
    if sort_by == "follow_up_date":
        # Push NULL follow-up dates after scheduled dates regardless of sort direction.
        order_expr = sort_col.desc().nulls_last() if sort_order == "desc" else sort_col.asc().nulls_last()

    rows = db.scalars(
        stmt.order_by(order_expr, Intervention.id.desc()).limit(limit).offset(offset)
    ).all()

    items = _hydrate_interventions(db, list(rows))
    status_counts = compute_status_counts(db, student_id=student_id)
    page, page_size, total_pages, has_next, has_previous = compute_pagination_meta(
        total=total, limit=limit, offset=offset
    )
    contains_synthetic = has_any_synthetic_students(db) or any(i.is_demo for i in items)

    return (
        InterventionListData(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
            status_counts=status_counts,
        ),
        contains_synthetic,
    )


def get_intervention_detail(db: Session, intervention_id: int) -> Tuple[InterventionDetailData, bool]:
    """Return one intervention with related student, prediction, history, and allowed transitions."""
    item = _get_intervention_or_404(db, intervention_id)
    student = db.get(Student, item.student_id)
    hydrated = _hydrate_interventions(db, [item])[0]

    related_pred: Optional[PredictionOut] = None
    if item.prediction_id is not None:
        pred_row = db.get(Prediction, item.prediction_id)
        if pred_row is not None:
            related_pred = PredictionOut.model_validate(pred_row)

    history_rows = db.scalars(
        select(InterventionHistory)
        .where(InterventionHistory.intervention_id == item.id)
        .order_by(InterventionHistory.created_at.asc(), InterventionHistory.id.asc())
    ).all()

    canon = normalize_intervention_status(item.status)
    allowed_next = list(ALLOWED_TRANSITIONS.get(canon, (canon,)))
    student_synth = bool(student.is_synthetic) if student is not None else bool(item.is_demo)
    contains_synthetic = student_synth or bool(item.is_demo) or has_any_synthetic_students(db)

    return (
        InterventionDetailData(
            intervention=hydrated,
            student_is_synthetic=student_synth,
            related_prediction=related_pred,
            history=[InterventionHistoryOut.model_validate(h) for h in history_rows],
            allowed_next_statuses=allowed_next,
            auth_notice=AUTH_ENFORCED_NOTICE,
        ),
        contains_synthetic,
    )


def get_intervention_history(
    db: Session, intervention_id: int
) -> Tuple[InterventionHistoryListData, bool]:
    """Return chronological audit log for a single intervention."""
    item = _get_intervention_or_404(db, intervention_id)
    history_rows = db.scalars(
        select(InterventionHistory)
        .where(InterventionHistory.intervention_id == item.id)
        .order_by(InterventionHistory.created_at.asc(), InterventionHistory.id.asc())
    ).all()
    return (
        InterventionHistoryListData(
            intervention_id=item.id,
            student_id=item.student_id,
            items=[InterventionHistoryOut.model_validate(h) for h in history_rows],
            total=len(history_rows),
        ),
        bool(item.is_demo) or has_any_synthetic_students(db),
    )


def list_student_interventions(
    db: Session, student_id: str, include_archived: bool = False
) -> Tuple[StudentInterventionsData, bool]:
    """Return all interventions for a shared student_id or raise 404 if student missing."""
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

    stmt = select(Intervention).where(Intervention.student_id == clean_id)
    if not include_archived:
        stmt = stmt.where(Intervention.is_archived.is_(False))
    rows = db.scalars(stmt.order_by(Intervention.created_at.desc(), Intervention.id.desc())).all()
    hydrated = _hydrate_interventions(db, list(rows))
    counts = compute_status_counts(db, student_id=clean_id, include_archived=include_archived)
    contains_synthetic = student.is_synthetic or has_any_synthetic_students(db)
    return (
        StudentInterventionsData(
            student_id=student.student_id,
            is_synthetic=student.is_synthetic,
            items=hydrated,
            total=len(hydrated),
            status_counts=counts,
            human_review_notice=HUMAN_REVIEW_NOTICE,
        ),
        contains_synthetic,
    )


def create_intervention(
    db: Session, request: InterventionCreateRequest, current_user: User
) -> Tuple[InterventionRecordOut, bool]:
    """Create a persistent counselor intervention and verified audit record in a transaction."""
    clean_sid = request.student_id.strip()
    student = db.get(Student, clean_sid)
    if student is None:
        raise PS3APIError(
            status_code=404,
            message=f"Student '{clean_sid}' not found.",
            errors=[
                ErrorDetail(
                    code="STUDENT_NOT_FOUND",
                    student_id=clean_sid,
                    message=f"Cannot create intervention: shared student_id '{clean_sid}' does not exist.",
                )
            ],
            contains_synthetic_data=has_any_synthetic_students(db),
        )

    is_demo = bool(student.is_synthetic)
    if request.prediction_id is not None:
        pred = db.get(Prediction, request.prediction_id)
        if pred is None:
            raise PS3APIError(
                status_code=404,
                message=f"Prediction #{request.prediction_id} not found.",
                errors=[
                    ErrorDetail(
                        code="PREDICTION_NOT_FOUND",
                        message=f"No prediction exists with id={request.prediction_id}.",
                    )
                ],
                contains_synthetic_data=student.is_synthetic or has_any_synthetic_students(db),
            )
        if pred.student_id != clean_sid:
            raise PS3APIError(
                status_code=422,
                message=(
                    f"Prediction #{request.prediction_id} belongs to '{pred.student_id}', "
                    f"not '{clean_sid}'."
                ),
                errors=[
                    ErrorDetail(
                        code="PREDICTION_STUDENT_MISMATCH",
                        column="prediction_id",
                        student_id=clean_sid,
                        message="prediction_id must belong to the target student_id.",
                    )
                ],
                contains_synthetic_data=student.is_synthetic or has_any_synthetic_students(db),
            )
        is_demo = bool(is_demo or pred.is_synthetic_input)

    clean_type = request.intervention_type.strip()
    clean_action = request.recommended_action.strip()
    clean_assignee = (
        request.assigned_to.strip()
        if request.assigned_to and request.assigned_to.strip()
        else None
    )
    if (
        current_user.role == "counsellor"
        and clean_assignee is not None
        and not _user_matches_assignee(current_user, clean_assignee)
    ):
        raise PS3APIError(
            status_code=403,
            message="Counsellors cannot assign newly created cases to other staff members.",
            errors=[
                ErrorDetail(
                    code="INSUFFICIENT_PERMISSIONS",
                    column="assigned_to",
                    message="Leave assigned_to unassigned, assign to yourself, or request an administrator.",
                )
            ],
        )

    clean_notes = request.notes.strip() if request.notes and request.notes.strip() else None

    if not request.allow_duplicate:
        dup_conditions = [
            Intervention.student_id == clean_sid,
            Intervention.intervention_type == clean_type,
            Intervention.is_archived.is_(False),
            ~Intervention.status.in_(list(TERMINAL_STATUSES)),
        ]
        if request.prediction_id is not None:
            dup_conditions.append(Intervention.prediction_id == request.prediction_id)
        else:
            dup_conditions.append(Intervention.recommended_action == clean_action)

        existing = db.scalars(select(Intervention).where(and_(*dup_conditions)).limit(1)).first()
        if existing is not None:
            raise PS3APIError(
                status_code=409,
                message=(
                    f"An active '{clean_type}' intervention (#{existing.id}) already exists "
                    f"for student '{clean_sid}'."
                ),
                errors=[
                    ErrorDetail(
                        code="DUPLICATE_ACTIVE_INTERVENTION",
                        student_id=clean_sid,
                        message=(
                            f"Active intervention #{existing.id} already covers this action. "
                            "Update the existing intervention or pass allow_duplicate=true."
                        ),
                    )
                ],
                contains_synthetic_data=is_demo or has_any_synthetic_students(db),
            )

    initial_status: InterventionStatus = request.status or (
        "ASSIGNED" if clean_assignee is not None else "PENDING"
    )
    now = datetime.now(timezone.utc)
    completed_at = now if initial_status == "COMPLETED" else None

    try:
        intr = Intervention(
            student_id=clean_sid,
            prediction_id=request.prediction_id,
            intervention_type=clean_type,
            recommended_action=clean_action,
            priority=request.priority,
            status=initial_status,
            assigned_to=clean_assignee,
            follow_up_date=request.follow_up_date,
            completed_at=completed_at,
            notes=clean_notes,
            is_demo=is_demo,
            version=1,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        db.add(intr)
        db.flush()

        _record_history(
            db=db,
            intervention=intr,
            action="INTERVENTION_CREATED",
            actor=current_user,
            previous_value=None,
            new_value={
                "status": initial_status,
                "priority": request.priority,
                "assigned_to": clean_assignee,
                "follow_up_date": _iso_or_none(request.follow_up_date),
                "intervention_type": clean_type,
                "version": 1,
            },
            summary=f"Intervention created ({clean_type}, status={initial_status}, priority={request.priority}).",
            created_at=now,
        )
        if clean_assignee:
            _record_history(
                db=db,
                intervention=intr,
                action="COUNSELLOR_ASSIGNED",
                actor=current_user,
                previous_value={"assigned_to": None},
                new_value={"assigned_to": clean_assignee},
                summary=f"Assigned to counsellor '{clean_assignee}'.",
                created_at=now,
            )
        if request.follow_up_date is not None:
            _record_history(
                db=db,
                intervention=intr,
                action="FOLLOW_UP_SCHEDULED",
                actor=current_user,
                previous_value={"follow_up_date": None},
                new_value={"follow_up_date": _iso_or_none(request.follow_up_date)},
                summary=f"Follow-up scheduled for {_iso_or_none(request.follow_up_date)}.",
                created_at=now,
            )

        db.commit()
        db.refresh(intr)
    except Exception:
        db.rollback()
        raise

    if clean_assignee:
        notify_intervention_lifecycle_change(
            db,
            intervention=intr,
            previous_status="PENDING",
            new_status=initial_status,
            previous_assigned_to=None,
            new_assigned_to=clean_assignee,
        )

    record = _hydrate_interventions(db, [intr])[0]
    return record, is_demo or has_any_synthetic_students(db)


def update_intervention(
    db: Session,
    intervention_id: int,
    request: InterventionUpdateRequest,
    current_user: User,
) -> Tuple[InterventionRecordOut, bool]:
    """Update intervention with RBAC checks, optimistic concurrency control, and audit logging."""
    intr = _get_intervention_or_404(db, intervention_id)
    if intr.is_archived:
        raise PS3APIError(
            status_code=409,
            message=f"Intervention #{intr.id} is archived and cannot be edited directly.",
            errors=[
                ErrorDetail(
                    code="INTERVENTION_ARCHIVED",
                    message="Archived interventions are read-only for accountability retention.",
                )
            ],
            contains_synthetic_data=bool(intr.is_demo) or has_any_synthetic_students(db),
        )

    fields_set = request.model_fields_set
    _assert_user_can_modify_intervention(
        intr=intr,
        current_user=current_user,
        requested_assignee=request.assigned_to if "assigned_to" in fields_set else None,
        assignee_supplied="assigned_to" in fields_set,
    )

    if int(intr.version) != request.version:
        raise PS3APIError(
            status_code=409,
            message=(
                f"Intervention #{intr.id} was modified by another user (your version: "
                f"{request.version}, current version: {intr.version}). Refresh and review "
                "the latest state before saving."
            ),
            errors=[
                ErrorDetail(
                    code="INTERVENTION_VERSION_CONFLICT",
                    column="version",
                    value=str(intr.version),
                    message=f"Expected version {intr.version}, got {request.version}.",
                )
            ],
            contains_synthetic_data=bool(intr.is_demo) or has_any_synthetic_students(db),
        )

    now = datetime.now(timezone.utc)
    current_status = normalize_intervention_status(intr.status)
    target_status: InterventionStatus = current_status
    previous_assigned_to = intr.assigned_to

    if "status" in fields_set and request.status is not None:
        allowed = ALLOWED_TRANSITIONS.get(current_status, (current_status,))
        if request.status not in allowed:
            raise PS3APIError(
                status_code=422,
                message=(
                    f"Cannot transition intervention #{intr.id} from '{current_status}' "
                    f"to '{request.status}'."
                ),
                errors=[
                    ErrorDetail(
                        code="INVALID_STATUS_TRANSITION",
                        column="status",
                        value=request.status,
                        message=f"Allowed next statuses from {current_status}: {', '.join(allowed)}.",
                    )
                ],
                contains_synthetic_data=bool(intr.is_demo) or has_any_synthetic_students(db),
            )
        target_status = request.status

    new_assignee = intr.assigned_to
    new_priority = _normalize_priority(intr.priority)
    new_action = intr.recommended_action
    new_follow_up = intr.follow_up_date
    new_notes = intr.notes
    new_completed_at = intr.completed_at

    history_events: List[Tuple[str, Optional[Dict[str, Any]], Optional[Dict[str, Any]], str]] = []

    if "assigned_to" in fields_set:
        candidate_assignee = (
            request.assigned_to.strip()
            if request.assigned_to is not None and request.assigned_to.strip()
            else None
        )
        if candidate_assignee != intr.assigned_to:
            history_events.append(
                (
                    "COUNSELLOR_ASSIGNED",
                    {"assigned_to": intr.assigned_to},
                    {"assigned_to": candidate_assignee},
                    (
                        f"Assigned to counsellor '{candidate_assignee}'."
                        if candidate_assignee
                        else "Cleared counsellor assignment."
                    ),
                )
            )
            new_assignee = candidate_assignee
            if (
                candidate_assignee is not None
                and current_status == "PENDING"
                and "status" not in fields_set
            ):
                target_status = "ASSIGNED"

    if "priority" in fields_set and request.priority is not None:
        if request.priority != _normalize_priority(intr.priority):
            history_events.append(
                (
                    "PRIORITY_CHANGED",
                    {"priority": _normalize_priority(intr.priority)},
                    {"priority": request.priority},
                    f"Priority updated from '{intr.priority}' to '{request.priority}'.",
                )
            )
            new_priority = request.priority

    if "recommended_action" in fields_set and request.recommended_action is not None:
        candidate_action = request.recommended_action.strip()
        if candidate_action and candidate_action != intr.recommended_action:
            history_events.append(
                (
                    "DESCRIPTION_UPDATED",
                    {"recommended_action": intr.recommended_action},
                    {"recommended_action": candidate_action},
                    "Updated intervention action description.",
                )
            )
            new_action = candidate_action

    if "follow_up_date" in fields_set:
        old_fup = _iso_or_none(intr.follow_up_date)
        new_fup = _iso_or_none(request.follow_up_date)
        if old_fup != new_fup:
            history_events.append(
                (
                    "FOLLOW_UP_SCHEDULED",
                    {"follow_up_date": old_fup},
                    {"follow_up_date": new_fup},
                    (
                        f"Follow-up scheduled for {new_fup}."
                        if new_fup
                        else "Cleared scheduled follow-up date."
                    ),
                )
            )
            new_follow_up = request.follow_up_date

    if "notes" in fields_set:
        candidate_notes = (
            request.notes.strip()
            if request.notes is not None and request.notes.strip()
            else None
        )
        if candidate_notes != intr.notes:
            history_events.append(
                (
                    "NOTES_UPDATED",
                    {"notes": intr.notes},
                    {"notes": candidate_notes},
                    "Added or updated counsellor notes."
                    if candidate_notes
                    else "Cleared counsellor notes.",
                )
            )
            new_notes = candidate_notes

    if target_status != current_status or intr.status != target_status:
        if target_status == "COMPLETED":
            action_name = "INTERVENTION_COMPLETED"
            new_completed_at = now
            summary = f"Marked intervention completed (previous status: {current_status})."
        elif current_status in TERMINAL_STATUSES and target_status not in TERMINAL_STATUSES:
            action_name = "INTERVENTION_REOPENED"
            new_completed_at = None
            summary = f"Reopened intervention from '{current_status}' to '{target_status}'."
        else:
            action_name = "STATUS_CHANGED"
            summary = f"Status changed from '{current_status}' to '{target_status}'."

        history_events.append(
            (
                action_name,
                {"status": current_status},
                {"status": target_status},
                summary,
            )
        )

    expected_version = int(intr.version)
    next_version = expected_version + 1

    try:
        update_stmt = (
            update(Intervention)
            .where(
                Intervention.id == intr.id,
                Intervention.version == expected_version,
            )
            .values(
                assigned_to=new_assignee,
                priority=new_priority,
                recommended_action=new_action,
                follow_up_date=new_follow_up,
                notes=new_notes,
                status=target_status,
                completed_at=new_completed_at,
                updated_at=now,
                version=next_version,
            )
        )
        res = db.execute(update_stmt)
        if res.rowcount != 1:
            db.rollback()
            fresh = db.get(Intervention, intervention_id)
            actual_ver = fresh.version if fresh is not None else expected_version
            raise PS3APIError(
                status_code=409,
                message=(
                    f"Concurrent modification detected on intervention #{intervention_id}. "
                    f"Latest version is {actual_ver}; refresh before retrying."
                ),
                errors=[
                    ErrorDetail(
                        code="INTERVENTION_VERSION_CONFLICT",
                        column="version",
                        value=str(actual_ver),
                        message=f"Expected version {actual_ver}, got {expected_version}.",
                    )
                ],
                contains_synthetic_data=bool(intr.is_demo) or has_any_synthetic_students(db),
            )

        for action_name, prev_val, new_val, summary in history_events:
            enriched_prev = {**(prev_val or {}), "version": expected_version}
            enriched_new = {**(new_val or {}), "version": next_version}
            _record_history(
                db=db,
                intervention=intr,
                action=action_name,
                actor=current_user,
                previous_value=enriched_prev,
                new_value=enriched_new,
                summary=summary,
                created_at=now,
            )

        db.commit()
        db.expire(intr)
        intr = _get_intervention_or_404(db, intervention_id)
    except Exception:
        db.rollback()
        raise

    notify_intervention_lifecycle_change(
        db,
        intervention=intr,
        previous_status=current_status,
        new_status=target_status,
        previous_assigned_to=previous_assigned_to,
        new_assigned_to=new_assignee,
    )

    record = _hydrate_interventions(db, [intr])[0]
    return record, bool(intr.is_demo) or has_any_synthetic_students(db)


def archive_intervention(
    db: Session,
    intervention_id: int,
    request: InterventionArchiveRequest,
    current_user: User,
) -> Tuple[InterventionRecordOut, bool]:
    """Soft-archive an intervention while preserving immutable audit history."""
    intr = _get_intervention_or_404(db, intervention_id)
    if intr.is_archived:
        raise PS3APIError(
            status_code=409,
            message=f"Intervention #{intr.id} is already archived.",
            errors=[ErrorDetail(code="ALREADY_ARCHIVED", message="Already archived.")],
        )
    if int(intr.version) != request.version:
        raise PS3APIError(
            status_code=409,
            message="Intervention version mismatch on archive request.",
            errors=[
                ErrorDetail(
                    code="INTERVENTION_VERSION_CONFLICT",
                    column="version",
                    value=str(intr.version),
                    message=f"Expected version {intr.version}, got {request.version}.",
                )
            ],
        )

    now = datetime.now(timezone.utc)
    expected_version = int(intr.version)
    next_version = expected_version + 1
    reason = request.reason.strip() if request.reason and request.reason.strip() else "Administrative archive"

    try:
        res = db.execute(
            update(Intervention)
            .where(Intervention.id == intr.id, Intervention.version == expected_version)
            .values(
                is_archived=True,
                archived_at=now,
                updated_at=now,
                version=next_version,
            )
        )
        if res.rowcount != 1:
            db.rollback()
            raise PS3APIError(
                status_code=409,
                message="Concurrent modification prevented archive.",
                errors=[ErrorDetail(code="INTERVENTION_VERSION_CONFLICT", message="Retry with fresh version.")],
            )
        _record_history(
            db=db,
            intervention=intr,
            action="INTERVENTION_ARCHIVED",
            actor=current_user,
            previous_value={"is_archived": False, "version": expected_version},
            new_value={"is_archived": True, "reason": reason, "version": next_version},
            summary=f"Intervention archived by '{current_user.username}': {reason}",
            created_at=now,
        )
        record_security_event(
            db,
            "INTERVENTION_ARCHIVED",
            f"Administrator '{current_user.username}' archived intervention #{intr.id}.",
            actor=current_user,
            target_type="intervention",
            target_id=str(intr.id),
            details={"reason": reason},
        )
        db.commit()
        db.expire(intr)
        intr = _get_intervention_or_404(db, intervention_id)
    except Exception:
        db.rollback()
        raise

    record = _hydrate_interventions(db, [intr])[0]
    return record, bool(intr.is_demo) or has_any_synthetic_students(db)

