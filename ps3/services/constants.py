"""Domain constants for EDUCORE AI PS3."""

# Required input columns (inference + monitoring features + shared student_id)
ID_COLUMN = "student_id"

MODEL_FEATURE_COLUMNS = (
    "attendance_rate",
    "average_grade",
    "late_assignments",
    "missing_assignments",
    "lms_logins_30d",
    "engagement_change_pct",
    "previous_failure_count",
)

REQUIRED_CSV_COLUMNS = (ID_COLUMN, *MODEL_FEATURE_COLUMNS)

# Training-only target column: kept strictly separate from inference features
TRAINING_TARGET_COLUMN = "dropout_label"

# Optional synthetic-labeling metadata columns recognized in CSV files
SYNTHETIC_FLAG_COLUMN = "is_synthetic"
DATA_SOURCE_COLUMN = "data_source"

OPTIONAL_METADATA_COLUMNS = (
    SYNTHETIC_FLAG_COLUMN,
    DATA_SOURCE_COLUMN,
)

# Domain validation bounds
MIN_ATTENDANCE_RATE = 0.0
MAX_ATTENDANCE_RATE = 100.0
MIN_AVERAGE_GRADE = 0.0
MAX_AVERAGE_GRADE = 100.0
MIN_ENGAGEMENT_CHANGE_PCT = -100.0
MAX_ENGAGEMENT_CHANGE_PCT = 1000.0
MIN_NON_NEGATIVE_COUNT = 0

NON_NEGATIVE_INT_COLUMNS = (
    "late_assignments",
    "missing_assignments",
    "lms_logins_30d",
    "previous_failure_count",
)

NUMERIC_FLOAT_COLUMNS = (
    "attendance_rate",
    "average_grade",
    "engagement_change_pct",
)

MISSING_SENTINELS = frozenset({"", "na", "n/a", "null", "none", "nan", "nil", "-"})

DEFAULT_DATA_SOURCE = "csv_upload"
SYNTHETIC_DATA_SOURCE = "synthetic_demo"
SYNTHETIC_NOTICE_MESSAGE = (
    "Dataset includes synthetic demo student records clearly labeled with is_synthetic=true "
    "and data_source='synthetic_demo'. Do not treat synthetic records as real institutional data."
)

# Phase 2 ML, Evaluation, Explainability & Recommendation Disclaimers
SYNTHETIC_METRICS_DISCLAIMER = (
    "DEMONSTRATION METRICS ONLY: This model was trained and evaluated on synthetic demo records, "
    "not real institutional student outcomes. Do not treat these metrics as real-world performance."
)
REAL_METRICS_DISCLAIMER = (
    "Evaluated on held-out labeled records from the institutional database. Monitor continuously for cohort drift."
)
CAUSATION_DISCLAIMER = (
    "Contributing indicators reflect statistical patterns and domain reference comparisons only; "
    "correlation does not prove causation."
)
HUMAN_REVIEW_NOTICE = (
    "All risk predictions and intervention recommendations are advisory aids for human counselor/faculty "
    "review, not automated institutional decisions."
)

