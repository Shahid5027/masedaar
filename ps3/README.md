# EDUCORE AI — PS3: Early Dropout Prediction & Student Retention Copilot (Phases 1 & 2)

Production-structured FastAPI backend for **PS3** inside the EDUCORE AI repository (`ps3/`). Includes Phase 1 database integration, strict CSV ingestion & validation, and synthetic dataset generation, plus Phase 2 Scikit-learn Random Forest training, stratified evaluation, configurable risk scoring, transparent explainability, and auditable intervention recommendations.

---

## Folder Structure

```text
ps3/
├── .env.example                  # Environment variable template
├── .gitignore
├── README.md
├── requirements.txt
├── pytest.ini
├── main.py                       # FastAPI app, lifespan, error handlers, /api/ps3 routing
├── config.py                     # Pydantic Settings configuration
├── database.py                   # SQLAlchemy engine & session lifecycle
├── models/
│   ├── __init__.py
│   ├── db_models.py              # students, ingestion_batches, activity_snapshots, training_targets, predictions, interventions, trained_models
│   └── schemas.py                # Pydantic schemas & consistent APIResponse envelope
├── services/
│   ├── __init__.py
│   ├── constants.py              # Feature columns, training target constant, domain bounds & disclaimers
│   ├── response.py               # Consistent JSON success/error response helpers
│   ├── csv_validator.py          # Pandas CSV parser & strict row/column validator
│   ├── data_service.py           # Atomic DB ingestion, summary stats, student queries
│   ├── synthetic_data.py         # Reproducible >=200 synthetic demo student generator & seeder
│   ├── ml_pipeline.py            # Scikit-learn imputer + RandomForest pipeline, evaluation & joblib persistence
│   ├── explainer.py              # SHAP (if available) or labeled rule-based indicator explanations
│   ├── recommender.py            # Auditable rule-based advisory intervention engine
│   └── prediction_service.py     # Risk classification, prediction persistence & explanation queries
├── routes/
│   ├── __init__.py
│   ├── health.py                 # GET  /api/ps3/health
│   ├── data.py                   # POST /api/ps3/data/validate, /upload, /seed-synthetic & GET /summary
│   ├── students.py               # GET  /api/ps3/students, /{student_id}, /{student_id}/explanation
│   ├── ml.py                     # POST /api/ps3/model/train & GET /api/ps3/model/metrics
│   └── predictions.py            # POST /api/ps3/predictions/run & GET /api/ps3/predictions
├── data/
│   └── synthetic_demo_students.csv
└── tests/
    ├── conftest.py
    ├── test_validation.py
    ├── test_upload_summary.py
    ├── test_students.py
    ├── test_synthetic_data.py
    ├── test_ml_pipeline.py
    ├── test_xai_and_recommendations.py
    └── test_predictions_api.py
```

---

## Feature & Identity Design

- **Shared Student Identity**: Preserves institutional `student_id` as the canonical primary/foreign key across all tables (`students`, `activity_snapshots`, `training_targets`, `predictions`, `interventions`). No separate identity/auth system is created.
- **Required Input Features (8 columns)**:
  1. `student_id` (unique non-empty string per CSV, max 64 chars)
  2. `attendance_rate` (float, `0.0` to `100.0`)
  3. `average_grade` (float, `0.0` to `100.0`)
  4. `late_assignments` (integer `>= 0`)
  5. `missing_assignments` (integer `>= 0`)
  6. `lms_logins_30d` (integer `>= 0`)
  7. `engagement_change_pct` (float, `-100.0` to `1000.0`)
  8. `previous_failure_count` (integer `>= 0`)
- **Training-Only Target Isolation**: `dropout_label` (`0` or `1`) is optional during CSV ingestion and is stored strictly in the separate `training_targets` table—never stored on `activity_snapshots` or returned in student inference feature payloads.
- **Synthetic Data Labeling**: Synthetic demo records use `SYNTH-STU-XXXX` IDs, `is_synthetic=true`, `data_source="synthetic_demo"`, and trigger `contains_synthetic_data: true` + `synthetic_notice` in API responses.

