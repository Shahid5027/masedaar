# EDUCORE AI PS3 — Phase 5 Security & Deployment Audit

**Readiness Classification:** **READY FOR CONTROLLED STAGING**
*(Not yet cleared for unrestricted production launch — see Section 17: Live PostgreSQL verification blocked on missing DB/credentials, external SMTP unverified without mail relay credentials, and upstream `next@14.2.28` dependency advisories remain open.)*

---

## 1. Architecture Reviewed

PS3 retains its existing Phase 1–4 separation inside `ps3/` without altering PS1, PS2, or the Phase 2 Random Forest / Explainability ML pipeline:
- **Backend (`ps3/`)**: FastAPI + SQLAlchemy 2.x + Pydantic v2 + Scikit-learn + Pandas/NumPy mounted under `/api/ps3`.
  - Added security/auth/notification layer across `config.py`, `database.py`, `main.py`, `models/db_models.py`, `models/schemas.py`, `services/auth_service.py`, `services/notification_service.py`, `routes/auth.py`, `routes/users.py`, `routes/notifications.py`, `routes/ops.py`, and hardened all existing routers (`health.py`, `data.py`, `ml.py`, `predictions.py`, `students.py`, `interventions.py`).
- **Frontend (`ps3/frontend/`)**: Next.js 14.2.28 App Router + TypeScript + Tailwind CSS + Recharts.
  - Added cookie/CSRF transport (`src/lib/api.ts`), authentication & session-expiry context (`src/components/auth/AuthProvider.tsx`), RBAC route guards (`src/components/auth/RoleGuard.tsx`), `/login` page, `/admin` workspace, top-bar `NotificationsPanel`, optimistic concurrency conflict recovery UI in `/interventions`, and security headers in `next.config.mjs`.

---

## 2. Authentication Implementation

Implemented in `ps3/services/auth_service.py`, `ps3/routes/auth.py`, `ps3/frontend/src/lib/api.ts`, `ps3/frontend/src/components/auth/AuthProvider.tsx`, and `ps3/frontend/src/app/login/page.tsx`:
- **Password Hashing & Policy**: Standard-library `hashlib.scrypt` with random per-user cryptographic salt and constant-time `hmac.compare_digest` verification. Passwords require minimum length (`PASSWORD_MIN_LENGTH=10` default, configurable `>= 8`) and mixed character classes (`validate_password_strength`).
- **Bootstrap Without Hardcoded Credentials**: Zero default passwords exist in code or migrations. Initial admin provisioning uses either CLI `ps3/scripts/create_admin.py` (reads `--password-env` or interactive `getpass`) or explicit `BOOTSTRAP_ADMIN_PASSWORD` env var on an empty `users` table (`bootstrap_admin_if_configured`).
- **Opaque Server-Backed Cookie Sessions**: `POST /api/ps3/auth/login` creates a database row in `user_sessions` (storing SHA-256 hash of opaque session token, sliding `expires_at`, and hard ceiling `absolute_expires_at`), sets cookie `ps3_session` (`HttpOnly`, configurable `COOKIE_SECURE`, `COOKIE_SAMESITE=lax`), and pairs it with double-submit CSRF cookie `ps3_csrf`.
- **CSRF Double-Submit Enforcement**: Mutating endpoints (`POST`, `PUT`, `PATCH`, `DELETE`, excluding `/auth/login`) validate header `X-CSRF-Token` against cookie `ps3_csrf` and the active session record.
- **Brute-Force Rate Limiting & Non-Enumeration**: Per-IP and per-account rate limiting (`LOGIN_RATE_LIMIT_ATTEMPTS`, `LOGIN_RATE_LIMIT_WINDOW_MINUTES`) rejects excess attempts with HTTP `429`; failed logins return uniform HTTP `401` without revealing account existence.
- **Session Lifecycle**: `POST /api/ps3/auth/refresh`, `POST /api/ps3/auth/logout` (revokes server-side session & clears cookies), `GET /api/ps3/auth/me`, and frontend `401` expiry handler redirecting to `/login?reason=expired`.

---

## 3. Role-Based Authorization Matrix

Backend enforcement via `Depends(require_roles(...))` in `ps3/services/auth_service.py`; denied requests return HTTP `403` and log `ACCESS_DENIED` into `security_audit_logs`:

