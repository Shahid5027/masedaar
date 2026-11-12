"""In-app notification inbox, follow-up scanner, and email retry endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import User
from models.schemas import (
    APIResponse,
    NotificationListData,
    NotificationOut,
    NotificationScanData,
)
from services.auth_service import require_roles
from services.notification_service import (
    list_user_notifications,
    mark_notification_read,
    retry_failed_notification,
    scan_due_followups,
)
from services.response import success_response

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=APIResponse[NotificationListData])
def list_notifications_endpoint(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[NotificationListData]:
    """Return in-app notifications scoped to the authenticated counsellor or administrator."""
    data = list_user_notifications(
        db=db, current_user=current_user, unread_only=unread_only, limit=limit
    )
    return success_response(
        message=f"Retrieved {len(data.items)} notification(s) ({data.unread_count} unread).",
        data=data,
    )


@router.patch("/{notification_id}/read", response_model=APIResponse[NotificationOut])
def mark_notification_read_endpoint(
    notification_id: int,
    current_user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[NotificationOut]:
    """Mark an authorized notification as read."""
    data = mark_notification_read(db=db, notification_id=notification_id, current_user=current_user)
    return success_response(
        message=f"Notification #{data.id} marked as read.",
        data=data,
    )


@router.post("/scan-followups", response_model=APIResponse[NotificationScanData])
def scan_followups_endpoint(
    _user: User = Depends(require_roles("administrator", "counsellor")),
    db: Session = Depends(get_db),
) -> APIResponse[NotificationScanData]:
    """Scan active interventions for approaching and overdue follow-ups and enqueue alerts."""
    data = scan_due_followups(db=db)
    return success_response(
        message=(
            f"Follow-up scan completed: {data.created_count} notification(s) generated "
            f"({data.approaching_count} approaching, {data.overdue_count} overdue)."
        ),
        data=data,
    )


@router.post("/{notification_id}/retry", response_model=APIResponse[NotificationOut])
def retry_notification_endpoint(
    notification_id: int,
    _admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[NotificationOut]:
    """Retry email delivery for a failed notification (administrator only)."""
    data = retry_failed_notification(db=db, notification_id=notification_id)
    return success_response(
        message=f"Notification #{data.id} retry completed (email_status={data.email_status}).",
        data=data,
    )

