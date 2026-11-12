"""SQLAlchemy ORM models for EDUCORE AI PS3."""

from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def _utc_now() -> datetime:
    """Return current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Student(Base):
    """Canonical student record preserving the shared institutional student_id."""

    __tablename__ = "students"

    student_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    data_source: Mapped[str] = mapped_column(String(64), nullable=False, default="csv_upload")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    snapshots: Mapped[List["ActivitySnapshot"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="desc(ActivitySnapshot.recorded_at), desc(ActivitySnapshot.id)",
    )
    training_targets: Mapped[List["TrainingTarget"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="desc(TrainingTarget.recorded_at), desc(TrainingTarget.id)",
    )
    predictions: Mapped[List["Prediction"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        order_by="desc(Prediction.predicted_at), desc(Prediction.id)",
    )
    interventions: Mapped[List["Intervention"]] = relationship(
        back_populates="student",
        passive_deletes=True,
        order_by="desc(Intervention.created_at), desc(Intervention.id)",
    )


class IngestionBatch(Base):
    """Audit record for each CSV ingestion or synthetic dataset load."""

    __tablename__ = "ingestion_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    has_training_labels: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    data_source: Mapped[str] = mapped_column(String(64), nullable=False, default="csv_upload")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    snapshots: Mapped[List["ActivitySnapshot"]] = relationship(back_populates="batch")


class ActivitySnapshot(Base):
    """Point-in-time academic & LMS engagement feature snapshot (excludes training target)."""

    __tablename__ = "activity_snapshots"
    __table_args__ = (
        CheckConstraint(
            "attendance_rate >= 0.0 AND attendance_rate <= 100.0",
            name="ck_snapshot_attendance_range",
        ),
        CheckConstraint(
            "average_grade >= 0.0 AND average_grade <= 100.0",
            name="ck_snapshot_grade_range",
        ),
        CheckConstraint("late_assignments >= 0", name="ck_snapshot_late_nonneg"),
        CheckConstraint("missing_assignments >= 0", name="ck_snapshot_missing_nonneg"),
        CheckConstraint("lms_logins_30d >= 0", name="ck_snapshot_logins_nonneg"),
        CheckConstraint("engagement_change_pct >= -100.0", name="ck_snapshot_engagement_min"),
        CheckConstraint("previous_failure_count >= 0", name="ck_snapshot_failures_nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("ingestion_batches.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Strictly the 7 numeric model features (paired with shared student_id)
    attendance_rate: Mapped[float] = mapped_column(Float, nullable=False)
    average_grade: Mapped[float] = mapped_column(Float, nullable=False)
    late_assignments: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_assignments: Mapped[int] = mapped_column(Integer, nullable=False)
    lms_logins_30d: Mapped[int] = mapped_column(Integer, nullable=False)
    engagement_change_pct: Mapped[float] = mapped_column(Float, nullable=False)
    previous_failure_count: Mapped[int] = mapped_column(Integer, nullable=False)

    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    data_source: Mapped[str] = mapped_column(String(64), nullable=False, default="csv_upload")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    student: Mapped["Student"] = relationship(back_populates="snapshots")
    batch: Mapped[Optional["IngestionBatch"]] = relationship(back_populates="snapshots")
    training_target: Mapped[Optional["TrainingTarget"]] = relationship(
        back_populates="snapshot",
        uselist=False,
        cascade="all, delete-orphan",
    )
    predictions: Mapped[List["Prediction"]] = relationship(back_populates="snapshot")


class TrainingTarget(Base):
    """Training-only ground-truth dropout target stored separately from inference features."""

    __tablename__ = "training_targets"
    __table_args__ = (
        CheckConstraint("dropout_label IN (0, 1)", name="ck_training_dropout_binary"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("activity_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    dropout_label: Mapped[int] = mapped_column(Integer, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    student: Mapped["Student"] = relationship(back_populates="training_targets")
    snapshot: Mapped["ActivitySnapshot"] = relationship(back_populates="training_target")


class Prediction(Base):
    """Model risk prediction outputs (populated by Phase 2 ML pipeline; never hardcoded)."""

    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("risk_score >= 0.0 AND risk_score <= 1.0", name="ck_prediction_risk_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("activity_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    top_risk_factors: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_synthetic_input: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )

    student: Mapped["Student"] = relationship(back_populates="predictions")
    snapshot: Mapped[Optional["ActivitySnapshot"]] = relationship(back_populates="predictions")
    interventions: Mapped[List["Intervention"]] = relationship(back_populates="prediction")


class Intervention(Base):
    """Retention counselor interventions linked to a student and optional prediction."""

    __tablename__ = "interventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prediction_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("predictions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    intervention_type: Mapped[str] = mapped_column(String(64), nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    follow_up_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    student: Mapped["Student"] = relationship(back_populates="interventions")
    prediction: Mapped[Optional["Prediction"]] = relationship(back_populates="interventions")
    history: Mapped[List["InterventionHistory"]] = relationship(
        back_populates="intervention",
        passive_deletes=True,
        order_by="asc(InterventionHistory.created_at), asc(InterventionHistory.id)",
    )


class InterventionHistory(Base):
    """Append-only chronological audit log of lifecycle and field updates on an intervention."""

    __tablename__ = "intervention_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intervention_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("interventions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("students.student_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    previous_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )

    intervention: Mapped["Intervention"] = relationship(back_populates="history")


class User(Base):
    """Authenticated platform account with role-based access control."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    sessions: Mapped[List["UserSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserSession(Base):
    """Revocable server-side authentication session paired with CSRF double-submit token."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    user: Mapped["User"] = relationship(back_populates="sessions")


class SecurityAuditLog(Base):
    """Institutional authentication, RBAC, user management, and operational audit log."""

    __tablename__ = "security_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )


class Notification(Base):
    """Persistent in-app and email notification log with deduplication & delivery tracking."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    recipient_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    intervention_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("interventions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    student_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="in_app_and_email")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(191), nullable=False, unique=True, index=True)
    email_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="skipped_no_smtp", index=True
    )
    email_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, index=True
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class TrainedModel(Base):
    """Persisted metadata and evaluation metrics for trained PS3 ML pipelines."""

    __tablename__ = "trained_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False, default="RandomForestClassifier")
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    feature_columns: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    training_source: Mapped[str] = mapped_column(String(64), nullable=False)
    is_demo_model: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    train_count: Mapped[int] = mapped_column(Integer, nullable=False)
    test_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    hyperparameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

