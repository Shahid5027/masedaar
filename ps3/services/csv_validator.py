"""CSV parsing and validation engine for EDUCORE AI PS3."""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from config import get_settings
from models.schemas import ErrorDetail, ValidationSummaryData
from services.constants import (
    DATA_SOURCE_COLUMN,
    ID_COLUMN,
    MAX_ATTENDANCE_RATE,
    MAX_AVERAGE_GRADE,
    MAX_ENGAGEMENT_CHANGE_PCT,
    MIN_ATTENDANCE_RATE,
    MIN_AVERAGE_GRADE,
    MIN_ENGAGEMENT_CHANGE_PCT,
    MISSING_SENTINELS,
    REQUIRED_CSV_COLUMNS,
    SYNTHETIC_DATA_SOURCE,
    SYNTHETIC_FLAG_COLUMN,
    TRAINING_TARGET_COLUMN,
)


@dataclass(frozen=True)
class FloatFieldRule:
    """Validation bounds and error metadata for a numeric float column."""

    column: str
    min_val: float
    max_val: float
    range_error_code: str
    unit_hint: str


@dataclass(frozen=True)
class IntFieldRule:
    """Validation bounds and error metadata for a non-negative integer column."""

    column: str
    negative_error_code: str


FLOAT_FIELD_RULES: Tuple[FloatFieldRule, ...] = (
    FloatFieldRule(
        column="attendance_rate",
        min_val=MIN_ATTENDANCE_RATE,
        max_val=MAX_ATTENDANCE_RATE,
        range_error_code="INVALID_ATTENDANCE_RATE",
        unit_hint="percentage between 0 and 100",
    ),
    FloatFieldRule(
        column="average_grade",
        min_val=MIN_AVERAGE_GRADE,
        max_val=MAX_AVERAGE_GRADE,
        range_error_code="INVALID_GRADE",
        unit_hint="numeric grade between 0 and 100",
    ),
    FloatFieldRule(
        column="engagement_change_pct",
        min_val=MIN_ENGAGEMENT_CHANGE_PCT,
        max_val=MAX_ENGAGEMENT_CHANGE_PCT,
        range_error_code="INVALID_ENGAGEMENT_CHANGE",
        unit_hint="percentage change between -100 and 1000",
    ),
)

INT_FIELD_RULES: Tuple[IntFieldRule, ...] = (
    IntFieldRule(column="late_assignments", negative_error_code="NEGATIVE_ASSIGNMENT_COUNT"),
    IntFieldRule(column="missing_assignments", negative_error_code="NEGATIVE_ASSIGNMENT_COUNT"),
    IntFieldRule(column="lms_logins_30d", negative_error_code="NEGATIVE_COUNT"),
    IntFieldRule(column="previous_failure_count", negative_error_code="NEGATIVE_COUNT"),
)

BOOLEAN_TRUE = frozenset({"true", "1", "yes", "y"})
BOOLEAN_FALSE = frozenset({"false", "0", "no", "n"})


@dataclass
class CSVValidationResult:
    """Output of dry-run or pre-ingestion CSV validation."""

    summary: ValidationSummaryData
    cleaned_features: List[Dict[str, Any]] = field(default_factory=list)
    cleaned_training_targets: Dict[str, int] = field(default_factory=dict)
    row_synthetic_flags: Dict[str, bool] = field(default_factory=dict)
    row_data_sources: Dict[str, str] = field(default_factory=dict)


def _is_missing(raw_value: str) -> bool:
    """Check whether a raw string cell represents a missing value."""
    return raw_value.strip().lower() in MISSING_SENTINELS


def _parse_finite_float(raw_value: str) -> Optional[float]:
    """Parse a finite float, rejecting booleans, NaN, and Inf."""
    stripped = raw_value.strip()
    if stripped.lower() in {"true", "false", "inf", "+inf", "-inf", "infinity", "-infinity"}:
        return None
    try:
        parsed = float(stripped)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _parse_boolean(raw_value: str) -> Optional[bool]:
    """Parse strict boolean string values."""
    normalized = raw_value.strip().lower()
    if normalized in BOOLEAN_TRUE:
        return True
    if normalized in BOOLEAN_FALSE:
        return False
    return None


