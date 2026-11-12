from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .models.schemas import HealthResponse
from .routes import (
    assessments_router,
    submissions_router,
    evaluations_router,
    moderation_router,
)

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json"
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global Exception Handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error occurred in PS2 service",
            "error": str(exc) if settings.DEBUG else "Internal server error"
        }
    )


# ---------------------------------------------------------------------------
# Health-Check Endpoint (GET /api/ps2/health)
# ---------------------------------------------------------------------------
@app.get(
    f"{settings.API_PREFIX}/health",
    response_model=HealthResponse,
    tags=["System"]
)
async def health_check():
    """
    Health check endpoint confirming EDUCORE AI PS2 backend status.
    """
    return HealthResponse(
        status="healthy",
        service="EDUCORE AI - PS2 Subjective Grading Assistant",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc)
    )


# Root redirect / fallback
@app.get("/", tags=["System"])
async def root():
    return {
        "service": "EDUCORE AI - PS2 Automated Formative Assessment & Subjective Grading Assistant",
        "health": f"{settings.API_PREFIX}/health",
        "documentation": f"{settings.API_PREFIX}/docs"
    }


# ---------------------------------------------------------------------------
# Modular Route Registration with Prefix /api/ps2
# ---------------------------------------------------------------------------
app.include_router(assessments_router, prefix=settings.API_PREFIX)
app.include_router(submissions_router, prefix=settings.API_PREFIX)
app.include_router(evaluations_router, prefix=settings.API_PREFIX)
app.include_router(moderation_router, prefix=settings.API_PREFIX)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
