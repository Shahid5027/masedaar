"""Administrator-only operational monitoring and security audit log endpoints."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import get_settings
from database import check_db_connection, get_db
from models.db_models import (
    Intervention,
    Notification,
    SecurityAuditLog,
    Student,
    TrainedModel,
    User,
    UserSession,
)
from models.schemas import (
    APIResponse,
    OperationalStatusData,
    SecurityAuditListData,
    SecurityAuditLogOut,
)
from services.auth_service import require_roles
from services.response import success_response

router = APIRouter(tags=["Operational Monitoring & Audit (Admin)"])


@router.get("/ops/status", response_model=APIResponse[OperationalStatusData])
def operational_status_endpoint(
    _admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[OperationalStatusData]:
    """Return operational system health separated from student analytics (administrator only)."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)

    db_ok = check_db_connection(db)
    bind = db.get_bind()
    dialect = bind.dialect.name if bind is not None else "unknown"

    active_model = db.scalar(
        select(TrainedModel)
        .where(TrainedModel.is_active.is_(True))
        .order_by(TrainedModel.trained_at.desc(), TrainedModel.id.desc())
        .limit(1)
    )
    artifact_ok = bool(active_model and Path(active_model.artifact_path).exists())

    active_sessions = (
        db.scalar(
            select(func.count(UserSession.id)).where(
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
                UserSession.absolute_expires_at > now,
            )
        )
        or 0
    )
    total_users = db.scalar(select(func.count(User.id))) or 0
    active_users = db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    failed_logins = (
        db.scalar(
            select(func.count(SecurityAuditLog.id)).where(
                SecurityAuditLog.event_type.in_(["LOGIN_FAILED", "LOGIN_RATE_LIMITED"]),
                SecurityAuditLog.created_at >= since_24h,
            )
        )
        or 0
    )
    failed_notifs = (
        db.scalar(
            select(func.count(Notification.id)).where(Notification.email_status == "failed")
        )
        or 0
    )
    archived_students = (
        db.scalar(select(func.count(Student.student_id)).where(Student.is_archived.is_(True)))
        or 0
    )
    archived_interventions = (
        db.scalar(select(func.count(Intervention.id)).where(Intervention.is_archived.is_(True)))
        or 0
    )

    payload = OperationalStatusData(
        service=settings.app_name,
        environment=settings.app_env,
        database_connected=db_ok,
        database_dialect=dialect,
        model_artifact_available=artifact_ok,
        active_model_version=active_model.model_version if active_model else None,
        active_sessions_count=int(active_sessions),
        total_users=int(total_users),
        active_users=int(active_users),
        failed_logins_24h=int(failed_logins),
        failed_notifications_count=int(failed_notifs),
        archived_students_count=int(archived_students),
        archived_interventions_count=int(archived_interventions),
        docs_enabled=settings.effective_docs_enabled,
        cookie_secure=settings.cookie_secure,
        email_transport=(settings.notification_email_transport or "disabled").strip().lower(),
    )
    return success_response(
        message="Operational status retrieved successfully.",
        data=payload,
    )


@router.get("/audit/security", response_model=APIResponse[SecurityAuditListData])
def list_security_audit_logs_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = Query(default=None, max_length=64),
    _admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[SecurityAuditListData]:
    """List institutional authentication and authorization audit logs (administrator only)."""
    stmt = select(SecurityAuditLog)
    if event_type and event_type.strip():
        stmt = stmt.where(SecurityAuditLog.event_type == event_type.strip())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(SecurityAuditLog.created_at.desc(), SecurityAuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return success_response(
        message=f"Retrieved {len(rows)} security audit event(s).",
        data=SecurityAuditListData(
            items=[SecurityAuditLogOut.model_validate(r) for r in rows],
            total=int(total),
        ),
    )

