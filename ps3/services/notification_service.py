"""Automated in-app & configurable email notification service for PS3 interventions."""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import get_settings
from models.db_models import Intervention, Notification, SecurityAuditLog, User
from models.schemas import (
    ErrorDetail,
    NotificationListData,
    NotificationOut,
    NotificationScanData,
)
from services.response import PS3APIError

logger = logging.getLogger("educore.ps3.notifications")

EMAIL_VERIFICATION_NOTICE = (
    "Email transport is disabled or running under a controlled test transport. "
    "External SMTP delivery is unverified until tested against live institutional SMTP credentials."
)

_TEST_OUTBOX: List[Dict[str, str]] = []
_OUTBOX_LOCK = Lock()
_SIMULATE_NEXT_SMTP_FAILURE = False


def reset_test_outbox(simulate_failure: bool = False) -> None:
    """Clear controlled in-memory email transport buffer (used in isolated tests)."""
    global _SIMULATE_NEXT_SMTP_FAILURE
    with _OUTBOX_LOCK:
        _TEST_OUTBOX.clear()
        _SIMULATE_NEXT_SMTP_FAILURE = simulate_failure


def get_test_outbox() -> List[Dict[str, str]]:
    """Return captured payloads recorded by the memory_test email transport."""
    with _OUTBOX_LOCK:
        return list(_TEST_OUTBOX)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _resolve_recipient_user(db: Session, assigned_to: Optional[str]) -> Optional[User]:
    """Match an intervention assignee string to an active User account by username, email, or name."""
    if not assigned_to or not assigned_to.strip():
        return None
    target = assigned_to.strip().lower()
    return db.scalar(
        select(User).where(
            User.is_active.is_(True),
            or_(
                func.lower(User.username) == target,
                func.lower(User.email) == target,
                func.lower(User.full_name) == target,
            ),
        )
    )


def _send_email_via_configured_transport(
    recipient_email: str,
    subject: str,
    body: str,
) -> Tuple[str, Optional[str]]:
    """Attempt outbound email delivery via configured SMTP or controlled test transport."""
    global _SIMULATE_NEXT_SMTP_FAILURE
    settings = get_settings()
    mode = (settings.notification_email_transport or "disabled").strip().lower()

    if mode == "memory_test":
        with _OUTBOX_LOCK:
            if _SIMULATE_NEXT_SMTP_FAILURE:
                _SIMULATE_NEXT_SMTP_FAILURE = False
                return "failed", "Simulated temporary SMTP transport failure."
            _TEST_OUTBOX.append(
                {
                    "to": recipient_email,
                    "subject": subject,
                    "body": body,
                }
            )
        return "test_captured", None

    if mode == "smtp":
        if not settings.smtp_host.strip():
            return "failed", "SMTP transport enabled but SMTP_HOST is empty."
        msg = EmailMessage()
        msg["From"] = settings.smtp_from_email
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
                if settings.smtp_use_tls:
                    client.starttls()
                if settings.smtp_username.strip():
                    client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(msg)
            return "sent", None
        except Exception as exc:
            return "failed", f"SMTP delivery error: {type(exc).__name__}"

    return "skipped_no_smtp", None


def _attempt_email_delivery(db: Session, notif: Notification) -> None:
    """Execute one email delivery attempt for a persisted notification without throwing."""
    if not notif.recipient_email:
        notif.email_status = "skipped_no_smtp"
        return

    settings = get_settings()
    if notif.email_attempts >= settings.notification_max_retries:
        return

    notif.email_attempts += 1
    status_val, err_msg = _send_email_via_configured_transport(
        recipient_email=notif.recipient_email,
        subject=notif.title,
        body=notif.message,
    )
    notif.email_status = status_val
    notif.last_error = err_msg
    if status_val in {"sent", "test_captured"}:
        notif.sent_at = _utc_now()
    elif status_val == "failed":
        logger.warning(
            "Notification #%s (%s) delivery failed (attempt %s): %s",
            notif.id,
            notif.event_type,
            notif.email_attempts,
            err_msg,
        )
        db.add(
            SecurityAuditLog(
                actor_username="notification_worker",
                actor_role="system",
                event_type="NOTIFICATION_FAILED",
                target_type="notification",
                target_id=str(notif.id),
                summary=f"Email delivery failed for notification #{notif.id} ({notif.event_type}).",
                details={"email_status": status_val, "attempts": notif.email_attempts},
                created_at=_utc_now(),
            )
        )


