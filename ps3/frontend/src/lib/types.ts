export interface ErrorDetail {
  code: string;
  message: string;
  row?: number | null;
  csv_line?: number | null;
  column?: string | null;
  value?: string | null;
  student_id?: string | null;
}

export interface ResponseMeta {
  module: string;
  api_version: string;
  timestamp: string;
  contains_synthetic_data: boolean;
  synthetic_notice?: string | null;
}

export interface APIResponse<T> {
  status: "success" | "error";
  message: string;
  data: T | null;
  errors: ErrorDetail[];
  meta: ResponseMeta;
}

export interface HealthData {
  service: string;
  environment: string;
  database_connected: boolean;
  database_dialect: string;
  model_artifact_available?: boolean;
}

export interface ValidationSummaryData {
  is_valid: boolean;
  filename: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  error_count: number;
  errors_truncated: boolean;
  required_columns: string[];
  detected_columns: string[];
  missing_columns: string[];
  has_training_target: boolean;
  training_target_column?: string | null;
  is_synthetic_detected: boolean;
  synthetic_label?: string | null;
  errors: ErrorDetail[];
}

export interface UploadData {
  batch_id: number;
  filename: string;
  ingested_rows: number;
  new_students: number;
  updated_students: number;
  snapshots_created: number;
  training_targets_stored: number;
  has_training_target: boolean;
  is_synthetic: boolean;
  data_source: string;
  synthetic_label?: string | null;
  uploaded_at: string;
}

export interface FeatureStat {
  min: number;
  max: number;
  mean: number;
  median: number;
  std: number;
}

export interface TrainingTargetsSummary {
  total_labeled_snapshots: number;
  dropout_count: number;
  retained_count: number;
  dropout_rate_pct: number;
  note: string;
}

export interface DataSummaryData {
  total_students: number;
  real_students: number;
  synthetic_students: number;
  contains_synthetic_data: boolean;
  synthetic_data_notice?: string | null;
  total_activity_snapshots: number;
  total_ingestion_batches: number;
  total_predictions: number;
  total_interventions: number;
  latest_risk_distribution?: Record<string, number>;
  training_targets_summary: TrainingTargetsSummary;
  feature_statistics: Record<string, FeatureStat>;
}

export interface ActivityFeaturesOut {
  snapshot_id: number;
  attendance_rate: number;
  average_grade: number;
  late_assignments: number;
  missing_assignments: number;
  lms_logins_30d: number;
  engagement_change_pct: number;
  previous_failure_count: number;
  is_synthetic: boolean;
  data_source: string;
  recorded_at: string;
}

export interface PredictionOut {
  id: number;
  snapshot_id?: number | null;
  risk_score: number;
  risk_level: string;
  model_version: string;
  top_risk_factors?: Record<string, unknown> | null;
  is_synthetic_input: boolean;
  predicted_at: string;
}

export interface InterventionOut {
  id: number;
  student_id?: string | null;
  prediction_id?: number | null;
  intervention_type: string;
  recommended_action: string;
  priority?: string;
  status: string;
  assigned_to?: string | null;
  follow_up_date?: string | null;
  completed_at?: string | null;
  notes?: string | null;
  is_demo?: boolean;
  created_at: string;
  updated_at: string;
}

export interface StudentListItem {
  student_id: string;
  is_synthetic: boolean;
  data_source: string;
  synthetic_label?: string | null;
  created_at: string;
  updated_at: string;
  latest_features?: ActivityFeaturesOut | null;
  latest_risk_probability?: number | null;
  latest_risk_level?: RiskLevel | null;
  latest_prediction_id?: number | null;
  latest_prediction_timestamp?: string | null;
  snapshot_count: number;
  prediction_count: number;
  intervention_count: number;
}

export interface StudentListData {
  items: StudentListItem[];
  total: number;
  limit: number;
  offset: number;
  page?: number;
  page_size?: number;
  total_pages?: number;
  has_next?: boolean;
  has_previous?: boolean;
  synthetic_count_in_page: number;
  real_count_in_page: number;
}

export interface StudentDetailData {
  student_id: string;
  is_synthetic: boolean;
  data_source: string;
  synthetic_label?: string | null;
  created_at: string;
  updated_at: string;
  latest_features?: ActivityFeaturesOut | null;
  activity_history: ActivityFeaturesOut[];
  predictions: PredictionOut[];
  interventions: InterventionOut[];
  has_training_target_record: boolean;
}