---

## Setup Instructions

### 1. Navigate to `ps3/`

```powershell
cd ps3
```

### 2. Create and Activate a Virtual Environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env`:

```powershell
Copy-Item .env.example .env
```

For **Supabase / PostgreSQL**, update `DATABASE_URL` in `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres?sslmode=require
```

For quick local development without a PostgreSQL server, leave the default SQLite URL (`sqlite:///./educore_ps3.db`).

---

## Synthetic Demo Dataset (>= 200 Records)

Generate the clearly labeled 250-record synthetic dataset CSV (`data/synthetic_demo_students.csv`):

```powershell
python -m services.synthetic_data --rows 250 --output data/synthetic_demo_students.csv
```

To generate **and** seed those clearly labeled synthetic records into your configured database:

```powershell
python -m services.synthetic_data --rows 250 --seed-db
```

---

## Run the Backend API Server

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI docs: `http://127.0.0.1:8000/docs`

### Endpoints (mounted under `/api/ps3`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/ps3/health` | Service and database connectivity check |
| `POST` | `/api/ps3/data/validate` | Dry-run CSV validation (returns structured row/column errors) |
| `POST` | `/api/ps3/data/upload` | Atomic CSV validation + database ingestion (`?is_synthetic=true` optional) |
| `POST` | `/api/ps3/data/seed-synthetic` | Explicitly generate & ingest `>=200` labeled synthetic demo records |
| `GET` | `/api/ps3/data/summary` | Real DB counts, Pandas/NumPy feature stats, training target distribution |
| `GET` | `/api/ps3/students` | Paginated, filterable, sortable student list with latest features |
| `GET` | `/api/ps3/students/{student_id}` | Student profile, snapshot history, real predictions, and interventions |
| `POST` | `/api/ps3/model/train` | Train Random Forest pipeline (`auto`, `real_only`, or `synthetic_only`) |
| `GET` | `/api/ps3/model/metrics` | Retrieve stored evaluation metrics, confusion matrix, and thresholds |
| `POST` | `/api/ps3/predictions/run` | Score students' latest snapshots, classify risk, explain, and persist recommendations |
| `GET` | `/api/ps3/predictions` | Query stored predictions with filters (`risk_level`, `student_id`, `is_demo`) |
| `GET` | `/api/ps3/students/{student_id}/explanation` | Retrieve student risk score, contributing indicators, and advisory interventions |

---

## Phase 2 Machine Learning Architecture

1. **Feature Isolation & Leakage Prevention**:
   - Trains strictly on the 7 numeric features (`attendance_rate`, `average_grade`, `late_assignments`, `missing_assignments`, `lms_logins_30d`, `engagement_change_pct`, `previous_failure_count`) paired with `dropout_label` (`0`/`1`) from `training_targets`.
   - Performs stratified `train_test_split` **before** fitting preprocessing (`SimpleImputer(strategy="median")`) or `RandomForestClassifier(class_weight="balanced")`.
   - When no approved real labeled dataset meets minimum sample & class criteria (`MIN_TRAINING_SAMPLES=20` with both classes `0` and `1`), `dataset_mode="auto"` falls back to the clearly labeled synthetic dataset and sets `is_demo_model=true`.
2. **Artifact Persistence**:
   - Saves serialized Scikit-learn `Pipeline` bundles to `MODEL_ARTIFACTS_DIR` (`artifacts/models/<model_version>.joblib`) and records metadata + evaluation metrics in the `trained_models` table.
