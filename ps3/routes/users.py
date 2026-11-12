"""Administrator-only user account management and role assignment endpoints."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import User
from models.schemas import (
    APIResponse,
    UserCreateRequest,
    UserListData,
    UserOut,
    UserUpdateRequest,
)
from services.auth_service import (
    create_user_account,
    list_users,
    require_roles,
    update_user_account,
)
from services.response import success_response

router = APIRouter(prefix="/users", tags=["User Management (Admin)"])


@router.get("", response_model=APIResponse[UserListData])
def list_users_endpoint(
    _admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[UserListData]:
    """List all user accounts without password hashes (administrator only)."""
    data = list_users(db)
    return success_response(
        message=f"Retrieved {data.total} user account(s).",
        data=data,
    )


@router.post("", response_model=APIResponse[UserOut], status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    payload: UserCreateRequest,
    request: Request,
    admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[UserOut]:
    """Create a new platform account with enforced role & password policy (administrator only)."""
    ip = request.client.host if request.client else None
    created = create_user_account(db=db, request=payload, actor=admin, ip_address=ip)
    return success_response(
        message=f"User '{created.username}' ({created.role}) created successfully.",
        data=created,
    )


@router.patch("/{user_id}", response_model=APIResponse[UserOut])
def update_user_endpoint(
    user_id: int,
    payload: UserUpdateRequest,
    request: Request,
    admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[UserOut]:
    """Update user role, activation status, display name, or password (administrator only)."""
    ip = request.client.host if request.client else None
    updated = update_user_account(
        db=db,
        user_id=user_id,
        request=payload,
        actor=admin,
        ip_address=ip,
    )
    return success_response(
        message=f"User '{updated.username}' updated successfully.",
        data=updated,
    )

