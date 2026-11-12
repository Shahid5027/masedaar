"""Isolated ephemeral backend server for Playwright Phase 5 E2E verification."""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

TEMP_DIR = Path(tempfile.mkdtemp(prefix="ps3_e2e_"))
DB_PATH = TEMP_DIR / "ps3_e2e.db"
MODELS_DIR = TEMP_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def _cleanup() -> None:
    shutil.rmtree(TEMP_DIR, ignore_errors=True)


atexit.register(_cleanup)

# Configure isolated test environment before importing app/settings.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
os.environ["MODEL_ARTIFACTS_DIR"] = str(MODELS_DIR)
os.environ["CORS_ORIGINS"] = "http://127.0.0.1:3015,http://localhost:3015"
os.environ["COOKIE_SECURE"] = "false"
os.environ["NOTIFICATION_EMAIL_TRANSPORT"] = "memory_test"
os.environ["AUTO_SEED_SYNTHETIC_DEMO"] = "false"

PS3_ROOT = Path(__file__).resolve().parents[1]
if str(PS3_ROOT) not in sys.path:
    sys.path.insert(0, str(PS3_ROOT))

import uvicorn  # noqa: E402
from database import SessionLocal, init_db  # noqa: E402
from main import app  # noqa: E402
from models.schemas import PredictionRunRequest, TrainModelRequest, UserCreateRequest  # noqa: E402
from services.auth_service import create_user_account  # noqa: E402
from services.ml_pipeline import train_and_register_model  # noqa: E402
from services.prediction_service import run_predictions  # noqa: E402
from services.synthetic_data import seed_synthetic_demo_data  # noqa: E402


def seed_e2e_state() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_synthetic_demo_data(db=db, num_records=200, seed=42)
        train_and_register_model(
            db=db,
            request=TrainModelRequest(
                dataset_mode="synthetic_only", allow_synthetic_fallback=True
            ),
        )
        run_predictions(
            db=db,
            request=PredictionRunRequest(include_synthetic=True, persist_interventions=True),
        )
        for username, email, full_name, role, password in [
            (
                "admin.e2e",
                "admin.e2e@university.edu",
                "E2E Administrator",
                "administrator",
                "AdminPass123!",
            ),
            (
                "counsellor.e2e",
                "counsellor.e2e@university.edu",
                "E2E Counsellor",
                "counsellor",
                "CounsellorPass123!",
            ),
            (
                "viewer.e2e",
                "viewer.e2e@university.edu",
                "E2E Viewer",
                "viewer",
                "ViewerPass123!",
            ),
        ]:
            create_user_account(
                db=db,
                request=UserCreateRequest(
                    username=username,
                    email=email,
                    full_name=full_name,
                    role=role,
                    password=password,
                    is_active=True,
                ),
                actor=None,
                ip_address="e2e-seed",
            )
    finally:
        db.close()


if __name__ == "__main__":
    seed_e2e_state()
    uvicorn.run(app, host="127.0.0.1", port=8015, log_level="warning")