3. **Configurable Risk Classification**:
   - Maps probabilities in `[0.0, 1.0]` using configurable thresholds (`RISK_THRESHOLD_MEDIUM=0.35`, `RISK_THRESHOLD_HIGH=0.70`, `THRESHOLD_PROFILE=demo_default` in `.env` / `config.py`):
     - `low`: `< RISK_THRESHOLD_MEDIUM`
     - `medium`: `RISK_THRESHOLD_MEDIUM <= p < RISK_THRESHOLD_HIGH`
     - `high`: `>= RISK_THRESHOLD_HIGH`
4. **Explainable AI & Non-Causal Safeguards**:
   - Uses SHAP `TreeExplainer` when the optional `shap` package is available and stable; otherwise uses transparent rule-based domain indicators weighted by model `feature_importances_` and explicitly labels them as **rule-based contributing indicators, not SHAP explanations**.
   - Every explanation carries an explicit disclaimer that statistical associations and threshold comparisons **do not prove causation**.
5. **Auditable Intervention Recommendations (Human Review Only)**:
   - Rule-based suggestions (`faculty_check_in`, `assignment_planning`, `subject_tutoring`, `time_management_coaching`, `access_and_engagement_check`, `academic_advising`, `counselor_review`, or `routine_monitoring`) are stored in `interventions` with `status="pending_review"` as advisory recommendations for human counselors/faculty—never automatic institutional decisions.

### Training & Prediction Workflow (Commands)

Start the server (`uvicorn main:app --host 127.0.0.1 --port 8000 --reload`), then run:

1. **Train the model (uses real DB labels if available, else synthetic demo fallback):**
   ```powershell
   Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/ps3/model/train" -ContentType "application/json" -Body '{"dataset_mode":"auto"}'
   ```
2. **Inspect evaluation metrics (accuracy, precision, recall, F1, ROC-AUC, confusion matrix):**
   ```powershell
   Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/ps3/model/metrics"
   ```
3. **Run predictions across students and persist risk tiers, explanations & recommendations:**
   ```powershell
   Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/ps3/predictions/run" -ContentType "application/json" -Body '{"include_synthetic":true,"persist_interventions":true}'
   ```
4. **List predictions or inspect a single student's explanation:**
   ```powershell
   Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/ps3/predictions?risk_level=high"
   Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/ps3/students/SYNTH-STU-0001/explanation"
   ```

### Demo-Data Limitations

- Models trained with `training_source="synthetic_demo_database"` or `"synthetic_demo_csv"` carry `is_demo_model=true`, `is_demo=true` on predictions, and an explicit evaluation disclaimer: synthetic-data metrics are demonstration results only and do **not** reflect real-world institutional accuracy or calibration.
- Always validate and calibrate thresholds on approved institutional labeled cohorts (`dataset_mode="real_only"`) before operational academic advising use.

### Consistent JSON Response Structure

Every endpoint (success or error) returns:

```json
{
  "status": "success | error",
  "message": "Human-readable summary",
  "data": { },
  "errors": [
    {
      "code": "ERROR_CODE",
      "message": "Detailed error description",
      "row": 2,
      "csv_line": 3,
      "column": "attendance_rate",
      "value": "115.0",
      "student_id": "STU-1002"
    }
  ],
  "meta": {
    "module": "ps3",
    "api_version": "1.0.0",
    "timestamp": "2026-11-12T05:20:00Z",
    "contains_synthetic_data": false,
    "synthetic_notice": null
  }
}
```

---

## Phase 3: Frontend Dashboard (`frontend/`)

The Phase 3 frontend (`ps3/frontend/`) is a responsive **Next.js 14 (App Router) + TypeScript + Tailwind CSS + Recharts + Lucide** early-warning dashboard integrated directly with the `/api/ps3/*` backend.

### Frontend Routes