| Capability / Endpoint Group | `administrator` | `counsellor` | `viewer` | Unauthenticated |
| :--- | :---: | :---: | :---: | :---: |
| `GET /api/ps3/health` | Allowed | Allowed | Allowed | Allowed (minimal status) |
| `POST /api/ps3/auth/login` | Allowed | Allowed | Allowed | Allowed (rate-limited) |
| `GET /auth/me`, `POST /auth/refresh`, `POST /auth/logout` | Allowed | Allowed | Allowed | `401` |
| `GET /data/summary`, `GET /model/metrics`, `GET /predictions` | Allowed | Allowed | Allowed | `401` |
| `POST /data/validate`, `/data/upload`, `/data/seed-synthetic` | Allowed | `403` | `403` | `401` |
| `POST /model/train`, `POST /predictions/run` | Allowed | `403` | `403` | `401` |
| `GET /students`, `GET /students/{id}`, `/students/{id}/explanation`, `/students/{id}/interventions` | Allowed | Allowed | `403` | `401` |
| `GET/POST/PATCH /interventions*` | Allowed | Allowed (own or unassigned cases only; cross-counsellor reassignment returns `403`) | `403` | `401` |
| `POST /interventions/{id}/archive` | Allowed | `403` | `403` | `401` |
| `GET /notifications`, `PATCH /notifications/{id}/read`, `POST /notifications/scan-followups` | Allowed | Allowed (scoped to recipient) | `403` | `401` |
| `POST /notifications/{id}/retry` | Allowed | `403` | `403` | `401` |
| `GET/POST/PATCH /users*`, `GET /ops/status`, `GET /audit/security` | Allowed | `403` | `403` | `401` |

Frontend sidebar (`AppShell.tsx`), page actions (`/`, `/model`, `/students/[studentId]`, `/interventions`), and `RoleGuard` (`403 — Access Restricted`) mirror this backend matrix.

---

## 4. Database Changes

Updated `ps3/models/db_models.py`, `ps3/models/__init__.py`, and `ps3/database.py` (`apply_additive_migrations()`):
- **New Tables**:
  - `users` (`id`, `username`, `email`, `full_name`, `role`, `password_hash`, `is_active`, `last_login_at`, timestamps)
  - `user_sessions` (`id`, `user_id`, `token_hash`, `csrf_token`, `ip_address`, `user_agent`, `expires_at`, `absolute_expires_at`, `revoked_at`, `created_at`)
  - `security_audit_logs` (`id`, `actor_user_id`, `actor_username`, `actor_role`, `event_type`, `target_type`, `target_id`, `summary`, `details`, `ip_address`, `created_at`)
  - `notifications` (`id`, `recipient_user_id`, `recipient_username`, `intervention_id`, `student_id`, `event_type`, `channel`, `title`, `message`, `dedupe_key`, `email_status`, `email_attempts`, `last_error`, `is_read`, `read_at`, `created_at`, `sent_at`)
- **Modified Existing Tables (Additive & Non-Destructive)**:
  - `students`: added `is_archived`, `archived_at`.
  - `interventions`: added `version` (default `1`), `is_archived`, `archived_at`.
  - `intervention_history`: added `actor_user_id`, `actor_role`, tightened `intervention_id` FK to `ON DELETE RESTRICT`, removed ORM `delete-orphan` cascade.
- **Verified Legacy Migration**: Executed `init_db()` on a temporary copy of existing `educore_ps3.db`: all 12 tables and both append-only SQLite triggers were created while all `252` pre-existing student rows remained intact.

---

## 5. Audit-History Protection

- **Verified Server Actor Identity**: `intervention_service.py` derives `actor_id`, `actor_user_id`, and `actor_role` strictly from the authenticated `current_user` server dependency (`POST` / `PATCH` / `POST /archive`), ignoring forged client `actor_id` inputs.
- **Database Append-Only Enforcement**:
  - SQLite triggers installed in `database.py`: `trg_intervention_history_no_delete` and `trg_intervention_history_no_update` raise `ABORT` on any `DELETE` or `UPDATE` against `intervention_history`.
  - PostgreSQL trigger function `ps3_protect_intervention_history()` (`BEFORE UPDATE OR DELETE ON intervention_history`) written in `database.py`.