def _build_failed_summary(
    filename: str,
    errors: List[ErrorDetail],
    detected_columns: Optional[List[str]] = None,
    missing_columns: Optional[List[str]] = None,
    total_rows: int = 0,
    invalid_rows: int = 0,
    has_training_target: bool = False,
    is_synthetic_detected: bool = False,
) -> CSVValidationResult:
    """Construct a failed CSVValidationResult with consistent summary metadata."""
    summary = ValidationSummaryData(
        is_valid=False,
        filename=filename,
        total_rows=total_rows,
        valid_rows=max(0, total_rows - invalid_rows),
        invalid_rows=invalid_rows,
        error_count=len(errors),
        errors_truncated=False,
        required_columns=list(REQUIRED_CSV_COLUMNS),
        detected_columns=detected_columns or [],
        missing_columns=missing_columns or [],
        has_training_target=has_training_target,
        training_target_column=TRAINING_TARGET_COLUMN if has_training_target else None,
        is_synthetic_detected=is_synthetic_detected,
        synthetic_label="SYNTHETIC_DEMO_DATA" if is_synthetic_detected else None,
        errors=errors,
    )
    return CSVValidationResult(summary=summary)


def validate_csv_bytes(
    raw_bytes: bytes,
    filename: str = "upload.csv",
    assume_synthetic: bool = False,
) -> CSVValidationResult:
    """Parse and thoroughly validate CSV bytes without mutating the database."""
    settings = get_settings()

    if not raw_bytes or len(raw_bytes.strip()) == 0:
        return _build_failed_summary(
            filename=filename,
            errors=[
                ErrorDetail(
                    code="EMPTY_FILE",
                    message="Uploaded CSV file is empty. Provide a header row and at least one student record.",
                )
            ],
        )

    if len(raw_bytes) > settings.max_upload_bytes:
        return _build_failed_summary(
            filename=filename,
            errors=[
                ErrorDetail(
                    code="FILE_TOO_LARGE",
                    message=f"File exceeds maximum allowed size of {settings.max_upload_mb} MB.",
                )
            ],
        )

    try:
        text_content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _build_failed_summary(
            filename=filename,
            errors=[
                ErrorDetail(
                    code="INVALID_ENCODING",
                    message="CSV file must be UTF-8 encoded.",
                )
            ],
        )

    # Pre-validate raw header & column structure via csv.reader so duplicate headers are caught.
    try:
        reader = csv.reader(io.StringIO(text_content))
        raw_header = next(reader, None)
    except csv.Error as exc:
        return _build_failed_summary(
            filename=filename,
            errors=[
                ErrorDetail(
                    code="MALFORMED_CSV",
                    message=f"Failed to parse CSV header: {exc}",
                )
            ],
        )

    if not raw_header or all(col.strip() == "" for col in raw_header):
        return _build_failed_summary(
            filename=filename,
            errors=[
                ErrorDetail(
                    code="MISSING_HEADER",
                    message="CSV file is missing a valid header row.",
                )
            ],
        )

    cleaned_headers = [col.strip() for col in raw_header]
    seen_headers: set[str] = set()
    duplicate_headers: List[str] = []
    for col in cleaned_headers:
        if col == "":
            duplicate_headers.append("<empty>")
        elif col in seen_headers and col not in duplicate_headers:
            duplicate_headers.append(col)
        seen_headers.add(col)

    if duplicate_headers:
        return _build_failed_summary(
            filename=filename,
            detected_columns=cleaned_headers,
            errors=[
                ErrorDetail(
                    code="DUPLICATE_OR_BLANK_COLUMN",
                    message=f"CSV contains duplicate or blank header column(s): {', '.join(duplicate_headers)}.",
                )
            ],
        )

    missing_columns = [col for col in REQUIRED_CSV_COLUMNS if col not in cleaned_headers]
    has_training_target = TRAINING_TARGET_COLUMN in cleaned_headers

    if missing_columns:
        return _build_failed_summary(
            filename=filename,
            detected_columns=cleaned_headers,
            missing_columns=missing_columns,
            has_training_target=has_training_target,
            is_synthetic_detected=assume_synthetic,
            errors=[
                ErrorDetail(
                    code="MISSING_REQUIRED_COLUMNS",
                    message=(
                        f"Missing required CSV column(s): {', '.join(missing_columns)}. "
                        f"Required columns: {', '.join(REQUIRED_CSV_COLUMNS)}."
                    ),
                )
            ],
        )

    # Check row width consistency before Pandas load to give clear jagged-row errors.
    expected_col_count = len(cleaned_headers)
    structural_errors: List[ErrorDetail] = []
    try:
        for row_idx, raw_row in enumerate(reader, start=1):
            if len(raw_row) != expected_col_count:
                structural_errors.append(
                    ErrorDetail(
                        code="COLUMN_COUNT_MISMATCH",
                        row=row_idx,
                        csv_line=row_idx + 1,
                        message=(
                            f"Row {row_idx} (CSV line {row_idx + 1}) has {len(raw_row)} column(s), "
                            f"expected {expected_col_count}."
                        ),
                    )
                )
                if len(structural_errors) >= settings.max_validation_errors_returned:
                    break
    except csv.Error as exc:
        return _build_failed_summary(
            filename=filename,
            detected_columns=cleaned_headers,
            has_training_target=has_training_target,
            errors=[
                ErrorDetail(
                    code="MALFORMED_CSV",
                    message=f"Malformed CSV syntax: {exc}",
                )
            ],
        )

    if structural_errors:
        return _build_failed_summary(
            filename=filename,
            detected_columns=cleaned_headers,
            has_training_target=has_training_target,
            errors=structural_errors,
        )

    try:
        df = pd.read_csv(
            io.StringIO(text_content),
            dtype=str,
            keep_default_na=False,
            skipinitialspace=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _build_failed_summary(
            filename=filename,
            detected_columns=cleaned_headers,
            has_training_target=has_training_target,
            errors=[
                ErrorDetail(
                    code="MALFORMED_CSV",
                    message=f"Unable to parse CSV with Pandas: {exc}",
                )
            ],
        )

    df.columns = [str(c).strip() for c in df.columns]
    total_rows = len(df)
    if total_rows == 0:
        return _build_failed_summary(
            filename=filename,
            detected_columns=cleaned_headers,
            has_training_target=has_training_target,
            is_synthetic_detected=assume_synthetic,
            errors=[
                ErrorDetail(
                    code="EMPTY_DATASET",
                    message="CSV contains a valid header but zero student data rows.",
                )
            ],
        )

    all_errors: List[ErrorDetail] = []
    invalid_row_indices: set[int] = set()
    seen_student_ids: Dict[str, int] = {}

    cleaned_features: List[Dict[str, Any]] = []
    cleaned_training_targets: Dict[str, int] = {}
    row_synthetic_flags: Dict[str, bool] = {}
    row_data_sources: Dict[str, str] = {}
    any_synthetic = assume_synthetic

    has_synthetic_col = SYNTHETIC_FLAG_COLUMN in df.columns
    has_source_col = DATA_SOURCE_COLUMN in df.columns

    def record_error(err: ErrorDetail, row_num: int) -> None:
        invalid_row_indices.add(row_num)
        all_errors.append(err)

    for idx, row in enumerate(df.to_dict(orient="records"), start=1):
        csv_line = idx + 1
        row_valid = True

        # 1. Validate shared student_id (non-missing, length <= 64, unique within CSV)
        raw_sid = str(row[ID_COLUMN])
        sid = raw_sid.strip()
        if _is_missing(raw_sid):
            record_error(
                ErrorDetail(
                    code="MISSING_VALUE",
                    row=idx,
                    csv_line=csv_line,
                    column=ID_COLUMN,
                    value=raw_sid,
                    message=f"Missing required value for '{ID_COLUMN}' at row {idx} (CSV line {csv_line}).",
                ),
                idx,
            )
            row_valid = False
        elif len(sid) > 64:
            record_error(
                ErrorDetail(
                    code="INVALID_STUDENT_ID",
                    row=idx,
                    csv_line=csv_line,
                    column=ID_COLUMN,
                    value=sid,
                    student_id=sid[:64],
                    message=f"student_id at row {idx} exceeds 64 characters.",
                ),
                idx,
            )
            row_valid = False
        elif sid in seen_student_ids:
            first_row = seen_student_ids[sid]
            record_error(
                ErrorDetail(
                    code="DUPLICATE_STUDENT_ID",
                    row=idx,
                    csv_line=csv_line,
                    column=ID_COLUMN,
                    value=sid,
                    student_id=sid,
                    message=(
                        f"Duplicate student_id '{sid}' at row {idx} (CSV line {csv_line}); "
                        f"first appeared at row {first_row}."
                    ),
                ),
                idx,
            )
            row_valid = False
        else:
            seen_student_ids[sid] = idx

        row_sid_label = sid if sid and not _is_missing(raw_sid) else None
        parsed_row: Dict[str, Any] = {ID_COLUMN: sid}

        # 2. Validate bounded float feature columns
        for rule in FLOAT_FIELD_RULES:
            raw_val = str(row[rule.column])
            if _is_missing(raw_val):
                record_error(
                    ErrorDetail(
                        code="MISSING_VALUE",
                        row=idx,
                        csv_line=csv_line,
                        column=rule.column,
                        value=raw_val,
                        student_id=row_sid_label,
                        message=(
                            f"Missing required value for '{rule.column}' at row {idx} "
                            f"(CSV line {csv_line})."
                        ),
                    ),
                    idx,
                )
                row_valid = False
                continue

            num_val = _parse_finite_float(raw_val)
            if num_val is None:
                record_error(
                    ErrorDetail(
                        code="INVALID_NUMERIC_VALUE",
                        row=idx,
                        csv_line=csv_line,
                        column=rule.column,
                        value=raw_val.strip(),
                        student_id=row_sid_label,
                        message=(
                            f"Invalid numeric value '{raw_val.strip()}' for '{rule.column}' "
                            f"at row {idx} (CSV line {csv_line}); expected {rule.unit_hint}."
                        ),
                    ),
                    idx,
                )
                row_valid = False
                continue

            if num_val < rule.min_val or num_val > rule.max_val:
                record_error(
                    ErrorDetail(
                        code=rule.range_error_code,
                        row=idx,
                        csv_line=csv_line,
                        column=rule.column,
                        value=raw_val.strip(),
                        student_id=row_sid_label,
                        message=(
                            f"Invalid {rule.column} '{raw_val.strip()}' at row {idx} "
                            f"(CSV line {csv_line}): must be a {rule.unit_hint}."
                        ),
                    ),
                    idx,
                )
                row_valid = False
                continue

            parsed_row[rule.column] = round(float(num_val), 4)

        # 3. Validate non-negative integer count columns
        for rule in INT_FIELD_RULES:
            raw_val = str(row[rule.column])
            if _is_missing(raw_val):
                record_error(
                    ErrorDetail(
                        code="MISSING_VALUE",
                        row=idx,
                        csv_line=csv_line,
                        column=rule.column,
                        value=raw_val,
                        student_id=row_sid_label,
                        message=(
                            f"Missing required value for '{rule.column}' at row {idx} "
                            f"(CSV line {csv_line})."
                        ),
                    ),
                    idx,
                )
                row_valid = False
                continue

            num_val = _parse_finite_float(raw_val)
            if num_val is None:
                record_error(
                    ErrorDetail(
                        code="INVALID_INTEGER_COUNT",
                        row=idx,
                        csv_line=csv_line,
                        column=rule.column,
                        value=raw_val.strip(),
                        student_id=row_sid_label,
                        message=(
                            f"Invalid integer '{raw_val.strip()}' for '{rule.column}' "
                            f"at row {idx} (CSV line {csv_line}); expected a non-negative whole number."
                        ),
                    ),
                    idx,
                )
                row_valid = False
                continue

            if num_val < 0:
                record_error(
                    ErrorDetail(
                        code=rule.negative_error_code,
                        row=idx,
                        csv_line=csv_line,
                        column=rule.column,
                        value=raw_val.strip(),
                        student_id=row_sid_label,
                        message=(
                            f"Negative count '{raw_val.strip()}' for '{rule.column}' at row {idx} "
                            f"(CSV line {csv_line}): counts must be >= 0."
                        ),
                    ),
                    idx,
                )
                row_valid = False
                continue

            if not num_val.is_integer():
                record_error(
                    ErrorDetail(
                        code="INVALID_INTEGER_COUNT",
                        row=idx,
                        csv_line=csv_line,
                        column=rule.column,
                        value=raw_val.strip(),
                        student_id=row_sid_label,
                        message=(
                            f"Non-integer value '{raw_val.strip()}' for '{rule.column}' at row {idx} "
                            f"(CSV line {csv_line}): expected a whole integer >= 0."
                        ),
                    ),
                    idx,
                )
                row_valid = False
                continue

            parsed_row[rule.column] = int(num_val)

        # 4. Validate optional training-only target (dropout_label), keeping it separate from features
        if has_training_target:
            raw_target = str(row[TRAINING_TARGET_COLUMN])
            if _is_missing(raw_target):
                record_error(
                    ErrorDetail(
                        code="MISSING_VALUE",
                        row=idx,
                        csv_line=csv_line,
                        column=TRAINING_TARGET_COLUMN,
                        value=raw_target,
                        student_id=row_sid_label,
                        message=(
                            f"Missing value for training target '{TRAINING_TARGET_COLUMN}' "
                            f"at row {idx} (CSV line {csv_line})."
                        ),
                    ),
                    idx,
                )
                row_valid = False
            else:
                target_num = _parse_finite_float(raw_target)
                if target_num is None or not target_num.is_integer() or int(target_num) not in (0, 1):
                    record_error(
                        ErrorDetail(
                            code="INVALID_DROPOUT_LABEL",
                            row=idx,
                            csv_line=csv_line,
                            column=TRAINING_TARGET_COLUMN,
                            value=raw_target.strip(),
                            student_id=row_sid_label,
                            message=(
                                f"Invalid '{TRAINING_TARGET_COLUMN}' value '{raw_target.strip()}' "
                                f"at row {idx} (CSV line {csv_line}); must be 0 or 1."
                            ),
                        ),
                        idx,
                    )
                    row_valid = False
                elif row_sid_label:
                    cleaned_training_targets[sid] = int(target_num)

        # 5. Validate optional synthetic metadata columns
        row_is_synthetic = assume_synthetic
        if has_synthetic_col:
            raw_syn = str(row[SYNTHETIC_FLAG_COLUMN])
            if not _is_missing(raw_syn):
                parsed_bool = _parse_boolean(raw_syn)
                if parsed_bool is None:
                    record_error(
                        ErrorDetail(
                            code="INVALID_BOOLEAN_VALUE",
                            row=idx,
                            csv_line=csv_line,
                            column=SYNTHETIC_FLAG_COLUMN,
                            value=raw_syn.strip(),
                            student_id=row_sid_label,
                            message=(
                                f"Invalid boolean '{raw_syn.strip()}' for '{SYNTHETIC_FLAG_COLUMN}' "
                                f"at row {idx} (CSV line {csv_line}); expected true/false or 1/0."
                            ),
                        ),
                        idx,
                    )
                    row_valid = False
                else:
                    row_is_synthetic = row_is_synthetic or parsed_bool

        if row_is_synthetic:
            any_synthetic = True

        row_source = SYNTHETIC_DATA_SOURCE if row_is_synthetic else "csv_upload"
        if has_source_col and not _is_missing(str(row[DATA_SOURCE_COLUMN])):
            raw_src = str(row[DATA_SOURCE_COLUMN]).strip()[:64]
            row_source = raw_src
            if "synthetic" in raw_src.lower():
                row_is_synthetic = True
                any_synthetic = True

        if row_valid and row_sid_label:
            cleaned_features.append(parsed_row)
            row_synthetic_flags[sid] = row_is_synthetic
            row_data_sources[sid] = row_source

    total_errors = len(all_errors)
    max_errors = settings.max_validation_errors_returned
    errors_truncated = total_errors > max_errors
    returned_errors = all_errors[:max_errors]
    invalid_count = len(invalid_row_indices)
    is_valid = total_errors == 0

    summary = ValidationSummaryData(
        is_valid=is_valid,
        filename=filename,
        total_rows=total_rows,
        valid_rows=total_rows - invalid_count,
        invalid_rows=invalid_count,
        error_count=total_errors,
        errors_truncated=errors_truncated,
        required_columns=list(REQUIRED_CSV_COLUMNS),
        detected_columns=cleaned_headers,
        missing_columns=[],
        has_training_target=has_training_target,
        training_target_column=TRAINING_TARGET_COLUMN if has_training_target else None,
        is_synthetic_detected=any_synthetic,
        synthetic_label="SYNTHETIC_DEMO_DATA" if any_synthetic else None,
        errors=returned_errors,
    )

    if not is_valid:
        return CSVValidationResult(summary=summary)

    return CSVValidationResult(
        summary=summary,
        cleaned_features=cleaned_features,
        cleaned_training_targets=cleaned_training_targets if has_training_target else {},
        row_synthetic_flags=row_synthetic_flags,
        row_data_sources=row_data_sources,
    )