| Route | Purpose |
| :--- | :--- |
| `/` | Overview Dashboard: cohort KPIs, quick "Run Predictions" trigger, risk distribution charts, cohort feature means/medians, model snapshot, students requiring attention, and ingestion totals |
| `/data` | Data Management: drag-and-drop CSV upload, non-mutating dry-run validation (`POST /data/validate`), CSV ingestion (`POST /data/upload`), `DEMO ONLY` synthetic seeding (`POST /data/seed-synthetic`), and live summary |
| `/students` | Student Risk Analysis: search by `student_id`, filter by risk tier and real vs synthetic source, sort by risk probability or academic indicators, and paginated directory |
| `/students/[studentId]` | Student Profile & Explainability: feature history, prediction history, risk probability, rule-based vs SHAP method indicator, risk-increasing vs protective factors, non-causation notice, and human-reviewed recommendations |
| `/model` | Model Analytics: Accuracy, Precision, Recall, F1, ROC-AUC (with fallback notes), Random Forest feature importance chart, holdout confusion matrix, class distribution, and guarded model training dialog (`POST /model/train`) |
| `/interventions` | Interventions Management Workspace: full case lifecycle (create, assign counsellor, transition status, schedule follow-up, record notes, reopen), status KPIs, paginated directory, and chronological audit history |

### Running the Full Stack Locally

1. **Start the FastAPI Backend** (from `ps3/`):
   ```powershell
   .\.venv\Scripts\Activate.ps1
   uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```
2. **Configure Frontend Environment** (from `ps3/frontend/`):
   Copy `.env.example` to `.env.local` if customizing the API URL (defaults to `http://127.0.0.1:8000`):
   ```powershell
   Copy-Item .env.example .env.local
   ```
3. **Install & Run Next.js** (from `ps3/frontend/`):
   ```powershell
   npm install
   npm run dev
   ```
   Open `http://127.0.0.1:3000`.

> **Windows Note:** If Node.js is installed in a non-global portable folder (e.g. `%LOCALAPPDATA%\nodejs\node-v22.14.0-win-x64`), add it to `PATH` in PowerShell before running `npm` commands.

### Frontend Verification Commands (from `ps3/frontend/`)

```powershell
npm run typecheck
npm run lint
npm test
npm run build
```

---

## Phase 4: Persistent Intervention Management, Scalable Pagination & Deployment Readiness

