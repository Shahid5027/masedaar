"""Helpers to construct consistent JSON API responses and raise domain HTTP errors."""

from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi.responses import JSONResponse

from config import get_settings
from models.schemas import APIResponse, ErrorDetail, ResponseMeta
from services.constants import SYNTHETIC_NOTICE_MESSAGE


class PS3APIError(Exception):
    """Structured domain error rendered through the consistent JSON error envelope."""

    def __init__(
        self,
        status_code: int,
        message: str,
        errors: Optional[List[ErrorDetail]] = None,
        contains_synthetic_data: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.errors = errors or []
        self.contains_synthetic_data = contains_synthetic_data


def build_meta(contains_synthetic_data: bool = False) -> ResponseMeta:
    """Create standard response metadata."""
    settings = get_settings()
    return ResponseMeta(
        module="ps3",
        api_version=settings.app_version,
        timestamp=datetime.now(timezone.utc),
        contains_synthetic_data=contains_synthetic_data,
        synthetic_notice=SYNTHETIC_NOTICE_MESSAGE if contains_synthetic_data else None,
    )


def success_response(
    message: str,
    data: Any = None,
    contains_synthetic_data: bool = False,
    errors: Optional[List[ErrorDetail]] = None,
) -> APIResponse[Any]:
    """Build a consistent success response envelope."""
    return APIResponse(
        status="success",
        message=message,
        data=data,
        errors=errors or [],
        meta=build_meta(contains_synthetic_data=contains_synthetic_data),
    )


def error_json_response(
    status_code: int,
    message: str,
    errors: Optional[List[ErrorDetail]] = None,
    contains_synthetic_data: bool = False,
) -> JSONResponse:
    """Build a JSONResponse matching APIResponse for any error condition."""
    payload = APIResponse(
        status="error",
        message=message,
        data=None,
        errors=errors or [],
        meta=build_meta(contains_synthetic_data=contains_synthetic_data),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))

