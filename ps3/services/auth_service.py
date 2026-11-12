"""Authentication, secure cookie sessions, CSRF protection, rate limiting, and RBAC dependencies."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Callable, Deque, Dict, Optional, Tuple

from fastapi import Depends, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models.db_models import SecurityAuditLog, User, UserSession
from models.schemas import (
    ErrorDetail,
    UserCreateRequest,
    UserListData,
    UserOut,
    UserRole,
    UserUpdateRequest,
)
from services.response import PS3APIError

logger = logging.getLogger("educore.ps3.security")

_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32

_SAFE_HTTP_METHODS = {"GET", "HEAD", "OPTIONS"}
_IP_FAILURE_BUCKETS: Dict[str, Deque[float]] = defaultdict(deque)
_IP_LOCK = Lock()


def _utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """Normalize naive datetimes loaded from SQLite to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hash_password(password: str) -> str:
    """Hash a plaintext password using OpenSSL scrypt with a fresh 16-byte salt."""
    salt = os.urandom(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(derived).decode("ascii")
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt_b64}${hash_b64}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Constant-time verification of password against stored scrypt hash."""
    try:
        algo, n_str, r_str, p_str, salt_b64, hash_b64 = stored_hash.split("$")
        if algo != "scrypt":
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
        candidate = hashlib.scrypt(
            plain_password.encode("utf-8"),
            salt=salt,
            n=int(n_str),
            r=int(r_str),
            p=int(p_str),
            dklen=len(expected),
        )
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def validate_password_strength(password: str, min_length: Optional[int] = None) -> None:
    """Enforce institutional password complexity policy."""
    settings = get_settings()
    required_len = min_length or settings.password_min_length
    issues: list[str] = []
    if len(password) < required_len:
        issues.append(f"at least {required_len} characters")
    if not re.search(r"[A-Z]", password):
        issues.append("one uppercase letter")
    if not re.search(r"[a-z]", password):
        issues.append("one lowercase letter")
    if not re.search(r"\d", password):
        issues.append("one number")
    if not re.search(r"[^A-Za-z0-9]", password):
        issues.append("one special character")

    if issues:
        raise PS3APIError(
            status_code=422,
            message="Password does not meet complexity requirements.",
            errors=[
                ErrorDetail(
                    code="WEAK_PASSWORD",
                    column="password",
                    message=f"Password must include {', '.join(issues)}.",
                )
            ],
        )


def _hash_token(raw_token: str) -> str:
    """Hash opaque session token with SHA-256 before database lookup or storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _client_ip(request: Request) -> str:
    """Extract client IP cautiously for audit logs and rate limiting."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client and request.client.host:
        return request.client.host[:64]
    return "unknown"


def clear_rate_limit_cache() -> None:
    """Reset in-memory IP failure buckets (used in isolated tests)."""
    with _IP_LOCK:
        _IP_FAILURE_BUCKETS.clear()


def _check_ip_rate_limit(ip_address: str) -> None:
    """Reject abusive bursts of failed logins from the same IP."""
    settings = get_settings()
    now_ts = _utc_now().timestamp()
    window_sec = settings.login_rate_limit_window_minutes * 60
    with _IP_LOCK:
        bucket = _IP_FAILURE_BUCKETS[ip_address]
        while bucket and (now_ts - bucket[0]) > window_sec:
            bucket.popleft()
        if len(bucket) >= settings.login_rate_limit_attempts * 2:
            raise PS3APIError(
                status_code=429,
                message="Too many failed login attempts. Please try again later.",
                errors=[
                    ErrorDetail(
                        code="RATE_LIMITED",
                        message="Login rate limit exceeded for this source address.",
                    )
                ],
            )


def _record_ip_failure(ip_address: str) -> None:
    now_ts = _utc_now().timestamp()
    with _IP_LOCK:
        _IP_FAILURE_BUCKETS[ip_address].append(now_ts)


def record_security_event(
    db: Session,
    event_type: str,
    summary: str,
    *,
    actor: Optional[User] = None,
    actor_username_override: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Persist a non-sensitive security or admin audit event."""
    entry = SecurityAuditLog(
        actor_user_id=actor.id if actor is not None else None,
        actor_username=actor.username if actor is not None else actor_username_override,
        actor_role=actor.role if actor is not None else None,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        details=details,
        ip_address=ip_address,
        created_at=_utc_now(),
    )
    db.add(entry)