- **Soft Archival Retention**: `POST /api/ps3/interventions/{id}/archive` marks `is_archived=true` and `archived_at` while preserving historical `intervention_history` and writing an archival event. Verified in `test_optimistic_concurrency_and_audit_history_protection`.

---

## 6. PostgreSQL / Supabase Verification

- **Status: BLOCKED (No Live PostgreSQL/Supabase Instance or Credentials Available on Host)**
- This Windows environment has neither `psql`, `pg_isready`, nor `docker`, and neither `ps3/.env` nor `ps3/frontend/.env.local` exists with PostgreSQL/Supabase credentials.
- `psycopg2-binary==2.9.13` is installed, PostgreSQL `DO $$ ... $$` migration/trigger DDL and `docker-compose.yml` (`postgres:16-alpine`) were authored and reviewed in `ps3/database.py` and `ps3/docker-compose.yml`, **but live execution, trigger enforcement, connection pooling, and migration behavior against an actual PostgreSQL / Supabase server remain unverified**.

---

## 7. Concurrency Control

- **Optimistic Version Locking**: `Intervention.version` starts at `1` (`InterventionUpdateRequest` and `InterventionArchiveRequest` require `version: int >= 1`).
- **Atomic Conditional SQL Update**: `intervention_service.py` executes `UPDATE interventions SET ..., version = version + 1 WHERE id = :id AND version = :expected_version`. Zero affected rows triggers rollback and raises HTTP `409` (`INTERVENTION_VERSION_CONFLICT`).
- **Frontend Recovery**: `src/app/interventions/page.tsx` submits the loaded `version`, detects HTTP `409 INTERVENTION_VERSION_CONFLICT`, displays an explicit conflict alert, and provides a one-click **"Refresh Latest Version"** button. Verified in both backend integration tests and Vitest (`auth_rbac_notifications.test.tsx`).

---

## 8. Notification Implementation

Implemented in `ps3/services/notification_service.py`, `ps3/routes/notifications.py`, and `ps3/frontend/src/components/shared/NotificationsPanel.tsx`:
- **Supported Events**: `INTERVENTION_ASSIGNED`, `FOLLOW_UP_APPROACHING`, `FOLLOW_UP_OVERDUE`, `INTERVENTION_STATUS_CHANGED`, and `INTERVENTION_COMPLETED`.
- **Deduplication & Failure Isolation**: Unique `dedupe_key` prevents duplicate alerts across scans (`POST /api/ps3/notifications/scan-followups`); transport errors record `email_status="failed"` with `last_error` and support admin retry (`POST /api/ps3/notifications/{id}/retry`) without rolling back intervention mutations.
- **Controlled Transport Verification**: Tested in `test_notifications_controlled_transport_dedupe_retry_and_privacy` using `NOTIFICATION_EMAIL_TRANSPORT=memory_test`. External live SMTP delivery (`smtp` transport) has **not** been tested against a real mail server (blocked for lack of SMTP relay credentials).

---

## 9. Browser E2E Test Results

Configured in `ps3/frontend/playwright.config.ts` with isolated backend (`ps3/scripts/e2e_server.py` on `:8015` using ephemeral SQLite temp DB) and production `next start` frontend (`:3015`) running in headless Chrome (`channel: "chrome"`):
- File: `ps3/frontend/e2e/phase5.spec.ts`
- Result: **4 passed in 22.2s**:
  1. Unauthenticated `/` redirects to `/login`; invalid credentials show error alert cleanly.
  2. `viewer` RBAC restrictions enforced across sidebar links, hidden actions (`Run Predictions`, `Train Model`, `Notifications`), and direct route `403 — Access Restricted` blocks (`/data`, `/students`, `/interventions`, `/admin`), plus clean sign-out.
  3. `counsellor` workflow end-to-end: route block on `/admin`, student search (`SYNTH-STU-0001`), student profile & explanations view (without admin rescore action), intervention create -> assign -> `IN_PROGRESS` -> follow-up date -> notes -> save (`v2` + verified actor `counsellor.e2e (counsellor)` in audit timeline), top-bar Notifications bell + `Scan Due`, and expired-session redirect to `/login?reason=expired` after cookie clearing.
  4. `administrator` workflow end-to-end: `/admin` operational telemetry + user account creation (`counsellor.new`) + security audit log inspection (`LOGIN_SUCCESS`), case archival (`Archive Case`) in `/interventions`, and clean sign-out.

