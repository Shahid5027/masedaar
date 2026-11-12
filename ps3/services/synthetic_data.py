"""Reproducible synthetic student dataset generator and CLI seeder (clearly labeled)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from config import BASE_DIR
from database import SessionLocal, init_db
from models.schemas import UploadData
from services.constants import SYNTHETIC_DATA_SOURCE
from services.csv_validator import validate_csv_bytes
from services.data_service import ingest_validated_csv

DEFAULT_SYNTHETIC_CSV_PATH = BASE_DIR / "data" / "synthetic_demo_students.csv"
MIN_SYNTHETIC_RECORDS = 200


def generate_synthetic_dataframe(
    num_records: int = 250,
    seed: int = 42,
    enforce_minimum: bool = True,
) -> pd.DataFrame:
    """Generate >=200 realistic, clearly labeled synthetic student records.

    Cohort archetypes model realistic institutional dropout signals across attendance,
    grades, assignment completion, LMS logins, engagement shifts, and prior failures,
    plus a separated training-only `dropout_label` target.
    """
    if enforce_minimum and num_records < MIN_SYNTHETIC_RECORDS:
        raise ValueError(
            f"Synthetic dataset must contain at least {MIN_SYNTHETIC_RECORDS} records; got {num_records}."
        )
    if num_records <= 0:
        raise ValueError("num_records must be positive.")

    rng = np.random.default_rng(seed)

    # Archetypes: 0=thriving (42%), 1=steady (28%), 2=sudden_drop (16%), 3=chronic_risk (14%)
    archetypes = rng.choice([0, 1, 2, 3], size=num_records, p=[0.42, 0.28, 0.16, 0.14])

    rows = []
    for idx, cohort in enumerate(archetypes, start=1):
        student_id = f"SYNTH-STU-{idx:04d}"

        if cohort == 0:
            attendance = float(np.clip(rng.normal(92.0, 4.5), 78.0, 100.0))
            grade = float(np.clip(rng.normal(85.0, 7.0), 68.0, 99.5))
            late = int(np.clip(rng.poisson(0.7), 0, 4))
            missing = int(np.clip(rng.poisson(0.25), 0, 2))
            logins = int(np.clip(rng.normal(38.0, 10.0), 18, 70))
            engagement_delta = float(np.clip(rng.normal(6.5, 11.0), -18.0, 45.0))
            failures = int(rng.choice([0, 1], p=[0.95, 0.05]))
        elif cohort == 1:
            attendance = float(np.clip(rng.normal(79.0, 6.0), 62.0, 94.0))
            grade = float(np.clip(rng.normal(71.0, 7.5), 54.0, 88.0))
            late = int(np.clip(rng.poisson(2.1), 0, 7))
            missing = int(np.clip(rng.poisson(1.1), 0, 5))
            logins = int(np.clip(rng.normal(21.0, 6.5), 8, 42))
            engagement_delta = float(np.clip(rng.normal(-3.0, 12.0), -30.0, 30.0))
            failures = int(rng.choice([0, 1, 2], p=[0.70, 0.24, 0.06]))
        elif cohort == 2:
            attendance = float(np.clip(rng.normal(61.0, 9.0), 35.0, 82.0))
            grade = float(np.clip(rng.normal(60.0, 8.5), 38.0, 78.0))
            late = int(np.clip(rng.poisson(3.8), 1, 10))
            missing = int(np.clip(rng.poisson(3.4), 1, 9))
            logins = int(np.clip(rng.normal(9.5, 4.5), 1, 24))
            engagement_delta = float(np.clip(rng.normal(-46.0, 14.0), -85.0, -15.0))
            failures = int(rng.choice([0, 1, 2], p=[0.45, 0.38, 0.17]))
        else:
            attendance = float(np.clip(rng.normal(44.0, 11.0), 18.0, 68.0))
            grade = float(np.clip(rng.normal(43.0, 10.0), 18.0, 65.0))
            late = int(np.clip(rng.poisson(5.4), 1, 14))
            missing = int(np.clip(rng.poisson(5.8), 2, 14))
            logins = int(np.clip(rng.normal(4.5, 3.0), 0, 14))
            engagement_delta = float(np.clip(rng.normal(-60.0, 16.0), -95.0, -15.0))
            failures = int(np.clip(rng.poisson(2.2) + 1, 1, 6))

        # Realistic latent risk logit for training-only dropout_label
        logit = (
            1.65
            - 0.048 * (attendance - 70.0)
            - 0.045 * (grade - 62.0)
            + 0.16 * late
            + 0.34 * missing
            - 0.055 * logins
            - 0.028 * engagement_delta
            + 0.68 * failures
            + rng.normal(0.0, 0.45)
        )
        dropout_prob = 1.0 / (1.0 + np.exp(-logit))
        dropout_label = int(rng.random() < dropout_prob)

        rows.append(
            {
                "student_id": student_id,
                "attendance_rate": round(attendance, 2),
                "average_grade": round(grade, 2),
                "late_assignments": late,
                "missing_assignments": missing,
                "lms_logins_30d": logins,
                "engagement_change_pct": round(engagement_delta, 2),
                "previous_failure_count": failures,
                # Training-only target (separated from inference features during ingestion)
                "dropout_label": dropout_label,
                # Explicit synthetic dataset markers
                "is_synthetic": True,
                "data_source": SYNTHETIC_DATA_SOURCE,
            }
        )

    return pd.DataFrame(rows)


def generate_synthetic_csv_bytes(num_records: int = 250, seed: int = 42) -> Tuple[bytes, pd.DataFrame]:
    """Generate synthetic dataset and serialize to UTF-8 CSV bytes."""
    df = generate_synthetic_dataframe(num_records=num_records, seed=seed)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    return csv_bytes, df


def write_synthetic_csv(
    output_path: Optional[Path] = None,
    num_records: int = 250,
    seed: int = 42,
) -> Path:
    """Write the synthetic demo dataset CSV to disk."""
    target_path = output_path or DEFAULT_SYNTHETIC_CSV_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    csv_bytes, _ = generate_synthetic_csv_bytes(num_records=num_records, seed=seed)
    target_path.write_bytes(csv_bytes)
    return target_path


def seed_synthetic_demo_data(
    db: Session,
    num_records: int = 250,
    seed: int = 42,
    csv_path: Optional[Path] = None,
) -> UploadData:
    """Generate/save synthetic CSV and ingest it through the standard validator and DB service."""
    target_path = csv_path or DEFAULT_SYNTHETIC_CSV_PATH
    csv_bytes, _ = generate_synthetic_csv_bytes(num_records=num_records, seed=seed)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(csv_bytes)

    validation = validate_csv_bytes(
        raw_bytes=csv_bytes,
        filename=target_path.name,
        assume_synthetic=True,
    )
    return ingest_validated_csv(
        db=db,
        validation=validation,
        filename=target_path.name,
        force_synthetic=True,
    )


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate clearly labeled synthetic demo student records for EDUCORE AI PS3."
    )
    parser.add_argument("--rows", type=int, default=250, help="Number of synthetic records (>=200).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_SYNTHETIC_CSV_PATH,
        help="Destination CSV path.",
    )
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="Also validate and ingest the generated synthetic dataset into the configured database.",
    )
    args = parser.parse_args()

    out_path = write_synthetic_csv(output_path=args.output, num_records=args.rows, seed=args.seed)
    print(f"[SYNTHETIC_DEMO] Generated {args.rows} labeled synthetic records at: {out_path}")

    if args.seed_db:
        init_db()
        db = SessionLocal()
        try:
            result = seed_synthetic_demo_data(
                db=db,
                num_records=args.rows,
                seed=args.seed,
                csv_path=out_path,
            )
            print(
                f"[SYNTHETIC_DEMO] Seeded batch_id={result.batch_id}, "
                f"ingested_rows={result.ingested_rows}, "
                f"training_targets_stored={result.training_targets_stored}, "
                f"is_synthetic={result.is_synthetic}"
            )
        finally:
            db.close()


if __name__ == "__main__":
    _main()

