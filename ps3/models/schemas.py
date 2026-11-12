"""Pydantic schemas and consistent JSON response envelope for EDUCORE AI PS3."""

from datetime import datetime
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    """Structured error entry for CSV validation, HTTP, and domain errors."""

    code: str
    message: str
    row: Optional[int] = Field(default=None, description="1-based data row index in CSV.")
    csv_line: Optional[int] = Field(default=None, description="1-based physical line in CSV.")
    column: Optional[str] = None
    value: Optional[str] = None
    student_id: Optional[str] = None


class ResponseMeta(BaseModel):
    """Consistent metadata attached to every API response."""

    module: str = "ps3"
    api_version: str
    timestamp: datetime
    contains_synthetic_data: bool = False
    synthetic_notice: Optional[str] = None


class APIResponse(BaseModel, Generic[DataT]):
    """Consistent top-level JSON response structure across all PS3 endpoints."""

    status: Literal["success", "error"]
    message: str
    data: Optional[DataT] = None
    errors: List[ErrorDetail] = Field(default_factory=list)
    meta: ResponseMeta


class HealthData(BaseModel):
    """Health check payload."""

    service: str
    environment: str
    database_connected: bool
    database_dialect: str
    model_artifact_available: bool = False


class ValidationSummaryData(BaseModel):
    """Dry-run CSV validation result payload."""

    is_valid: bool
    filename: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    error_count: int
    errors_truncated: bool = False
    required_columns: List[str]
    detected_columns: List[str]
    missing_columns: List[str] = Field(default_factory=list)
    has_training_target: bool = False
    training_target_column: Optional[str] = None
    is_synthetic_detected: bool = False
    synthetic_label: Optional[str] = None
    errors: List[ErrorDetail] = Field(default_factory=list)


class UploadData(BaseModel):
    """CSV ingestion result payload."""

    batch_id: int
    filename: str
    ingested_rows: int
    new_students: int
    updated_students: int
    snapshots_created: int
    training_targets_stored: int
    has_training_target: bool
    is_synthetic: bool
    data_source: str
    synthetic_label: Optional[str] = None
    uploaded_at: datetime


class FeatureStat(BaseModel):
    """Descriptive statistics for a single numeric input feature."""

    min: float
    max: float
    mean: float
    median: float
    std: float


class TrainingTargetsSummary(BaseModel):
    """Isolated summary of training-only dropout_label targets."""

    total_labeled_snapshots: int
    dropout_count: int
    retained_count: int
    dropout_rate_pct: float
    note: str = "dropout_label is stored strictly in training_targets and excluded from inference features."


class DataSummaryData(BaseModel):
    """Real database summary payload for GET /data/summary."""

    total_students: int
    real_students: int
    synthetic_students: int
    contains_synthetic_data: bool
    synthetic_data_notice: Optional[str] = None
    total_activity_snapshots: int
    total_ingestion_batches: int
    total_predictions: int
    total_interventions: int
    latest_risk_distribution: Dict[str, int] = Field(default_factory=dict)
    training_targets_summary: TrainingTargetsSummary
    feature_statistics: dict[str, FeatureStat] = Field(default_factory=dict)


class ActivityFeaturesOut(BaseModel):
    """The 7 numeric input features + timestamp (strictly excludes dropout_label)."""

    model_config = ConfigDict(from_attributes=True)

    snapshot_id: int
    attendance_rate: float
    average_grade: float
    late_assignments: int
    missing_assignments: int
    lms_logins_30d: int
    engagement_change_pct: float
    previous_failure_count: int
    is_synthetic: bool
    data_source: str
    recorded_at: datetime


class PredictionOut(BaseModel):
    """Stored Phase 2 prediction record (never hardcoded)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    snapshot_id: Optional[int] = None
    risk_score: float
    risk_level: str
    model_version: str
    top_risk_factors: Optional[dict[str, Any]] = None
    is_synthetic_input: bool
    predicted_at: datetime


class InterventionOut(BaseModel):
    """Stored counselor intervention record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: Optional[str] = None
    prediction_id: Optional[int] = None
    intervention_type: str
    recommended_action: str
    priority: str = "medium"
    status: str
    assigned_to: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    is_demo: bool = False
    version: int = 1
    is_archived: bool = False
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class StudentListItem(BaseModel):
    """Summary representation of a student with latest activity features and risk score."""

    student_id: str
    is_synthetic: bool
    data_source: str
    synthetic_label: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    latest_features: Optional[ActivityFeaturesOut] = None
    latest_risk_probability: Optional[float] = None
    latest_risk_level: Optional[Literal["low", "medium", "high"]] = None
    latest_prediction_id: Optional[int] = None
    latest_prediction_timestamp: Optional[datetime] = None
    snapshot_count: int = 0
    prediction_count: int = 0
    intervention_count: int = 0