export interface TrainModelRequest {
  dataset_mode?: "auto" | "real_only" | "synthetic_only";
  allow_synthetic_fallback?: boolean;
  test_size?: number;
  n_estimators?: number;
  max_depth?: number;
  random_state?: number;
}

export interface ConfusionMatrixOut {
  matrix: number[][];
  tn: number;
  fp: number;
  fn: number;
  tp: number;
}

export interface ClassDistributionOut {
  total_samples: number;
  retained_0: number;
  dropout_1: number;
  dropout_rate_pct: number;
  train_distribution: Record<string, number>;
  test_distribution: Record<string, number>;
}

export interface ModelEvaluationMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  roc_auc?: number | null;
  roc_auc_note?: string | null;
  confusion_matrix: ConfusionMatrixOut;
  class_distribution: ClassDistributionOut;
  feature_importances: Record<string, number>;
}

export interface ModelMetricsData {
  model_version: string;
  algorithm: string;
  trained_at: string;
  feature_columns: string[];
  training_source: string;
  is_demo_model: boolean;
  evaluation_disclaimer: string;
  sample_count: number;
  train_count: number;
  test_count: number;
  threshold_profile: string;
  thresholds: Record<string, number>;
  hyperparameters: Record<string, unknown>;
  evaluation: ModelEvaluationMetrics;
}

export type RiskLevel = "low" | "medium" | "high";

export interface RiskIndicatorOut {
  feature: string;
  value?: number | null;
  direction: "increases_risk" | "protective" | "neutral";
  importance_weight: number;
  summary: string;
}

export interface ExplanationOut {
  method: string;
  is_shap: boolean;
  method_label: string;
  causation_disclaimer: string;
  indicators: RiskIndicatorOut[];
}

export interface RecommendedInterventionOut {
  intervention_id?: number | null;
  intervention_type: string;
  priority: "high" | "medium" | "low";
  recommended_action: string;
  trigger_reason: string;
  status: string;
  requires_human_review: boolean;
}

export interface PredictionRunRequest {
  student_ids?: string[];
  include_synthetic?: boolean;
  model_version?: string;
  persist_interventions?: boolean;
}

export interface PredictionRecordOut {
  prediction_id: number;
  student_id: string;
  snapshot_id?: number | null;
  risk_probability: number;
  risk_level: RiskLevel;
  model_version: string;
  prediction_timestamp: string;
  is_demo: boolean;
  threshold_profile: string;
  thresholds_used: Record<string, number>;
  explanation: ExplanationOut;
  recommended_interventions: RecommendedInterventionOut[];
  human_review_notice: string;
}

export interface PredictionRunData {
  model_version: string;
  is_demo_model: boolean;
  threshold_profile: string;
  thresholds: Record<string, number>;
  total_predicted: number;
  risk_breakdown: Record<string, number>;
  interventions_persisted: number;
  predictions: PredictionRecordOut[];
}

export interface PredictionListData {
  items: PredictionRecordOut[];
  total: number;
  limit: number;
  offset: number;
  page?: number;
  page_size?: number;
  total_pages?: number;
  has_next?: boolean;
  has_previous?: boolean;
  risk_breakdown_in_page: Record<string, number>;
}

export interface StudentExplanationData {
  student_id: string;
  is_synthetic: boolean;
  data_source: string;
  latest_features?: ActivityFeaturesOut | null;
  prediction: PredictionRecordOut;
  human_review_notice: string;
}

export type InterventionStatus =
  | "PENDING"
  | "ASSIGNED"
  | "IN_PROGRESS"
  | "FOLLOW_UP_REQUIRED"
  | "COMPLETED"
  | "CANCELLED";

export type InterventionPriority = "high" | "medium" | "low";

export interface InterventionHistoryOut {
  id: number;
  intervention_id: number;
  student_id: string;
  action: string;
  actor_id?: string | null;
  actor_user_id?: number | null;
  actor_role?: string | null;
  previous_value?: Record<string, unknown> | null;
  new_value?: Record<string, unknown> | null;
  summary: string;
  created_at: string;
}