### Intervention Workflow Endpoints (`/api/ps3`)

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/interventions` | `GET` | Paginated (`page`/`page_size` or `limit`/`offset`) intervention directory with `status`, `priority`, `assigned_to`, `student_id`, `is_demo`, `search`, `overdue_only` filters, sorting, and real DB `status_counts` |
| `/interventions` | `POST` | Create a human-reviewed intervention linked to a valid `student_id` (and optional `prediction_id`), with duplicate active-case guard (`409`) and `INTERVENTION_CREATED` audit logging |
| `/interventions/{intervention_id}` | `GET` | Fetch full intervention detail, linked prediction, `allowed_next_statuses`, and chronological audit `history` |
| `/interventions/{intervention_id}` | `PATCH` | Transactional update of `assigned_to`, `status`, `priority`, `follow_up_date`, `recommended_action`, and `notes`; validates status state transitions (`422`) and records field-level audit events |
| `/interventions/{intervention_id}/history` | `GET` | Retrieve chronological lifecycle history (`INTERVENTION_CREATED`, `COUNSELLOR_ASSIGNED`, `STATUS_CHANGED`, `FOLLOW_UP_SCHEDULED`, `NOTES_UPDATED`, `INTERVENTION_COMPLETED`, `INTERVENTION_REOPENED`) |
| `/students/{student_id}/interventions` | `GET` | List all active and historical interventions for a shared `student_id` |

### Scalable Cohort Pagination & Combined Filtering

- `GET /api/ps3/data/summary` now computes full-cohort `latest_risk_distribution` (`low`, `medium`, `high`, `scored_students`, `unscored_students`) in SQL across cohorts of any size (>500 students supported).
- `GET /api/ps3/students` joins the latest `ActivitySnapshot` and latest `Prediction` in SQL and supports `page`, `page_size`, `total_pages`, `has_next`, `has_previous`, `search`, `risk_level` (`low`/`medium`/`high`/`unscored`), `is_synthetic`, `min_attendance`, `max_attendance`, `predicted_from`, `predicted_to`, and `sort_by=risk_score|predicted_at|...`.

### Database Migration & Deployment Checklist

1. **Database & Safe Additive Migrations:** Startup calls `init_db()` (`database.py`), which runs `Base.metadata.create_all()` followed by idempotent `apply_additive_migrations()` to safely add new `interventions` columns (`priority`, `follow_up_date`, `completed_at`, `is_demo`) and indexes on existing SQLite or PostgreSQL/Supabase databases without dropping existing rows.
2. **Environment Configuration:**
   - Backend (`ps3/.env`, modeled from `ps3/.env.example`): `DATABASE_URL`, `MODEL_ARTIFACTS_DIR`, `CORS_ORIGINS`, `RISK_THRESHOLD_MEDIUM`, `RISK_THRESHOLD_HIGH`, `LOG_LEVEL`, `MAX_UPLOAD_MB`. Never commit real credentials or secrets.
   - Frontend (`ps3/frontend/.env.local`, modeled from `ps3/frontend/.env.example`): `NEXT_PUBLIC_API_BASE_URL` pointing to the deployed FastAPI origin.
3. **Production Startup Commands:**
   - **Backend (from `ps3/`):** `uvicorn main:app --host 0.0.0.0 --port 8000`
   - **Frontend (from `ps3/frontend/`):** `npm run build && npm run start -- -H 0.0.0.0 -p 3000`
4. **Authentication / RBAC Prerequisite Before External Exposure:** Current PS3 APIs do not enforce user authentication or role-based access control. Deploy only inside a trusted local/VPN network or add institutional OAuth2/JWT RBAC middleware protecting counsellor notes and write endpoints before public production launch.

---

## Phase 5: Security Hardening, Authentication, RBAC, Concurrency & Deployment Readiness

### 1. Authentication, Sessions & CSRF Protection
- **HttpOnly Server-Backed Sessions**: `POST /api/ps3/auth/login` verifies `scrypt` salted password hashes (`hashlib.scrypt`, constant-time `hmac.compare_digest`), stores an opaque hashed session token in `user_sessions`, and sets cookie `ps3_session` (`HttpOnly`, `SameSite=Lax|Strict|None`, `Secure` in production/TLS).
- **CSRF Double-Submit Protection**: All mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`, except `/auth/login`) validate `X-CSRF-Token` against cookie `ps3_csrf` and the active session's CSRF secret.
- **Brute-Force Rate Limiting & Audit Logging**: Login attempts are throttled per IP and account (`LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_MINUTES`) returning HTTP `429`, without leaking whether a username exists. Every authentication and denial event is recorded in `security_audit_logs`.
- **Lifecycle**: `POST /api/ps3/auth/refresh`, `POST /api/ps3/auth/logout` (revokes server session), and `GET /api/ps3/auth/me`.

### 2. Backend-Enforced Role-Based Access Control (RBAC)
| Role | Permitted Scope |
| :--- | :--- |
| `administrator` | Full platform access: user/role management (`/users`, `/admin`), CSV ingestion & synthetic seeding (`/data/*`), model training (`/model/train`), batch scoring (`/predictions/run`), intervention management + soft-archive (`/interventions/{id}/archive`), notifications (`/notifications/*`), operational telemetry (`/ops/status`), and security audit logs (`/audit/security`). |
| `counsellor` | Student cohort, individual student profiles/explanations, and interventions assigned to them or unassigned (`/students/*`, `/interventions/*`); cannot reassign cases owned by another counsellor (`403`), upload data, train models, archive records, or view `/ops/status` & `/audit/security`. |
| `viewer` | Cohort-level summaries (`/data/summary`), model metrics (`/model/metrics`), and prediction summaries (`/predictions`) only; blocked (`403`) from individual student profiles, counsellor notes, interventions, notifications, ingestion, training, and admin workspaces. |