def dispatch_intervention_notification(
    db: Session,
    *,
    intervention: Intervention,
    event_type: str,
    dedupe_key: str,
    title: str,
    message: str,
    recipient_user: Optional[User] = None,
) -> Optional[Notification]:
    """Persist a deduplicated notification and run isolated email delivery without failing caller."""
    try:
        existing = db.scalar(select(Notification).where(Notification.dedupe_key == dedupe_key))
        if existing is not None:
            return None

        resolved_user = recipient_user or _resolve_recipient_user(db, intervention.assigned_to)
        notif = Notification(
            recipient_user_id=resolved_user.id if resolved_user is not None else None,
            recipient_username=(
                resolved_user.username
                if resolved_user is not None
                else (intervention.assigned_to or None)
            ),
            recipient_email=resolved_user.email if resolved_user is not None else None,
            intervention_id=intervention.id,
            student_id=intervention.student_id,
            event_type=event_type,
            channel="in_app_and_email",
            title=title[:255],
            message=message,
            dedupe_key=dedupe_key[:191],
            email_status="pending",
            email_attempts=0,
            is_read=False,
            created_at=_utc_now(),
        )
        db.add(notif)
        db.flush()
        _attempt_email_delivery(db, notif)
        db.commit()
        db.refresh(notif)
        return notif
    except IntegrityError:
        db.rollback()
        return None
    except Exception as exc:
        db.rollback()
        logger.error("Isolated notification error on intervention #%s: %s", intervention.id, exc)
        return None


def notify_intervention_lifecycle_change(
    db: Session,
    *,
    intervention: Intervention,
    previous_status: str,
    new_status: str,
    previous_assigned_to: Optional[str],
    new_assigned_to: Optional[str],
) -> None:
    """Trigger privacy-safe notifications after an intervention update commits."""
    assigned_triggered = bool(new_assigned_to and new_assigned_to != previous_assigned_to)
    if assigned_triggered and new_assigned_to is not None:
        dispatch_intervention_notification(
            db,
            intervention=intervention,
            event_type="INTERVENTION_ASSIGNED",
            dedupe_key=f"assigned:{intervention.id}:v{intervention.version}:{new_assigned_to}",
            title=f"EDUCORE PS3: Intervention #{intervention.id} assigned",
            message=(
                f"Intervention #{intervention.id} (status: {new_status}) has been assigned to "
                f"'{new_assigned_to}'. Open the secure portal to review details."
            ),
        )

    if new_status != previous_status and not (assigned_triggered and new_status == "ASSIGNED"):
        if new_status == "COMPLETED":
            dispatch_intervention_notification(
                db,
                intervention=intervention,
                event_type="INTERVENTION_COMPLETED",
                dedupe_key=f"completed:{intervention.id}:v{intervention.version}",
                title=f"EDUCORE PS3: Intervention #{intervention.id} completed",
                message=(
                    f"Intervention #{intervention.id} moved from {previous_status} to COMPLETED. "
                    "Review history in the EDUCORE PS3 portal."
                ),
            )
        else:
            dispatch_intervention_notification(
                db,
                intervention=intervention,
                event_type="INTERVENTION_STATUS_CHANGED",
                dedupe_key=f"status:{intervention.id}:v{intervention.version}:{new_status}",
                title=f"EDUCORE PS3: Intervention #{intervention.id} updated ({new_status})",
                message=(
                    f"Intervention #{intervention.id} status changed from {previous_status} "
                    f"to {new_status}. Sign in to the EDUCORE PS3 portal for details."
                ),
            )