export interface InterventionRecordOut {
  id: number;
  student_id: string;
  prediction_id?: number | null;
  intervention_type: string;
  recommended_action: string;
  priority: InterventionPriority;
  status: InterventionStatus;
  raw_status: string;
  assigned_to?: string | null;
  follow_up_date?: string | null;
  completed_at?: string | null;
  notes?: string | null;
  version: number;
  is_archived: boolean;
  archived_at?: string | null;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
  latest_risk_level?: RiskLevel | null;
  latest_risk_probability?: number | null;
  history_count: number;
  human_review_notice: string;
}

export interface InterventionSummaryCounts {
  total: number;
  pending: number;
  assigned: number;
  in_progress: number;
  follow_up_required: number;
  follow_ups_due: number;
  completed: number;
  cancelled: number;
}

export interface InterventionListData {
  items: InterventionRecordOut[];
  total: number;
  limit: number;
  offset: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
  status_counts: InterventionSummaryCounts;
}

export interface InterventionDetailData {
  intervention: InterventionRecordOut;
  student_is_synthetic: boolean;
  related_prediction?: PredictionOut | null;
  history: InterventionHistoryOut[];
  allowed_next_statuses: InterventionStatus[];
  auth_notice: string;
}

export interface InterventionHistoryListData {
  intervention_id: number;
  student_id: string;
  items: InterventionHistoryOut[];
  total: number;
}

export interface StudentInterventionsData {
  student_id: string;
  is_synthetic: boolean;
  items: InterventionRecordOut[];
  total: number;
  status_counts: InterventionSummaryCounts;
  human_review_notice: string;
}

export interface InterventionCreateRequest {
  student_id: string;
  prediction_id?: number | null;
  intervention_type: string;
  recommended_action: string;
  priority?: InterventionPriority;
  status?: InterventionStatus;
  assigned_to?: string | null;
  follow_up_date?: string | null;
  notes?: string | null;
  actor_id?: string | null;
  allow_duplicate?: boolean;
}

export interface InterventionUpdateRequest {
  version: number;
  assigned_to?: string | null;
  status?: InterventionStatus;
  priority?: InterventionPriority;
  follow_up_date?: string | null;
  recommended_action?: string | null;
  notes?: string | null;
  actor_id?: string | null;
}

export interface InterventionArchiveRequest {
  version: number;
  reason?: string | null;
}

export type UserRole = "administrator" | "counsellor" | "viewer";

export interface UserOut {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  last_login_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LoginData {
  user: UserOut;
  csrf_token: string;
  expires_at: string;
  session_ttl_minutes: number;
}

export interface SessionMeData {
  user: UserOut;
  csrf_token: string;
  expires_at: string;
}

export interface UserCreateRequest {
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  password: string;
  is_active?: boolean;
}

export interface UserUpdateRequest {
  full_name?: string;
  email?: string;
  role?: UserRole;
  is_active?: boolean;
  new_password?: string;
}

export interface UserListData {
  items: UserOut[];
  total: number;
}

export interface NotificationOut {
  id: number;
  recipient_user_id?: number | null;
  recipient_username?: string | null;
  intervention_id?: number | null;
  student_id?: string | null;
  event_type: string;
  channel: string;
  title: string;
  message: string;
  email_status: string;
  email_attempts: number;
  last_error?: string | null;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
  sent_at?: string | null;
}

export interface NotificationListData {
  items: NotificationOut[];
  total: number;
  unread_count: number;
  email_transport: string;
  email_verification_notice: string;
}

export interface NotificationScanData {
  created_count: number;
  approaching_count: number;
  overdue_count: number;
  email_transport: string;
}

export interface SecurityAuditLogOut {
  id: number;
  actor_user_id?: number | null;
  actor_username?: string | null;
  actor_role?: string | null;
  event_type: string;
  target_type?: string | null;
  target_id?: string | null;
  summary: string;
  details?: Record<string, unknown> | null;
  ip_address?: string | null;
  created_at: string;
}

export interface SecurityAuditListData {
  items: SecurityAuditLogOut[];
  total: number;
}

export interface OperationalStatusData {
  service: string;
  environment: string;
  database_connected: boolean;
  database_dialect: string;
  model_artifact_available: boolean;
  active_model_version?: string | null;
  active_sessions_count: number;
  total_users: number;
  active_users: number;
  failed_logins_24h: number;
  failed_notifications_count: number;
  archived_students_count: number;
  archived_interventions_count: number;
  docs_enabled: boolean;
  cookie_secure: boolean;
  email_transport: string;
}