### 3. Initial Administrator Bootstrap (No Hardcoded Passwords)
No default admin password exists in source code or startup migrations. Provision an initial administrator using either:
- **CLI Script (recommended)**:
  ```powershell
  python scripts/create_admin.py --username admin.ops --email admin@university.edu --full-name "Operations Admin"
  ```
- **Startup Env Bootstrap (when `users` table is empty)**: Set `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_FULL_NAME`, and `BOOTSTRAP_ADMIN_PASSWORD` explicitly in `.env`.

### 4. Optimistic Concurrency, Tamper-Protected Audit History & Soft Archival
- Interventions carry an integer `version` column checked atomically in SQL (`UPDATE interventions ... WHERE id = :id AND version = :expected_version`), returning HTTP `409` (`INTERVENTION_VERSION_CONFLICT`) on stale concurrent edits.
- `intervention_history` is protected by SQLite (`trg_intervention_history_no_delete`, `trg_intervention_history_no_update`) and PostgreSQL (`ps3_protect_intervention_history`) triggers blocking deletes/updates, plus `ON DELETE RESTRICT` foreign keys.
- `POST /api/ps3/interventions/{id}/archive` soft-archives records (`is_archived=true`, `archived_at`) while retaining all audit history.

### 5. Automated Notifications & Email Transport
- Lifecycle triggers (`INTERVENTION_ASSIGNED`, `FOLLOW_UP_APPROACHING`, `FOLLOW_UP_OVERDUE`, `INTERVENTION_STATUS_CHANGED`, `INTERVENTION_COMPLETED`) generate deduplicated in-app alerts visible in the top-bar Alerts bell (`GET /api/ps3/notifications`) and email delivery logs.
- Email transport (`NOTIFICATION_EMAIL_TRANSPORT`) supports `disabled` (default local/dev), `memory_test` (deterministic verification transport without external SMTP), or `smtp` (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_TLS`). Notification emails omit raw counsellor notes to protect student privacy.

### 6. Production Deployment, PostgreSQL Migration, Backup & Rollback
- **Containers**: Use `ps3/Dockerfile` (FastAPI), `ps3/frontend/Dockerfile` (Next.js), `ps3/docker-compose.yml` (PostgreSQL 16 + backend + frontend), and `ps3/deploy/nginx.conf.example` (TLS termination, HTTPS redirect, HSTS, security headers).
- **Production Guards**: Setting `APP_ENV=production` automatically disables interactive `/docs` & `/redoc` (`DOCS_ENABLED=false`) and rejects wildcard `CORS_ORIGINS=*`.
- **PostgreSQL Migration & Rollback**:
  - Startup runs `init_db()` -> `Base.metadata.create_all()` + idempotent `apply_additive_migrations()` to safely add Phase 4/5 columns, indexes, and triggers without dropping existing data.
  - Before upgrading an existing PostgreSQL database, take a snapshot (`pg_dump --format=custom --file=backup_pre_phase5.dump "$DATABASE_URL"`). Roll back via `pg_restore --clean --if-exists -d "$DATABASE_URL" backup_pre_phase5.dump` alongside redeploying the prior container tag.
- **Dependency Audit Notes**: Frontend `npm audit` flags upstream `next@14.2.28` advisories resolved only via major Next.js upgrade (`next@16.x`); review before public internet exposure if institutional policy forbids Next 14.x.

---

## Run Verification Tests

### Backend Unit & Security Integration Suite (from `ps3/`)

```powershell
pytest
```

### Frontend Unit & Auth/RBAC Component Tests + Production Build (from `ps3/frontend/`)

```powershell
npm run typecheck
npm run lint
npm test
npm run build
```

### Browser End-to-End Suite (Playwright, from `ps3/frontend/`)

```powershell
npm run test:e2e
```


