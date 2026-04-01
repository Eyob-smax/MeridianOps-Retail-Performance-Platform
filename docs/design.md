# MeridianOps Architecture (Current Delivery Snapshot)

## 1) Scope in this delivery

This increment covers foundation plus major operational domains now wired end-to-end:

- Prompt 1: project bootstrap and runtime baseline
- Prompt 2: local authentication, lockout, RBAC, masking baseline
- Prompt 3: members, loyalty points, wallet, and audit trail
- Prompt 4: campaign CRUD, coupon issuance, and redemption rule enforcement
- Prompt 5: inventory receiving/transfers/counting/reservations with append-only ledger
- Prompt 6: training topic/question/assignment/review queue/attempt stats and trend APIs
- Prompt 7: attendance check-in/check-out with device binding, rotating QR, make-up approvals, payroll export
- Prompt 8 (partial): analytics dashboards, exports, and read-only share links integrated in backend and frontend

Remaining gaps are concentrated in deeper hardening and full traceability coverage across all original requirements.

## 2) Local runtime topology

- Frontend: Vue SPA (`fullstack/frontend`)
- Backend: FastAPI (`fullstack/backend`)
- Persistence: PostgreSQL as system of record (SQLite used only in isolated tests)
- Operation model: local on-prem only, no external cloud dependencies for core behavior

## 3) Backend architecture

### 3.1 Layering

- `app/api`: transport/API endpoints and role enforcement points
- `app/services`: transactional business logic
- `app/db/models`: SQLAlchemy entities
- `app/schemas`: Pydantic request/response DTOs
- `app/core`: config, security, masking, encryption abstraction
- `alembic`: migration history

### 3.2 Security and auth

- Username/password login with bcrypt verification
- Password minimum length enforced at config + API level
- Failed auth attempts persisted in `auth_attempts`
- Lockout windows in `lockout_windows` after 5 failed attempts within configured window
- Session cookies (`meridianops_session`) backed by `sessions` table
- RBAC dependencies for roles:
  - administrator
  - store_manager
  - inventory_clerk
  - cashier
  - employee

### 3.3 Data model additions

Core entities added:

- Loyalty:
  - `members`
  - `points_ledger`
  - `wallet_accounts`
  - `wallet_ledger`
- Campaign lifecycle:
  - `campaigns`
  - `coupons`
  - `coupon_issuance_events`
  - `coupon_redemption_events`
- Cross-cutting:
  - `audit_log`
- Inventory and training:
  - `inventory_items`
  - `inventory_locations`
  - `inventory_documents`
  - `inventory_document_lines`
  - `inventory_ledger`
  - `inventory_reservations`
  - `quiz_topics`
  - `quiz_questions`
  - `quiz_assignments`
  - `spaced_repetition_state`
  - `quiz_attempts`
  - `review_queue_snapshots`
- Analytics and scheduler:
  - `dashboard_layouts`
  - `dashboard_share_links`
  - `kpi_job_runs`
  - `kpi_daily_metrics`
- Attendance:
  - `attendance_rule_configs`
  - `device_bindings`
  - `rotating_qr_tokens`
  - `attendance_shifts`
  - `attendance_daily_results`
  - `attendance_makeup_requests`

Migration sequence:

- `20260326_0001` baseline heartbeat table
- `20260326_0002` auth/session tables
- `20260326_0003` loyalty + campaigns + audit tables
- `20260326_0004` inventory + training tables
- `20260326_0005` analytics dashboard + share link tables
- `20260326_0006` KPI scheduler/materialized tables
- `20260327_0007` attendance + anti-fraud tables

### 3.4 Transaction and integrity rules

- Points accrual uses deterministic `floor(pre_tax_amount)` rule.
- Wallet credit/debit mutations lock account row (`SELECT ... FOR UPDATE`) before balance updates.
- Insufficient wallet debit is rejected atomically.
- Coupon redemption locks coupon row to prevent double redemption.
- Redemption checks enforce:
  - campaign active range
  - daily campaign cap
  - per-member daily limit
  - assignment/member compatibility
  - full-reduction threshold checks
- Redemption idempotency supported for successful replay of same `coupon + order_reference`.

### 3.5 Audit and sensitive data handling

- Loyalty and coupon actions emit audit events with actor/resource metadata.
- Sensitive keys in audit payload are masked by default.
- Optional field encryption abstraction (`FieldEncryptor`) is available for PII/wallet fields rollout.

## 4) Frontend architecture

### 4.1 App shell and auth

- Login flow integrated with backend session endpoints.
- Route guards enforce auth and role checks.
- Navigation is role-scoped from centralized route metadata and nav config.

### 4.2 Implemented UI delivery

- Members page supports cashier/manager lookup.
- Displays tier, points balance, wallet balance.
- Supports points accrual and wallet credit/debit actions.
- Shows points and wallet ledger entries.
- Campaign management page supports campaign creation and listing.
- Campaign detail/new pages are wired to campaign endpoints.
- Coupon issuance UI supports account assignment and printable QR payload mode.
- Checkout page supports coupon redemption and explicit reason-code feedback.
- Inventory receiving/transfer/count pages are connected to live inventory endpoints.
- Training management/review pages are connected to live training endpoints.
- Attendance and make-up request pages are connected to live attendance endpoints.
- Analytics listing and builder pages are connected to dashboard APIs.
- Admin security page is connected to auth policy + attendance rule endpoints.

## 5) Test strategy status

Implemented tests cover:

- auth login/session/logout behavior
- lockout after repeated failures
- RBAC denial/allow matrix
- masking + encryption helpers
- member points and wallet behavior
- campaign issuance/redeem flows including threshold and limit checks
- inventory receiving/transfer/reservation/count integrity
- training assignment/review/attempt/stats/trends flow
- attendance check-in/check-out/make-up approval/payroll export flow
- KPI scheduler/backfill/permissions and masking export checks

Notes for this environment:

- Dependency installation was interrupted by user action; full `pytest` execution currently fails before runtime due to missing local packages (`bcrypt`, `psycopg`).
- Source compiles successfully with `python -m compileall app`.

## 6) Operational defaults and bootstrap notes

- Seed users are created on first login if absent:
  - `admin`, `manager`, `clerk`, `cashier`, `employee`
- Default seed password: `ChangeMeNow123` (local development only)
- Campaign defaults:
  - daily redemption cap `200`
  - per-member daily limit `1`

## 7) Known gaps (remaining hardening)

- Additional API/UI depth for full real-world attendance policies (advanced shift templates, multi-store policy overrides)
- Dashboard visual builder UX polish and richer widget-level interaction behavior
- Final requirement-by-requirement traceability matrix with exhaustive evidence links
- Expanded frontend component-level tests for critical user journeys beyond service-layer tests
