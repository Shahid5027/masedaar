"""Health and operational status endpoint for EDUCORE AI PS3."""

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import get_settings
from database import check_db_connection, get_db
from models.db_models import TrainedModel
from models.schemas import APIResponse, HealthData
from services.data_service import has_any_synthetic_students
from services.response import success_response

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=APIResponse[HealthData])
def health_check(db: Session = Depends(get_db)) -> APIResponse[HealthData]:
    """Verify FastAPI service, DB connectivity, and trained ML artifact presence without leaking PII."""
    settings = get_settings()
    db_ok = check_db_connection(db)
    contains_synthetic = has_any_synthetic_students(db)
    bind = db.get_bind()
    active_model = db.scalar(
        select(TrainedModel)
        .where(TrainedModel.is_active.is_(True))
        .order_by(TrainedModel.trained_at.desc(), TrainedModel.id.desc())
        .limit(1)
    )
    artifact_ok = bool(active_model and Path(active_model.artifact_path).exists())
    payload = HealthData(
        service=settings.app_name,
        environment=settings.app_env,
        database_connected=db_ok,
        database_dialect=bind.dialect.name if bind is not None else "unknown",
        model_artifact_available=artifact_ok,
    )
    return success_response(
        message="PS3 backend service is healthy.",
        data=payload,
        contains_synthetic_data=contains_synthetic,
    )