class StudentListData(BaseModel):
    """Paginated list of students."""

    items: List[StudentListItem]
    total: int
    limit: int
    offset: int
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
    has_next: bool = False
    has_previous: bool = False
    synthetic_count_in_page: int
    real_count_in_page: int


class StudentDetailData(BaseModel):
    """Detailed view of a single student across snapshots, predictions, and interventions."""

    student_id: str
    is_synthetic: bool
    data_source: str
    synthetic_label: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    latest_features: Optional[ActivityFeaturesOut] = None
    activity_history: List[ActivityFeaturesOut] = Field(default_factory=list)
    predictions: List[PredictionOut] = Field(default_factory=list)
    interventions: List[InterventionOut] = Field(default_factory=list)
    has_training_target_record: bool = False


# ==============================================================================
# Phase 2: ML Pipeline, Evaluation, Risk Classification, XAI & Recommendations
# ==============================================================================


class TrainModelRequest(BaseModel):
    """Optional configuration overrides when triggering model training."""

    dataset_mode: Literal["auto", "real_only", "synthetic_only"] = "auto"
    allow_synthetic_fallback: bool = True
    test_size: Optional[float] = Field(default=None, gt=0.05, lt=0.5)
    n_estimators: Optional[int] = Field(default=None, ge=10, le=1000)
    max_depth: Optional[int] = Field(default=None, ge=2, le=50)
    random_state: Optional[int] = None


class ConfusionMatrixOut(BaseModel):
    """Binary 2x2 confusion matrix (`labels=[0, 1]`)."""

    matrix: List[List[int]]
    tn: int
    fp: int
    fn: int
    tp: int


class ClassDistributionOut(BaseModel):
    """Target class balance across full, train, and test datasets."""

    total_samples: int
    retained_0: int
    dropout_1: int
    dropout_rate_pct: float
    train_distribution: Dict[str, int]
    test_distribution: Dict[str, int]


class ModelEvaluationMetrics(BaseModel):
    """Evaluation metrics computed on the stratified holdout test set."""

    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: Optional[float] = None
    roc_auc_note: Optional[str] = None
    confusion_matrix: ConfusionMatrixOut
    class_distribution: ClassDistributionOut
    feature_importances: Dict[str, float]


class ModelMetricsData(BaseModel):
    """Model metadata, threshold configuration, and evaluation report."""

    model_version: str
    algorithm: str
    trained_at: datetime
    feature_columns: List[str]
    training_source: str
    is_demo_model: bool
    evaluation_disclaimer: str
    sample_count: int
    train_count: int
    test_count: int
    threshold_profile: str
    thresholds: Dict[str, float]
    hyperparameters: Dict[str, Any]
    evaluation: ModelEvaluationMetrics


class RiskIndicatorOut(BaseModel):
    """Single contributing or protective indicator explaining a student's risk assessment."""

    feature: str
    value: Optional[Union[float, int]] = None
    direction: Literal["increases_risk", "protective", "neutral"]
    importance_weight: float
    summary: str


class ExplanationOut(BaseModel):
    """Transparent, non-causal explanation for a student's risk prediction."""

    method: str
    is_shap: bool
    method_label: str
    causation_disclaimer: str
    indicators: List[RiskIndicatorOut]


class RecommendedInterventionOut(BaseModel):
    """Auditable advisory recommendation for human review."""

    intervention_id: Optional[int] = None
    intervention_type: str
    priority: Literal["high", "medium", "low"]
    recommended_action: str
    trigger_reason: str
    status: str = "pending_review"
    requires_human_review: bool = True


class PredictionRunRequest(BaseModel):
    """Parameters for running batch or targeted student risk predictions."""

    student_ids: Optional[List[str]] = None
    include_synthetic: bool = True
    model_version: Optional[str] = None
    persist_interventions: bool = True


