"""CSV validation, ingestion, summary, and synthetic demo seeding endpoints."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models.db_models import User
from models.schemas import (
    APIResponse,
    DataSummaryData,
    ErrorDetail,
    UploadData,
    ValidationSummaryData,
)
from services.auth_service import require_roles
from services.csv_validator import validate_csv_bytes
from services.data_service import (
    get_data_summary,
    has_any_synthetic_students,
    ingest_validated_csv,
)
from services.response import PS3APIError, success_response
from services.synthetic_data import MIN_SYNTHETIC_RECORDS, seed_synthetic_demo_data

logger = logging.getLogger("educore.ps3.data")
router = APIRouter(prefix="/data", tags=["Data Ingestion & Validation"])


def _validate_csv_filename(filename: Optional[str]) -> str:
    """Sanitize uploaded filename and verify .csv extension."""
    clean_name = Path((filename or "upload.csv").strip() or "upload.csv").name
    suffix = Path(clean_name).suffix.lower()
    if suffix and suffix != ".csv":
        logger.warning("Rejected non-CSV upload filename extension '%s'.", suffix)
        raise PS3APIError(
            status_code=400,
            message=f"Unsupported file type '{suffix}'. Please upload a UTF-8 CSV (.csv) file.",
            errors=[
                ErrorDetail(
                    code="INVALID_FILE_TYPE",
                    message=f"Expected a .csv file, got '{clean_name}'.",
                )
            ],
        )
    return clean_name


async def _read_upload_bytes(file: UploadFile) -> tuple[str, bytes]:
    """Read uploaded file bytes with filename validation and size guard."""
    filename = _validate_csv_filename(file.filename)
    settings = get_settings()
    raw_bytes = await file.read(settings.max_upload_bytes + 1)
    if len(raw_bytes) > settings.max_upload_bytes:
        raise PS3APIError(
            status_code=413,
            message=f"Uploaded file exceeds maximum allowed size of {settings.max_upload_mb} MB.",
            errors=[
                ErrorDetail(
                    code="FILE_TOO_LARGE",
                    message=f"File '{filename}' exceeds {settings.max_upload_mb} MB limit.",
                )
            ],
        )
    return filename, raw_bytes


@router.post("/validate", response_model=APIResponse[ValidationSummaryData])
async def validate_csv_endpoint(
    file: UploadFile = File(..., description="CSV file containing student academic and LMS features."),
    is_synthetic: bool = Query(
        default=False,
        description="Optional flag indicating whether this CSV contains synthetic demo records.",
    ),
    _admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[ValidationSummaryData]:
    """Perform dry-run schema, uniqueness, and domain validation on an uploaded CSV file."""
    filename, raw_bytes = await _read_upload_bytes(file)
    result = validate_csv_bytes(
        raw_bytes=raw_bytes,
        filename=filename,
        assume_synthetic=is_synthetic,
    )
    summary = result.summary
    msg = (
        f"CSV validation passed for {summary.valid_rows} student row(s)."
        if summary.is_valid
        else f"CSV validation failed with {summary.error_count} error(s) across {summary.invalid_rows} row(s)."
    )
    db_has_synthetic = has_any_synthetic_students(db)
    return success_response(
        message=msg,
        data=summary,
        contains_synthetic_data=summary.is_synthetic_detected or db_has_synthetic,
        errors=summary.errors,
    )


@router.post(
    "/upload",
    response_model=APIResponse[UploadData],
    status_code=status.HTTP_201_CREATED,
)
async def upload_csv_endpoint(
    file: UploadFile = File(..., description="Validated CSV file to ingest into the database."),
    is_synthetic: bool = Query(
        default=False,
        description="Set to true when uploading synthetic demo data so all records are labeled.",
    ),
    admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[UploadData]:
    """Validate and atomically ingest student activity snapshots (administrator only)."""
    filename, raw_bytes = await _read_upload_bytes(file)
    validation = validate_csv_bytes(
        raw_bytes=raw_bytes,
        filename=filename,
        assume_synthetic=is_synthetic,
    )
    try:
        upload_result = ingest_validated_csv(
            db=db,
            validation=validation,
            filename=filename,
            force_synthetic=is_synthetic,
        )
    except PS3APIError as exc:
        logger.warning(
            "CSV upload failed for administrator='%s' file='%s': %s",
            admin.username,
            filename,
            exc.errors[0].code if exc.errors else "UPLOAD_FAILED",
        )
        raise
    label_note = " (with training-only dropout_label stored separately)" if upload_result.has_training_target else ""
    synthetic_tag = " [SYNTHETIC DEMO DATA]" if upload_result.is_synthetic else ""
    return success_response(
        message=f"Successfully ingested {upload_result.ingested_rows} student record(s){label_note}{synthetic_tag}.",
        data=upload_result,
        contains_synthetic_data=upload_result.is_synthetic or has_any_synthetic_students(db),
    )


@router.get("/summary", response_model=APIResponse[DataSummaryData])
def data_summary_endpoint(
    _user: User = Depends(require_roles("administrator", "counsellor", "viewer")),
    db: Session = Depends(get_db),
) -> APIResponse[DataSummaryData]:
    """Return real database counts, Pandas/NumPy feature statistics, and synthetic data status."""
    summary = get_data_summary(db)
    return success_response(
        message="Database summary computed successfully.",
        data=summary,
        contains_synthetic_data=summary.contains_synthetic_data,
    )


@router.post(
    "/seed-synthetic",
    response_model=APIResponse[UploadData],
    status_code=status.HTTP_201_CREATED,
)
def seed_synthetic_endpoint(
    num_records: int = Query(
        default=250,
        ge=MIN_SYNTHETIC_RECORDS,
        le=5000,
        description="Number of clearly-labeled synthetic demo records to generate and ingest (>=200).",
    ),
    seed: int = Query(default=42, description="Deterministic random seed."),
    _admin: User = Depends(require_roles("administrator")),
    db: Session = Depends(get_db),
) -> APIResponse[UploadData]:
    """Explicitly generate and ingest clearly labeled synthetic demo student records (>=200)."""
    upload_result = seed_synthetic_demo_data(db=db, num_records=num_records, seed=seed)
    return success_response(
        message=(
            f"Generated and seeded {upload_result.ingested_rows} clearly labeled synthetic demo "
            "student records (is_synthetic=true)."
        ),
        data=upload_result,
        contains_synthetic_data=True,
    )

