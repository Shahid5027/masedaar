"""FastAPI application entrypoint for EDUCORE AI - PS3."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import get_settings
from database import SessionLocal, init_db
from models.db_models import Student
from models.schemas import ErrorDetail
from routes.auth import router as auth_router
from routes.data import router as data_router
from routes.health import router as health_router
from routes.interventions import router as interventions_router
from routes.ml import router as ml_router
from routes.notifications import router as notifications_router
from routes.ops import router as ops_router
from routes.predictions import router as predictions_router
from routes.students import router as students_router
from routes.users import router as users_router
from services.auth_service import bootstrap_admin_if_configured
from services.response import PS3APIError, error_json_response
from services.synthetic_data import seed_synthetic_demo_data

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("educore.ps3")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize database schema on startup, bootstrap admin if configured, and optionally seed demo."""
    init_db()
    db = SessionLocal()
    try:
        bootstrap_admin_if_configured(db)
        if settings.auto_seed_synthetic_demo:
            existing_count = db.scalar(select(func.count(Student.student_id))) or 0
            if existing_count == 0:
                upload_info = seed_synthetic_demo_data(
                    db=db,
                    num_records=settings.synthetic_demo_record_count,
                    seed=settings.synthetic_random_seed,
                )
                logger.info(
                    "Auto-seeded %s clearly labeled synthetic demo records (batch_id=%s).",
                    upload_info.ingested_rows,
                    upload_info.batch_id,
                )
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    """Create and configure the hardened FastAPI application instance."""
    docs_on = settings.effective_docs_enabled
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "EDUCORE AI PS3: Early Dropout Prediction and Student Retention Copilot. "
            "Secured API under /api/ps3 with role-based access control and audit logging."
        ),
        docs_url="/docs" if docs_on else None,
        redoc_url="/redoc" if docs_on else None,
        openapi_url="/openapi.json" if docs_on else None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith(settings.api_prefix):
            response.headers.setdefault("Cache-Control", "no-store")
        if settings.enable_hsts:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-CSRF-Token"],
    )

    @app.exception_handler(PS3APIError)
    async def handle_ps3_api_error(_request: Request, exc: PS3APIError) -> JSONResponse:
        return error_json_response(
            status_code=exc.status_code,
            message=exc.message,
            errors=exc.errors,
            contains_synthetic_data=exc.contains_synthetic_data,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        formatted_errors = [
            ErrorDetail(
                code="REQUEST_VALIDATION_ERROR",
                column=".".join(str(part) for part in err.get("loc", [])),
                message=err.get("msg", "Invalid request parameter."),
            )
            for err in exc.errors()
        ]
        return error_json_response(
            status_code=422,
            message="Request parameter validation failed.",
            errors=formatted_errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return error_json_response(
            status_code=exc.status_code,
            message=str(exc.detail),
            errors=[ErrorDetail(code=f"HTTP_{exc.status_code}", message=str(exc.detail))],
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_sqlalchemy_error(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Database error encountered in PS3 API: %s", exc)
        return error_json_response(
            status_code=500,
            message="A database error occurred while processing your request.",
            errors=[ErrorDetail(code="DATABASE_ERROR", message="Internal database operation failed.")],
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error in PS3 API: %s", exc)
        return error_json_response(
            status_code=500,
            message="An unexpected internal server error occurred.",
            errors=[ErrorDetail(code="INTERNAL_SERVER_ERROR", message="Unexpected server error.")],
        )

    api_router = APIRouter(prefix=settings.api_prefix)
    api_router.include_router(health_router)
    api_router.include_router(auth_router)
    api_router.include_router(users_router)
    api_router.include_router(data_router)
    api_router.include_router(students_router)
    api_router.include_router(ml_router)
    api_router.include_router(predictions_router)
    api_router.include_router(interventions_router)
    api_router.include_router(notifications_router)
    api_router.include_router(ops_router)
    app.include_router(api_router)

    return app


app = create_app()