def scan_due_followups(db: Session) -> NotificationScanData:
    """Generate deduplicated approaching and overdue follow-up notifications."""
    settings = get_settings()
    now = _utc_now()
    horizon = now + timedelta(hours=settings.follow_up_approaching_hours)

    rows = db.scalars(
        select(Intervention).where(
            Intervention.is_archived.is_(False),
            Intervention.follow_up_date.is_not(None),
            Intervention.status.notin_(["COMPLETED", "CANCELLED"]),
        )
    ).all()

    created_count = 0
    approaching_count = 0
    overdue_count = 0

    for intr in rows:
        if intr.follow_up_date is None:
            continue
        due_utc = _as_utc(intr.follow_up_date)
        due_bucket = due_utc.strftime("%Y-%m-%d")

        if due_utc < now:
            notif = dispatch_intervention_notification(
                db,
                intervention=intr,
                event_type="FOLLOW_UP_OVERDUE",
                dedupe_key=f"overdue:{intr.id}:{due_bucket}",
                title=f"EDUCORE PS3 Alert: Intervention #{intr.id} follow-up overdue",
                message=(
                    f"Scheduled follow-up for intervention #{intr.id} is overdue "
                    f"(due {due_utc.strftime('%Y-%m-%d %H:%M UTC')}). Review in portal."
                ),
            )
            if notif is not None:
                created_count += 1
                overdue_count += 1
        elif due_utc <= horizon:
            notif = dispatch_intervention_notification(
                db,
                intervention=intr,
                event_type="FOLLOW_UP_APPROACHING",
                dedupe_key=f"approaching:{intr.id}:{due_bucket}",
                title=f"EDUCORE PS3 Reminder: Intervention #{intr.id} follow-up approaching",
                message=(
                    f"Scheduled follow-up for intervention #{intr.id} is upcoming "
                    f"({due_utc.strftime('%Y-%m-%d %H:%M UTC')}). Review in portal."
                ),
            )
            if notif is not None:
                created_count += 1
                approaching_count += 1

    return NotificationScanData(
        created_count=created_count,
        approaching_count=approaching_count,
        overdue_count=overdue_count,
        email_transport=settings.notification_email_transport,
    )


def list_user_notifications(
    db: Session,
    current_user: User,
    unread_only: bool = False,
    limit: int = 50,
) -> NotificationListData:
    """List in-app notifications scoped strictly to the current user (admins see all/system too)."""
    settings = get_settings()
    base = select(Notification)
    if current_user.role != "administrator":
        base = base.where(
            or_(
                Notification.recipient_user_id == current_user.id,
                func.lower(Notification.recipient_username) == current_user.username.lower(),
                func.lower(Notification.recipient_username) == current_user.full_name.lower(),
            )
        )

    if unread_only:
        filtered = base.where(Notification.is_read.is_(False))
    else:
        filtered = base

    items_rows = db.scalars(
        filtered.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
    ).all()
    total = db.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    unread_count = (
        db.scalar(
            select(func.count()).select_from(base.where(Notification.is_read.is_(False)).subquery())
        )
        or 0
    )

    mode = (settings.notification_email_transport or "disabled").strip().lower()
    notice = (
        "Live SMTP transport configured via environment variables."
        if mode == "smtp" and settings.smtp_host.strip()
        else EMAIL_VERIFICATION_NOTICE
    )
    return NotificationListData(
        items=[NotificationOut.model_validate(row) for row in items_rows],
        total=int(total),
        unread_count=int(unread_count),
        email_transport=mode,
        email_verification_notice=notice,
    )


def mark_notification_read(db: Session, notification_id: int, current_user: User) -> NotificationOut:
    """Mark a notification as read if authorized."""
    notif = db.get(Notification, notification_id)
    if notif is None:
        raise PS3APIError(
            status_code=404,
            message=f"Notification #{notification_id} not found.",
            errors=[ErrorDetail(code="NOTIFICATION_NOT_FOUND", message="Invalid notification id.")],
        )

    is_recipient = (
        notif.recipient_user_id == current_user.id
        or (
            notif.recipient_username is not None
            and notif.recipient_username.lower()
            in {current_user.username.lower(), current_user.full_name.lower()}
        )
    )
    if current_user.role != "administrator" and not is_recipient:
        raise PS3APIError(
            status_code=403,
            message="You cannot modify notifications belonging to another user.",
            errors=[ErrorDetail(code="INSUFFICIENT_PERMISSIONS", message="Unauthorized notification.")],
        )

    if not notif.is_read:
        notif.is_read = True
        notif.read_at = _utc_now()
        db.commit()
        db.refresh(notif)
    return NotificationOut.model_validate(notif)


def retry_failed_notification(db: Session, notification_id: int) -> NotificationOut:
    """Retry a failed email delivery while respecting configured retry limits."""
    notif = db.get(Notification, notification_id)
    if notif is None:
        raise PS3APIError(
            status_code=404,
            message=f"Notification #{notification_id} not found.",
            errors=[ErrorDetail(code="NOTIFICATION_NOT_FOUND", message="Invalid notification id.")],
        )
    settings = get_settings()
    if notif.email_attempts >= settings.notification_max_retries:
        raise PS3APIError(
            status_code=422,
            message="Maximum email retry attempts reached for this notification.",
            errors=[
                ErrorDetail(
                    code="MAX_RETRIES_EXCEEDED",
                    message=f"Configured max retries ({settings.notification_max_retries}) exhausted.",
                )
            ],
        )
    _attempt_email_delivery(db, notif)
    db.commit()
    db.refresh(notif)
    return NotificationOut.model_validate(notif)