class PredictionRecordOut(BaseModel):
    """Complete Phase 2 prediction payload including risk level, explanation, and recommendations."""

    prediction_id: int
    student_id: str
    snapshot_id: Optional[int] = None
    risk_probability: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high"]
    model_version: str
    prediction_timestamp: datetime
    is_demo: bool
    threshold_profile: str
    thresholds_used: Dict[str, float]
    explanation: ExplanationOut
    recommended_interventions: List[RecommendedInterventionOut] = Field(default_factory=list)
    human_review_notice: str


class PredictionRunData(BaseModel):
    """Summary and items produced by POST /api/ps3/predictions/run."""

    model_version: str
    is_demo_model: bool
    threshold_profile: str
    thresholds: Dict[str, float]
    total_predicted: int
    risk_breakdown: Dict[str, int]
    interventions_persisted: int
    predictions: List[PredictionRecordOut]


class PredictionListData(BaseModel):
    """Paginated predictions query response."""

    items: List[PredictionRecordOut]
    total: int
    limit: int
    offset: int
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
    has_next: bool = False
    has_previous: bool = False
    risk_breakdown_in_page: Dict[str, int]


class StudentExplanationData(BaseModel):
    """Student-centric explanation and retention recommendation view."""

    student_id: str
    is_synthetic: bool
    data_source: str
    latest_features: Optional[ActivityFeaturesOut] = None
    prediction: PredictionRecordOut
    human_review_notice: str


# ==============================================================================
# Phase 4: Persistent Intervention Management & Audit History
# ==============================================================================

InterventionStatus = Literal[
    "PENDING",
    "ASSIGNED",
    "IN_PROGRESS",
    "FOLLOW_UP_REQUIRED",
    "COMPLETED",
    "CANCELLED",
]
InterventionPriority = Literal["high", "medium", "low"]


class InterventionHistoryOut(BaseModel):
    """Chronological intervention lifecycle audit entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    intervention_id: int
    student_id: str
    action: str
    actor_id: Optional[str] = None
    actor_user_id: Optional[int] = None
    actor_role: Optional[str] = None
    previous_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    summary: str
    created_at: datetime


class InterventionRecordOut(BaseModel):
    """Full intervention workflow record enriched with student/prediction context."""

    id: int
    student_id: str
    prediction_id: Optional[int] = None
    intervention_type: str
    recommended_action: str
    priority: InterventionPriority
    status: InterventionStatus
    raw_status: str
    assigned_to: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    is_demo: bool = False
    version: int = 1
    is_archived: bool = False
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    latest_risk_level: Optional[Literal["low", "medium", "high"]] = None
    latest_risk_probability: Optional[float] = None
    history_count: int = 0
    human_review_notice: str


class InterventionSummaryCounts(BaseModel):
    """Real database status counts across interventions."""

    total: int
    pending: int
    assigned: int
    in_progress: int
    follow_up_required: int
    follow_ups_due: int
    completed: int
    cancelled: int


class InterventionListData(BaseModel):
    """Paginated intervention directory payload."""

    items: List[InterventionRecordOut]
    total: int
    limit: int
    offset: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
    status_counts: InterventionSummaryCounts


class InterventionDetailData(BaseModel):
    """Detailed view of one intervention including student, prediction, and history."""

    intervention: InterventionRecordOut
    student_is_synthetic: bool
    related_prediction: Optional[PredictionOut] = None
    history: List[InterventionHistoryOut] = Field(default_factory=list)
    allowed_next_statuses: List[InterventionStatus] = Field(default_factory=list)
    auth_notice: str


class InterventionHistoryListData(BaseModel):
    """Audit history timeline response for a single intervention."""

    intervention_id: int
    student_id: str
    items: List[InterventionHistoryOut] = Field(default_factory=list)
    total: int


class StudentInterventionsData(BaseModel):
    """All interventions associated with a shared student_id."""

    student_id: str
    is_synthetic: bool
    items: List[InterventionRecordOut] = Field(default_factory=list)
    total: int
    status_counts: InterventionSummaryCounts
    human_review_notice: str


class InterventionCreateRequest(BaseModel):
    """Payload to manually create a counselor-reviewed student intervention."""

    student_id: str = Field(min_length=1, max_length=64)
    prediction_id: Optional[int] = Field(default=None, ge=1)
    intervention_type: str = Field(min_length=2, max_length=64)
    recommended_action: str = Field(min_length=3, max_length=2000)
    priority: InterventionPriority = "medium"
    status: Optional[InterventionStatus] = None
    assigned_to: Optional[str] = Field(default=None, max_length=128)
    follow_up_date: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=4000)
    actor_id: Optional[str] = Field(default=None, max_length=128)
    allow_duplicate: bool = False


class InterventionUpdateRequest(BaseModel):
    """Partial update payload enforcing optimistic concurrency via current version."""

    version: int = Field(ge=1, description="Current intervention version for concurrency safety.")
    assigned_to: Optional[str] = Field(default=None, max_length=128)
    status: Optional[InterventionStatus] = None
    priority: Optional[InterventionPriority] = None
    follow_up_date: Optional[datetime] = None
    recommended_action: Optional[str] = Field(default=None, min_length=3, max_length=2000)
    notes: Optional[str] = Field(default=None, max_length=4000)
    actor_id: Optional[str] = Field(default=None, max_length=128)


class InterventionArchiveRequest(BaseModel):
    """Soft-archive request preserving student/intervention audit history."""

    version: int = Field(ge=1)
    reason: Optional[str] = Field(default=None, max_length=500)


# ==============================================================================
# Phase 5: Authentication, RBAC, Audit Logs, Notifications & Operational Status
# ==============================================================================

UserRole = Literal["administrator", "counsellor", "viewer"]


class UserOut(BaseModel):
    """Sanitized account projection (never includes passwords or hashes)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class LoginRequest(BaseModel):
    """Username or email login payload."""

    username_or_email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class LoginData(BaseModel):
    """Authenticated login session response (session token kept in HttpOnly cookie)."""

    user: UserOut
    csrf_token: str
    expires_at: datetime
    session_ttl_minutes: int