*(Note: Executed against the production `next build` + `next start` bundle prior to the two test-config-only adjustments in `vitest.config.ts` and `tests/components.test.tsx`; no runtime `src/` files changed afterwards.)*

---

## 10. Security Review Results

- **Production Docs & CORS**: `APP_ENV=production` disables Swagger/OpenAPI docs (`DOCS_ENABLED=false`) and rejects wildcard `CORS_ORIGINS=*`. `allow_methods` and `allow_headers` are explicitly allowlisted in `ps3/main.py`.
- **Upload Hardening**: `ps3/routes/data.py` enforces size cap (`MAX_UPLOAD_MB`), `.csv` extension check, and `Path(filename).name` path-traversal sanitization.
- **HTTP Security Headers**: FastAPI middleware (`ps3/main.py`) sets `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`, `Permissions-Policy`, `Cache-Control: no-store`, and conditional `Strict-Transport-Security` when `ENABLE_HSTS=true`. `ps3/frontend/next.config.mjs` sets `poweredByHeader: false` and CSP / framing / MIME / referrer / permissions headers, reinforced in `ps3/deploy/nginx.conf.example`.
- **Secret Hygiene**: Verified no `.env` or `frontend/.env.local` files exist in `ps3/`; only `educore_ps3.db` local dev SQLite DB and template `.env.example` files exist. No credentials or default passwords are embedded in source code.

---

## 11. Dependency Review

- **Python (`ps3/requirements.txt` / `.venv`)**: Verified installed versions include `fastapi==0.162.5`, `SQLAlchemy==2.1.8`, `pydantic==2.14.3`, `pydantic-settings==2.16.2`, `psycopg2-binary==2.9.13`, `scikit-learn==1.9.1`, `pandas==3.1.1`, `numpy==2.5.4`, `uvicorn==0.54.0`, `pytest==9.2.0`, `httpx==0.28.1`. Automated CVE scanning via `pip-audit` was not run (`pip` module not installed in `.venv`).
- **Node/Frontend (`ps3/frontend/package.json`)**: `npm audit` reported **14 vulnerabilities (7 moderate, 4 high, 3 critical)**:
  - `next@14.2.28` and transitive `postcss`: upstream Next.js advisories; remediation via `npm audit fix --force` requires a breaking major-version upgrade to `next@16.4.6`.
  - `tinypool <=2.1.1` (dev/test dependency via Vitest): critical prototype-pollution advisory; remediation requires breaking major upgrade to `vitest@5.1.0`.

---

## 12. Privacy Safeguards

- `viewer` accounts cannot access `/students*`, `/interventions*`, `/notifications*`, `/users*`, or `/audit/security` (`403`).
- `counsellor` accounts cannot view operational telemetry (`/ops/status`), platform security audit logs (`/audit/security`), or interventions reassigned to other staff (`403`).
- Notification alerts & email bodies omit raw counsellor notes (`notification_service.py` enforces body excludes private note text; verified by `test_notifications_controlled_transport_dedupe_retry_and_privacy`).
- Login failures never disclose whether a username/email exists.

---

## 13. Deployment Configuration

Added production deployment templates and instructions (updated `ps3/README.md`):
- `ps3/Dockerfile` (non-root Python 3.12 FastAPI container with healthcheck)
- `ps3/frontend/Dockerfile` (multi-stage non-root Node 22 Next.js container)
- `ps3/docker-compose.yml` (`postgres:16-alpine` + `backend` + `frontend` with healthchecks and named volumes)
- `ps3/deploy/nginx.conf.example` (TLS termination, HTTP->HTTPS redirect, HSTS, security headers, reverse proxy for `/api/ps3/` and `/`)
- `ps3/.env.example` and `ps3/frontend/.env.example` updated for Phase 5 auth/cookie/CSRF/SMTP settings
- `ps3/scripts/create_admin.py` for non-hardcoded CLI admin provisioning

---

## 14. Backend Test Results

