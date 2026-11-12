"""Database engine, session management, and initialization utilities."""

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings


class Base(DeclarativeBase):
    """Base declarative class for all PS3 SQLAlchemy ORM models."""


def _configure_sqlite_foreign_keys(engine: Engine) -> None:
    """Ensure SQLite enforces foreign key constraints just like PostgreSQL."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a configured SQLAlchemy engine for PostgreSQL/Supabase or SQLite."""
    url = database_url or get_settings().normalized_database_url
    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            future=True,
        )
        _configure_sqlite_foreign_keys(engine)
        return engine

    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
    )


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def apply_additive_migrations(target_engine: Engine) -> None:
    """Safely add Phase 4 & Phase 5 columns, indexes, and audit-protection triggers."""
    inspector = inspect(target_engine)
    dialect = target_engine.dialect.name
    dt_type = "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME"
    bool_false = "FALSE" if dialect == "postgresql" else "0"

    table_column_ddl: dict[str, dict[str, str]] = {
        "students": {
            "is_archived": f"ALTER TABLE students ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT {bool_false}",
            "archived_at": f"ALTER TABLE students ADD COLUMN archived_at {dt_type}",
        },
        "interventions": {
            "priority": "ALTER TABLE interventions ADD COLUMN priority VARCHAR(16) NOT NULL DEFAULT 'medium'",
            "follow_up_date": f"ALTER TABLE interventions ADD COLUMN follow_up_date {dt_type}",
            "completed_at": f"ALTER TABLE interventions ADD COLUMN completed_at {dt_type}",
            "is_demo": f"ALTER TABLE interventions ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT {bool_false}",
            "version": "ALTER TABLE interventions ADD COLUMN version INTEGER NOT NULL DEFAULT 1",
            "is_archived": f"ALTER TABLE interventions ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT {bool_false}",
            "archived_at": f"ALTER TABLE interventions ADD COLUMN archived_at {dt_type}",
        },
        "intervention_history": {
            "actor_user_id": "ALTER TABLE intervention_history ADD COLUMN actor_user_id INTEGER",
            "actor_role": "ALTER TABLE intervention_history ADD COLUMN actor_role VARCHAR(32)",
        },
    }

    index_ddl: list[str] = []
    if inspector.has_table("students"):
        index_ddl.append("CREATE INDEX IF NOT EXISTS ix_students_is_archived ON students (is_archived)")
    if inspector.has_table("interventions"):
        index_ddl.extend(
            [
                "CREATE INDEX IF NOT EXISTS ix_interventions_prediction_id ON interventions (prediction_id)",
                "CREATE INDEX IF NOT EXISTS ix_interventions_priority ON interventions (priority)",
                "CREATE INDEX IF NOT EXISTS ix_interventions_status ON interventions (status)",
                "CREATE INDEX IF NOT EXISTS ix_interventions_assigned_to ON interventions (assigned_to)",
                "CREATE INDEX IF NOT EXISTS ix_interventions_follow_up_date ON interventions (follow_up_date)",
                "CREATE INDEX IF NOT EXISTS ix_interventions_is_demo ON interventions (is_demo)",
                "CREATE INDEX IF NOT EXISTS ix_interventions_is_archived ON interventions (is_archived)",
                "CREATE INDEX IF NOT EXISTS ix_interventions_created_at ON interventions (created_at)",
            ]
        )
    if inspector.has_table("predictions"):
        index_ddl.extend(
            [
                "CREATE INDEX IF NOT EXISTS ix_predictions_risk_level ON predictions (risk_level)",
                "CREATE INDEX IF NOT EXISTS ix_predictions_predicted_at ON predictions (predicted_at)",
            ]
        )
    if inspector.has_table("intervention_history"):
        index_ddl.append(
            "CREATE INDEX IF NOT EXISTS ix_intervention_history_actor_user_id ON intervention_history (actor_user_id)"
        )

    with target_engine.begin() as conn:
        for table_name, columns_map in table_column_ddl.items():
            if not inspector.has_table(table_name):
                continue
            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
            for col_name, ddl in columns_map.items():
                if col_name not in existing_cols:
                    conn.execute(text(ddl))

        for ddl in index_ddl:
            conn.execute(text(ddl))

        if inspector.has_table("intervention_history"):
            if dialect == "sqlite":
                conn.execute(
                    text(
                        "CREATE TRIGGER IF NOT EXISTS trg_intervention_history_no_delete "
                        "BEFORE DELETE ON intervention_history "
                        "BEGIN "
                        "SELECT RAISE(ABORT, 'Audit history records are append-only and cannot be deleted.'); "
                        "END;"
                    )
                )
                conn.execute(
                    text(
                        "CREATE TRIGGER IF NOT EXISTS trg_intervention_history_no_update "
                        "BEFORE UPDATE ON intervention_history "
                        "BEGIN "
                        "SELECT RAISE(ABORT, 'Audit history records are immutable and cannot be modified.'); "
                        "END;"
                    )
                )
            elif dialect == "postgresql":
                conn.execute(
                    text(
                        """
                        CREATE OR REPLACE FUNCTION ps3_protect_intervention_history()
                        RETURNS trigger AS $$
                        BEGIN
                            RAISE EXCEPTION 'Audit history records are immutable and append-only.';
                        END;
                        $$ LANGUAGE plpgsql;
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_trigger WHERE tgname = 'trg_intervention_history_immutable'
                            ) THEN
                                CREATE TRIGGER trg_intervention_history_immutable
                                BEFORE UPDATE OR DELETE ON intervention_history
                                FOR EACH ROW EXECUTE FUNCTION ps3_protect_intervention_history();
                            END IF;
                        END $$;
                        """
                    )
                )


def init_db(target_engine: Engine | None = None) -> None:
    """Create all database tables and apply safe additive Phase 4 migrations."""
    # Import ORM models so they are registered with Base.metadata before create_all.
    import models.db_models  # noqa: F401

    active_engine = target_engine or engine
    Base.metadata.create_all(bind=active_engine)
    apply_additive_migrations(active_engine)


def check_db_connection(db: Session) -> bool:
    """Run a lightweight connectivity check against the active database."""
    db.execute(text("SELECT 1"))
    return True


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