class SessionMeData(BaseModel):
    """Current authenticated user & active session details."""

    user: UserOut
    csrf_token: str
    expires_at: datetime


class UserCreateRequest(BaseModel):
    """Administrator payload to create a platform account."""

    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    email: str = Field(min_length=5, max_length=255)
    full_name: str = Field(min_length=2, max_length=128)
    role: UserRole
    password: str = Field(min_length=8, max_length=256)
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    """Administrator payload to update role, active status, display name, or password."""

    full_name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    email: Optional[str] = Field(default=None, min_length=5, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=256)


class UserListData(BaseModel):
    """List of managed user accounts."""

    items: List[UserOut]
    total: int


class NotificationOut(BaseModel):
    """In-app and email delivery tracking entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient_user_id: Optional[int] = None
    recipient_username: Optional[str] = None
    intervention_id: Optional[int] = None
    student_id: Optional[str] = None
    event_type: str
    channel: str
    title: str
    message: str
    email_status: str
    email_attempts: int
    last_error: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
    sent_at: Optional[datetime] = None


class NotificationListData(BaseModel):
    """Paginated notification inbox with unread count."""

    items: List[NotificationOut]
    total: int
    unread_count: int
    email_transport: str
    email_verification_notice: str


class NotificationScanData(BaseModel):
    """Summary of follow-up alert generation pass."""

    created_count: int
    approaching_count: int
    overdue_count: int
    email_transport: str


class SecurityAuditLogOut(BaseModel):
    """Security & administrative audit event entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: Optional[int] = None
    actor_username: Optional[str] = None
    actor_role: Optional[str] = None
    event_type: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    summary: str
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime


class SecurityAuditListData(BaseModel):
    """Paginated security audit trail."""

    items: List[SecurityAuditLogOut]
    total: int


class OperationalStatusData(BaseModel):
    """Administrator operational telemetry separated from student risk analytics."""

    service: str
    environment: str
    database_connected: bool
    database_dialect: str
    model_artifact_available: bool
    active_model_version: Optional[str] = None
    active_sessions_count: int
    total_users: int
    active_users: int
    failed_logins_24h: int
    failed_notifications_count: int
    archived_students_count: int
    archived_interventions_count: int
    docs_enabled: bool
    cookie_secure: bool
    email_transport: str