def _set_auth_cookies(response: Response, raw_session_token: str, csrf_token: str) -> None:
    """Attach HttpOnly session cookie and companion CSRF cookie."""
    settings = get_settings()
    max_age = settings.session_ttl_minutes * 60
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_session_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        path="/",
        max_age=max_age,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        path="/",
        max_age=max_age,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Expire session and CSRF cookies cleanly on logout or session invalidation."""
    settings = get_settings()
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    response.delete_cookie(key=settings.csrf_cookie_name, path="/")


def authenticate_user_login(
    db: Session,
    request: Request,
    response: Response,
    username_or_email: str,
    password: str,
) -> Tuple[User, UserSession]:
    """Verify credentials, enforce lockout/rate limit, create session, and set cookies."""
    settings = get_settings()
    ip_address = _client_ip(request)
    _check_ip_rate_limit(ip_address)

    identifier = username_or_email.strip().lower()
    user = db.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == identifier,
                func.lower(User.email) == identifier,
            )
        )
    )

    now = _utc_now()
    if user is not None and user.locked_until is not None and _as_utc(user.locked_until) > now:
        logger.warning("Blocked login attempt for temporarily locked account from ip=%s.", ip_address)
        record_security_event(
            db,
            "LOGIN_RATE_LIMITED",
            "Blocked login attempt while account lockout window was active.",
            actor=user,
            target_type="user",
            target_id=str(user.id),
            ip_address=ip_address,
        )
        db.commit()
        raise PS3APIError(
            status_code=429,
            message="Too many failed login attempts. Please try again later.",
            errors=[
                ErrorDetail(
                    code="RATE_LIMITED",
                    message="Account temporarily locked due to repeated failed attempts.",
                )
            ],
        )

    # Run password verification even if user is missing to reduce timing discrepancies
    dummy_hash = "scrypt$16384$8$1$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    password_ok = verify_password(password, user.password_hash if user is not None else dummy_hash)

    if user is None or not user.is_active or not password_ok:
        _record_ip_failure(ip_address)
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.login_rate_limit_attempts:
                user.locked_until = now + timedelta(
                    minutes=settings.login_rate_limit_window_minutes
                )
            record_security_event(
                db,
                "LOGIN_FAILED",
                "Failed authentication attempt.",
                actor=user,
                target_type="user",
                target_id=str(user.id),
                details={"reason": "inactive_account" if not user.is_active else "invalid_password"},
                ip_address=ip_address,
            )
        else:
            record_security_event(
                db,
                "LOGIN_FAILED",
                "Failed authentication attempt for unrecognized identifier.",
                actor_username_override="unknown",
                details={"reason": "invalid_credentials"},
                ip_address=ip_address,
            )
        db.commit()
        logger.warning("Authentication failed from ip=%s.", ip_address)
        raise PS3APIError(
            status_code=401,
            message="Invalid credentials or inactive account.",
            errors=[
                ErrorDetail(
                    code="INVALID_CREDENTIALS",
                    message="Authentication failed. Check your username/email and password.",
                )
            ],
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now

    raw_session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(24)
    expires_at = now + timedelta(minutes=settings.session_ttl_minutes)
    absolute_expires_at = now + timedelta(hours=settings.session_max_lifetime_hours)

    session = UserSession(
        user_id=user.id,
        token_hash=_hash_token(raw_session_token),
        csrf_token=csrf_token,
        expires_at=expires_at,
        absolute_expires_at=absolute_expires_at,
        last_seen_at=now,
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
        ip_address=ip_address,
        created_at=now,
    )
    db.add(session)
    record_security_event(
        db,
        "LOGIN_SUCCESS",
        f"User '{user.username}' authenticated successfully.",
        actor=user,
        target_type="user",
        target_id=str(user.id),
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    db.refresh(session)

    _set_auth_cookies(response, raw_session_token, csrf_token)
    return user, session


def get_current_session_context(
    request: Request,
    db: Session = Depends(get_db),
) -> Tuple[User, UserSession]:
    """Authenticate current session cookie and enforce CSRF on state-changing requests."""
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise PS3APIError(
            status_code=401,
            message="Authentication is required to access this resource.",
            errors=[
                ErrorDetail(
                    code="AUTHENTICATION_REQUIRED",
                    message="Sign in to access EDUCORE AI PS3 endpoints.",
                )
            ],
        )

    token_digest = _hash_token(raw_token)
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_digest))
    now = _utc_now()

    if session is None or session.revoked_at is not None:
        raise PS3APIError(
            status_code=401,
            message="Session is invalid or has been signed out.",
            errors=[
                ErrorDetail(
                    code="INVALID_SESSION",
                    message="Please sign in again.",
                )
            ],
        )

    if _as_utc(session.expires_at) <= now or _as_utc(session.absolute_expires_at) <= now:
        session.revoked_at = now
        user_for_log = db.get(User, session.user_id)
        record_security_event(
            db,
            "SESSION_EXPIRED",
            "Session expired before request completion.",
            actor=user_for_log,
            target_type="user_session",
            target_id=str(session.id),
            ip_address=_client_ip(request),
        )
        db.commit()
        raise PS3APIError(
            status_code=401,
            message="Your session has expired. Please sign in again.",
            errors=[
                ErrorDetail(
                    code="SESSION_EXPIRED",
                    message="Authentication session expired.",
                )
            ],
        )

    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise PS3APIError(
            status_code=401,
            message="Authenticated account is inactive or unavailable.",
            errors=[
                ErrorDetail(
                    code="ACCOUNT_INACTIVE",
                    message="Contact an administrator to activate this account.",
                )
            ],
        )

    if request.method.upper() not in _SAFE_HTTP_METHODS:
        header_csrf = request.headers.get("X-CSRF-Token") or request.headers.get("x-csrf-token")
        if not header_csrf or not hmac.compare_digest(header_csrf, session.csrf_token):
            record_security_event(
                db,
                "CSRF_VALIDATION_FAILED",
                f"Blocked {request.method} request to {request.url.path} due to missing/invalid CSRF token.",
                actor=user,
                target_type="endpoint",
                target_id=request.url.path,
                ip_address=_client_ip(request),
            )
            db.commit()
            raise PS3APIError(
                status_code=403,
                message="CSRF validation failed for state-changing request.",
                errors=[
                    ErrorDetail(
                        code="CSRF_VALIDATION_FAILED",
                        message="Supply a valid X-CSRF-Token matching your active session.",
                    )
                ],
            )

    session.last_seen_at = now
    db.commit()
    return user, session


def get_current_user(
    context: Tuple[User, UserSession] = Depends(get_current_session_context),
) -> User:
    """FastAPI dependency returning the verified active User."""
    return context[0]


def require_roles(*allowed_roles: UserRole) -> Callable[..., User]:
    """FastAPI dependency enforcing backend RBAC roles and logging denied attempts."""

    def _dependency(
        request: Request,
        context: Tuple[User, UserSession] = Depends(get_current_session_context),
        db: Session = Depends(get_db),
    ) -> User:
        user = context[0]
        if user.role not in allowed_roles:
            record_security_event(
                db,
                "ACCESS_DENIED",
                f"Role '{user.role}' denied {request.method} access to {request.url.path}.",
                actor=user,
                target_type="endpoint",
                target_id=request.url.path,
                details={"required_roles": list(allowed_roles), "user_role": user.role},
                ip_address=_client_ip(request),
            )
            db.commit()
            logger.warning(
                "RBAC denied user='%s' role='%s' on %s %s",
                user.username,
                user.role,
                request.method,
                request.url.path,
            )
            raise PS3APIError(
                status_code=403,
                message="You do not have permission to perform this action.",
                errors=[
                    ErrorDetail(
                        code="INSUFFICIENT_PERMISSIONS",
                        message=f"Requires role: {', '.join(allowed_roles)}.",
                    )
                ],
            )
        return user

    return _dependency


def refresh_user_session(
    db: Session,
    response: Response,
    user: User,
    session: UserSession,
) -> UserSession:
    """Extend session expiration up to absolute lifetime and rotate CSRF token."""
    settings = get_settings()
    now = _utc_now()
    abs_exp = _as_utc(session.absolute_expires_at)
    if abs_exp <= now:
        raise PS3APIError(
            status_code=401,
            message="Maximum session lifetime reached. Please sign in again.",
            errors=[ErrorDetail(code="SESSION_EXPIRED", message="Re-authentication required.")],
        )

    new_exp = min(now + timedelta(minutes=settings.session_ttl_minutes), abs_exp)
    new_raw_token = secrets.token_urlsafe(32)
    new_csrf = secrets.token_urlsafe(24)
    session.token_hash = _hash_token(new_raw_token)
    session.csrf_token = new_csrf
    session.expires_at = new_exp
    session.last_seen_at = now
    db.commit()
    db.refresh(session)
    _set_auth_cookies(response, new_raw_token, new_csrf)
    return session


def logout_user_session(
    db: Session,
    request: Request,
    response: Response,
    user: User,
    session: UserSession,
) -> None:
    """Revoke server-side session token, log audit trail, and clear cookies."""
    session.revoked_at = _utc_now()
    record_security_event(
        db,
        "LOGOUT",
        f"User '{user.username}' signed out.",
        actor=user,
        target_type="user_session",
        target_id=str(session.id),
        ip_address=_client_ip(request),
    )
    db.commit()
    _clear_auth_cookies(response)


def list_users(db: Session) -> UserListData:
    """Return all user accounts sorted by role and username (excluding password hashes)."""
    rows = db.scalars(select(User).order_by(User.role.asc(), User.username.asc())).all()
    items = [UserOut.model_validate(u) for u in rows]
    return UserListData(items=items, total=len(items))


def create_user_account(
    db: Session,
    request: UserCreateRequest,
    *,
    actor: Optional[User] = None,
    ip_address: Optional[str] = None,
) -> UserOut:
    """Create a validated user account with strong scrypt password hashing."""
    username = request.username.strip()
    email = request.email.strip().lower()
    full_name = request.full_name.strip()
    validate_password_strength(request.password)

    existing = db.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == username.lower(),
                func.lower(User.email) == email,
            )
        )
    )
    if existing is not None:
        raise PS3APIError(
            status_code=409,
            message="Username or email already exists.",
            errors=[
                ErrorDetail(
                    code="USER_ALREADY_EXISTS",
                    message="Choose a unique username and email address.",
                )
            ],
        )

    now = _utc_now()
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        role=request.role,
        password_hash=hash_password(request.password),
        is_active=request.is_active,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    record_security_event(
        db,
        "USER_CREATED",
        f"Created account '{user.username}' with role '{user.role}'.",
        actor=actor,
        actor_username_override="system_bootstrap" if actor is None else None,
        target_type="user",
        target_id=str(user.id),
        details={"username": user.username, "role": user.role, "is_active": user.is_active},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


def update_user_account(
    db: Session,
    user_id: int,
    request: UserUpdateRequest,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> UserOut:
    """Update user profile, role, active state, or password with last-admin safeguard."""
    user = db.get(User, user_id)
    if user is None:
        raise PS3APIError(
            status_code=404,
            message=f"User #{user_id} was not found.",
            errors=[ErrorDetail(code="USER_NOT_FOUND", message=f"No user with id={user_id}.")],
        )

    fields_set = request.model_fields_set
    # Prevent removing or deactivating the last active administrator
    target_role = request.role if ("role" in fields_set and request.role is not None) else user.role
    target_active = (
        request.is_active
        if ("is_active" in fields_set and request.is_active is not None)
        else user.is_active
    )
    if user.role == "administrator" and (target_role != "administrator" or not target_active):
        other_active_admins = (
            db.scalar(
                select(func.count(User.id)).where(
                    User.id != user.id,
                    User.role == "administrator",
                    User.is_active.is_(True),
                )
            )
            or 0
        )
        if other_active_admins == 0:
            raise PS3APIError(
                status_code=422,
                message="Cannot deactivate or demote the last active administrator.",
                errors=[
                    ErrorDetail(
                        code="LAST_ADMIN_PROTECTED",
                        message="At least one active administrator account is required.",
                    )
                ],
            )

    now = _utc_now()
    changes: Dict[str, Any] = {}

    if "full_name" in fields_set and request.full_name is not None:
        clean_name = request.full_name.strip()
        if clean_name != user.full_name:
            changes["full_name"] = {"from": user.full_name, "to": clean_name}
            user.full_name = clean_name

    if "email" in fields_set and request.email is not None:
        clean_email = request.email.strip().lower()
        if clean_email != user.email:
            dup_email = db.scalar(
                select(User).where(User.id != user.id, func.lower(User.email) == clean_email)
            )
            if dup_email is not None:
                raise PS3APIError(
                    status_code=409,
                    message="Email address is already in use by another account.",
                    errors=[ErrorDetail(code="EMAIL_IN_USE", column="email", message="Duplicate email.")],
                )
            changes["email"] = {"from": user.email, "to": clean_email}
            user.email = clean_email

    if "role" in fields_set and request.role is not None and request.role != user.role:
        changes["role"] = {"from": user.role, "to": request.role}
        user.role = request.role

    if "is_active" in fields_set and request.is_active is not None and request.is_active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": request.is_active}
        user.is_active = request.is_active
        if not request.is_active:
            # Immediately revoke active sessions when an account is deactivated
            active_sessions = db.scalars(
                select(UserSession).where(
                    UserSession.user_id == user.id,
                    UserSession.revoked_at.is_(None),
                )
            ).all()
            for sess in active_sessions:
                sess.revoked_at = now

    if "new_password" in fields_set and request.new_password:
        validate_password_strength(request.new_password)
        user.password_hash = hash_password(request.new_password)
        changes["password_reset"] = True

    user.updated_at = now
    if changes:
        event_type = (
            "USER_DEACTIVATED"
            if changes.get("is_active", {}).get("to") is False
            else "USER_ACTIVATED"
            if changes.get("is_active", {}).get("to") is True
            else "USER_ROLE_CHANGED"
            if "role" in changes
            else "USER_UPDATED"
        )
        record_security_event(
            db,
            event_type,
            f"Administrator '{actor.username}' updated account '{user.username}'.",
            actor=actor,
            target_type="user",
            target_id=str(user.id),
            details=changes,
            ip_address=ip_address,
        )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


def bootstrap_admin_if_configured(db: Session) -> Optional[UserOut]:
    """Create initial administrator only when DB has 0 users AND BOOTSTRAP_ADMIN_PASSWORD is set."""
    settings = get_settings()
    user_count = db.scalar(select(func.count(User.id))) or 0
    if user_count > 0:
        return None
    if not settings.bootstrap_admin_password.strip():
        logger.warning(
            "No user accounts exist in database. Run scripts/create_admin.py or set "
            "BOOTSTRAP_ADMIN_PASSWORD before signing in."
        )
        return None

    created = create_user_account(
        db,
        UserCreateRequest(
            username=settings.bootstrap_admin_username,
            email=settings.bootstrap_admin_email,
            full_name=settings.bootstrap_admin_full_name,
            role="administrator",
            password=settings.bootstrap_admin_password,
            is_active=True,
        ),
        actor=None,
    )
    logger.info("Bootstrapped initial administrator account '%s'.", created.username)
    return created

