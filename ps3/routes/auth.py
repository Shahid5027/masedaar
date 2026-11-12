"""Authentication endpoints for login, logout, session renewal, and current-user identity."""

from typing import Tuple

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models.db_models import User, UserSession
from models.schemas import APIResponse, LoginData, LoginRequest, SessionMeData, UserOut
from services.auth_service import (
    authenticate_user_login,
    get_current_session_context,
    logout_user_session,
    refresh_user_session,
)
from services.response import success_response

router = APIRouter(prefix="/auth", tags=["Authentication & Sessions"])


@router.post("/login", response_model=APIResponse[LoginData])
def login_endpoint(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> APIResponse[LoginData]:
    """Authenticate user credentials, issue HttpOnly session cookie, and return CSRF token."""
    settings = get_settings()
    user, session = authenticate_user_login(
        db=db,
        request=request,
        response=response,
        username_or_email=payload.username_or_email,
        password=payload.password,
    )
    return success_response(
        message=f"Signed in as '{user.username}' ({user.role}).",
        data=LoginData(
            user=UserOut.model_validate(user),
            csrf_token=session.csrf_token,
            expires_at=session.expires_at,
            session_ttl_minutes=settings.session_ttl_minutes,
        ),
    )


@router.post("/logout", response_model=APIResponse[dict])
def logout_endpoint(
    request: Request,
    response: Response,
    context: Tuple[User, UserSession] = Depends(get_current_session_context),
    db: Session = Depends(get_db),
) -> APIResponse[dict]:
    """Revoke active server-side session and clear session cookies."""
    user, session = context
    logout_user_session(db=db, request=request, response=response, user=user, session=session)
    return success_response(
        message="Signed out successfully.",
        data={"logged_out": True},
    )


@router.post("/refresh", response_model=APIResponse[SessionMeData])
def refresh_session_endpoint(
    response: Response,
    context: Tuple[User, UserSession] = Depends(get_current_session_context),
    db: Session = Depends(get_db),
) -> APIResponse[SessionMeData]:
    """Rotate and extend the authenticated session within its maximum lifetime."""
    user, session = context
    updated = refresh_user_session(db=db, response=response, user=user, session=session)
    return success_response(
        message="Session refreshed successfully.",
        data=SessionMeData(
            user=UserOut.model_validate(user),
            csrf_token=updated.csrf_token,
            expires_at=updated.expires_at,
        ),
    )


@router.get("/me", response_model=APIResponse[SessionMeData])
def session_me_endpoint(
    context: Tuple[User, UserSession] = Depends(get_current_session_context),
) -> APIResponse[SessionMeData]:
    """Return authenticated user profile and active CSRF token."""
    user, session = context
    return success_response(
        message="Active session verified.",
        data=SessionMeData(
            user=UserOut.model_validate(user),
            csrf_token=session.csrf_token,
            expires_at=session.expires_at,
        ),
    )