Command: `.\.venv\Scripts\python.exe -m pytest` (run from `ps3/` after all backend edits)
- **Result: 36 passed, 1 warning in 89.82s** (0 failures, 0 skipped)
  - Existing Phase 1–4 suites (`31 tests` across validation, upload/summary, synthetic data, students, ML pipeline, XAI/recommendations, predictions, interventions lifecycle & legacy migration): **31 passed**
  - New Phase 5 security/auth/RBAC/concurrency/notifications/headers suite (`tests/test_phase5_security_auth_concurrency_notifications.py`): **5 passed**
- Legacy SQLite copy upgrade check (`educore_ps3.db`): **passed** (`12` tables, `2` append-only triggers, `252` students preserved).
- CLI admin bootstrap check (`scripts/create_admin.py`): **passed**.

---

## 15. Frontend Test Results

Command: `npm.cmd run typecheck && npm.cmd run lint && npm.cmd test` (run from `ps3/frontend/` after final edits)
- `tsc --noEmit`: **Passed (exit code 0)**
- `next lint`: **Passed (`No ESLint warnings or errors`)**
- `vitest run`: **Test Files 5 passed (5), Tests 20 passed (20) in 11.56s**
  - Existing tests (`apiClient.test.ts` 4, `services.test.ts` 5, `components.test.tsx` 3, `interventions.test.tsx` 3): **15 passed**
  - New Phase 5 auth/RBAC/notifications/409 concurrency tests (`auth_rbac_notifications.test.tsx`): **5 passed**

---

## 16. Production Build Result

Command: `npm.cmd run build` (run from `ps3/frontend/` with default API URL env after final edits)
- **Passed (exit code 0)**: compiled, type-checked, linted, and generated all 10 routes (`/`, `/_not-found`, `/admin`, `/data`, `/interventions`, `/login`, `/model`, `/students`, `/students/[studentId]`).

---

## 17. Remaining Blockers

Before moving beyond controlled staging into unrestricted institutional production:
1. **Live PostgreSQL / Supabase Verification (BLOCKER)**: Execute `init_db()` migrations, append-only triggers (`ps3_protect_intervention_history`), `scrypt` login/session persistence, and backup/restore (`pg_dump` / `pg_restore`) against a live PostgreSQL 16 / Supabase instance with TLS (`sslmode=require`).
2. **Live External SMTP Verification (BLOCKER for email alerts)**: Configure real institutional `SMTP_*` credentials and verify outbound TLS email delivery & failure retry behavior in staging.
3. **Frontend Next.js Security Advisories (BLOCKER if institutional policy forbids Next 14.2.28)**: Evaluate upgrading Next.js (`14.2.28 -> 16.x`) and Vitest/Tinypool dev dependencies reported by `npm audit` (14 advisories).
4. **Python `pip-audit` & Container Build Verification**: Run `pip-audit` in CI/staging and verify `docker compose up --build` + TLS Nginx termination in a Docker-enabled host.

---

## 18. Production Deployment Checklist

1. Provision PostgreSQL 16 / Supabase with `sslmode=require`; take a pre-upgrade `pg_dump` snapshot if migrating existing Phase 1–4 data.
2. Configure backend `.env` (`APP_ENV=production`, explicit `CORS_ORIGINS`, `COOKIE_SECURE=true`, `ENABLE_HSTS=true`, `DOCS_ENABLED=false`, `NOTIFICATION_EMAIL_TRANSPORT=smtp` + `SMTP_*`) and frontend `NEXT_PUBLIC_API_BASE_URL=/api/ps3`. Never store `.env` in Git.
3. Deploy behind TLS reverse proxy (`ps3/deploy/nginx.conf.example`) or `docker-compose.yml` + HTTPS load balancer.
4. Initialize database schema & triggers (`init_db()` at startup) and verify all tables + `ps3_protect_intervention_history` trigger exist in PostgreSQL.
5. Provision the initial administrator account via `python scripts/create_admin.py` (or temporary `BOOTSTRAP_ADMIN_*` env vars, then remove `BOOTSTRAP_ADMIN_PASSWORD` from runtime config).
6. Smoke-test login (`admin`, `counsellor`, `viewer`), RBAC `403` enforcement, notification delivery, `pg_restore` rollback drill, and monitor `/api/ps3/ops/status` and `/api/ps3/audit/security`.

