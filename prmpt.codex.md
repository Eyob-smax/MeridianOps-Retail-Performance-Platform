# MeridianOps Retail Performance Platform - Codex Execution Playbook

## How to use this file

- Run Prompt 1, wait until it is fully implemented and validated, then run Prompt 2, and so on.
- Do not skip prompts.
- Every prompt includes strict acceptance criteria. If criteria fail, Codex must fix gaps before moving forward.
- By the end of Prompt 10, the application must be fully functional end-to-end (frontend, backend, database, data flow, exports, scheduling, security, docs).

## Non-negotiable packaging and structure rules

Codex must enforce this exact output package shape for submission:

- Root Directory/
  - fullstack/ (all app source code only)
  - prompt.md (original prompt file)
  - trajectory.json (OpenAI trajectory format; if multiple sessions, use sessions/trajectory-1.json, trajectory-2.json, ...)
  - questions.md (required; requirements questions and assumptions)
  - docs/
    - design.md
    - api-spec.md
    - additional delivery docs if needed

Hard constraints:

- All runnable application code must stay inside fullstack/.
- Do not scatter code outside fullstack/.
- Keep docs and evidence files at root as defined above.
- Language: English-only UI.
- Runtime: local on-prem only (laptop/in-store server).
- No dependency on external cloud services for core functionality.

## Platform and architecture requirements

- Frontend: Vue.js SPA.
- Backend: FastAPI (REST-style endpoints, decoupled from frontend).
- Database: PostgreSQL as sole system of record.
- Security: local auth only; username/password; min 12 chars; bcrypt; lockout after 5 failures for 15 min.
- Roles:
  - Administrator
  - Store Manager
  - Inventory Clerk
  - Cashier
  - Employee

## Master business logic decomposition

### 1) Authentication and authorization

- Login with username/password only.
- Password policy: minimum 12 characters.
- Hashing via bcrypt.
- Failed login counter and temporary lockout policy.
- RBAC permission enforcement at API and UI layer.
- Data scope filtering in analytics and shared links by role.

### 2) Campaigns and coupon redemption

- Campaign types:
  - Percent-off
  - Fixed-amount coupon
  - Full-reduction offer (for example: $10 off $50)
- Rules:
  - Effective date range
  - Daily redemption cap (default 200)
  - Per-member limit (default 1 per day)
- Issuance methods:
  - Printable QR coupon
  - Account-based assignment
- Redemption at checkout through scanning.
- Clear feedback on eligibility, success/failure reasons.
- Full event traceability with operator identity and timestamp.

### 3) Member and loyalty

- Member tiers: Base, Silver, Gold.
- Points accrual: 1 point per $1 pre-tax, rounded down.
- Optional stored-value internal wallet.
- Cashier and manager can view balances and eligibility.
- Audit trail for loyalty and wallet changes.

### 4) Staff training and spaced repetition

- Supervisors create quizzes tied to products/policies.
- Per-employee daily review queue generated from spaced repetition.
- Topic weighting by difficulty.
- Explainable recommendations, example:
  - review in 3 days due to two recent misses.
- Performance outputs:
  - Hit rate
  - Trends over time

### 5) Inventory workflow and stock integrity

- Guided screens and workflows:
  - Inbound receiving
  - Outbound transfers
  - Stock counts
- Optional batch and expiration tracking.
- Reserved stock visibility for open orders.
- Inventory consistency model:
  - Append-only inventory ledger
  - Reservation creation/release via order lifecycle
  - DB transactions and row-level locking to prevent double-spend

### 6) Attendance and anti-fraud

- QR/NFC check-in and check-out.
- Optional GPS coordinate capture (no map required).
- Configurable tolerance default: +- 5 minutes.
- Anti-fraud:
  - Device binding
  - One-time QR rotating every 30s on local server screen
- Attendance calculations:
  - Cross-day shifts
  - Auto break deduction after 6h (default 30m)
  - Late/early penalty default 0.25h per incident beyond tolerance
- Make-up requests with manager approval notes.
- Payroll reconciliation export.

### 7) Dashboard and ad-hoc analytics

- Drag-and-drop dashboard layout.
- Linked filters and drill-down by store/date.
- Exports: PNG, PDF, CSV.
- Read-only links on local network.
- Scheduled local KPI materialization (example: daily 2:00 AM):
  - Conversion rate
  - Average order value
  - Inventory turnover

### 8) Local security and data protection

- Sensitive field masking by default in logs and exports.
- Optional at-rest encryption for stored-value and PII.
- Full local operation model.

## UI flow decomposition

### Global route map

- /login
- /app/home
- /app/campaigns
- /app/campaigns/new
- /app/campaigns/:id
- /app/checkout
- /app/members
- /app/training
- /app/training/review
- /app/inventory/receiving
- /app/inventory/transfers
- /app/inventory/counts
- /app/attendance/check
- /app/attendance/requests
- /app/analytics
- /app/analytics/builder
- /app/admin/security

### Primary role journeys

- Administrator:
  - Manage users, roles, policy settings, encryption/masking defaults.
- Store Manager:
  - Approve make-up requests, monitor campaigns, dashboards, and KPIs.
- Inventory Clerk:
  - Execute receiving/transfers/counts and resolve discrepancies.
- Cashier:
  - Lookup member, scan coupon, redeem, view clear validation feedback.
- Employee:
  - Do training review queue and attendance check in/out.

### UX interaction requirements

- Every critical form has:
  - Inline validation
  - Error state and retry action
  - Success confirmation with traceable event reference
- Data tables support:
  - Filter, sort, pagination
  - CSV export where relevant
- Accessibility basics:
  - Keyboard support for key operations
  - Focus state visibility
  - Readable contrast

## Database design decomposition

### Core schema groups

1. Identity and access

- users
- roles
- permissions
- user_roles
- role_permissions
- auth_attempts
- lockout_windows
- sessions

2. Organization

- regions
- stores
- user_store_scopes

3. Members and loyalty

- members
- member_tier_history
- points_ledger
- wallet_accounts
- wallet_ledger

4. Campaigns and coupons

- campaigns
- campaign_rules
- coupons
- coupon_assignments
- coupon_issuance_events
- coupon_redemption_events

5. Checkout and order context

- orders
- order_lines
- order_coupon_links
- checkout_events

6. Training

- quiz_topics
- quizzes
- quiz_questions
- quiz_options
- quiz_assignments
- quiz_attempts
- spaced_repetition_state
- review_queue_snapshots

7. Inventory

- inventory_items
- inventory_locations
- inventory_documents
- inventory_document_lines
- inventory_ledger (append-only)
- inventory_reservations
- stock_count_sessions
- stock_count_lines

8. Attendance

- attendance_events
- attendance_shifts
- attendance_rule_configs
- attendance_daily_results
- attendance_makeup_requests
- attendance_approvals
- device_bindings
- rotating_qr_tokens

9. Analytics and sharing

- kpi_daily_materialized
- dashboard_layouts
- dashboard_widgets
- dashboard_filter_links
- readonly_share_links
- export_jobs
- export_audit

10. Cross-cutting

- audit_log
- idempotency_keys
- scheduler_job_runs

### Data integrity rules

- Inventory ledger must be append-only.
- Coupon redemption must be idempotent.
- Reservation updates must be transactional with row-level locking.
- Foreign keys and check constraints enforce domain validity.
- Partial/compound indexes added for high-frequency filters and joins.

## 10 Codex prompts (run sequentially)

---

## Prompt 1 - Project bootstrap and baseline architecture

You are Codex. Build the complete project foundation.

Tasks:

- Create required package structure:
  - fullstack/ for all app code
  - root docs and evidence files (prompt.md, trajectory.json, questions.md, docs/design.md, docs/api-spec.md)
- Initialize FastAPI backend with modular folder structure.
- Initialize Vue SPA with modular folder structure and role-based shell.
- Configure PostgreSQL connectivity and migration strategy.
- Add env templates for local setup.
- Add linting, formatting, and test frameworks for frontend and backend.
- Add health endpoints and frontend health page.
- Add initial architecture narrative to docs/design.md.
- Start endpoint catalog in docs/api-spec.md.
- Record assumptions/questions in questions.md.
- Write first milestone events in trajectory.json.

Acceptance criteria:

- Frontend and backend run locally.
- DB connection is configured and validated.
- Directory/package constraints are respected.
- Initial docs are meaningful and not placeholders.

---

## Prompt 2 - Authentication, lockout, RBAC, masking baseline

You are Codex. Implement secure local auth and role permissions.

Tasks:

- Build user auth endpoints (login/logout/session validation).
- Enforce password min length 12.
- Use bcrypt for hashing and verification.
- Implement failed-attempt tracking and lockout after 5 failures for 15 minutes.
- Implement RBAC middleware/dependencies for all 5 roles.
- Build frontend login page and role-aware navigation menus.
- Implement secure error responses and lockout messages.
- Implement masking helper for sensitive values in logs/exports.
- Add optional encryption abstraction layer for PII and wallet fields.
- Add backend tests for lockout and RBAC enforcement.
- Update docs/api-spec.md and docs/design.md.
- Update trajectory.json with completed tasks.

Acceptance criteria:

- Lockout policy is test-proven.
- Unauthorized access returns proper error codes.
- Role-specific menus/routes are working.

---

## Prompt 3 - Members, tiers, points, wallet, audit

You are Codex. Implement member and loyalty system.

Tasks:

- Create member entities and APIs with tiers Base/Silver/Gold.
- Implement points rule: floor(pre_tax_amount) points.
- Add points ledger for every accrual/adjustment.
- Add optional wallet accounts and wallet ledger.
- Build cashier member lookup UI with tier, points, wallet balance.
- Add transaction-safe wallet debit/credit operations.
- Add audit logging for all loyalty and wallet changes.
- Add API tests for points correctness and wallet transaction safety.
- Update docs and trajectory.

Acceptance criteria:

- Points computation is exact and deterministic.
- Wallet operations are atomic and auditable.
- UI clearly shows balances and statuses.

---

## Prompt 4 - Campaign creation, issuance, scan redemption, rule enforcement

You are Codex. Implement full campaign and coupon lifecycle.

Tasks:

- Create campaign model and CRUD with campaign types:
  - percent-off
  - fixed-amount
  - full-reduction (threshold)
- Support date ranges, daily cap default 200, per-member daily limit default 1.
- Implement coupon issuance:
  - account assignment
  - printable QR generation flow
- Build redemption endpoint by scanned token.
- Return explicit reason codes for redemption failure.
- Build campaign management and cashier redemption UIs.
- Record issuance/redemption events with operator and timestamp.
- Add test matrix for edge cases and duplicate redemption safety.
- Update docs and trajectory.

Acceptance criteria:

- Issuance and redemption run end-to-end.
- Rule limits are strictly enforced.
- Event traceability is complete.

---

## Prompt 5 - Inventory documents, append-only ledger, reservations, locking

You are Codex. Implement inventory integrity module.

Tasks:

- Create append-only inventory ledger schema and services.
- Implement receiving workflow with optional batch/expiry.
- Implement outbound transfer workflow.
- Implement stock count workflow with variance posting.
- Implement reservation creation for open orders.
- Implement reservation release on cancellation/fulfillment.
- Use transaction boundaries and row-level locking for consistency.
- Build inventory UI pages for receiving, transfer, count, item inquiry.
- Add real-time reserved quantity indicators.
- Add concurrency tests to prove no double-spend/negative stock bugs.
- Update docs and trajectory.

Acceptance criteria:

- Ledger is append-only and reconcilable.
- Reservation and available stock remain coherent under concurrency.
- Workflows are role-protected and auditable.

---

## Prompt 6 - Training quizzes, spaced repetition queue, explainable recommendations

You are Codex. Implement employee training intelligence.

Tasks:

- Build supervisor quiz/topic management.
- Build quiz assignment and employee review queue APIs.
- Implement spaced repetition scheduler with difficulty weighting.
- Generate explainable recommendation reasons (human-readable).
- Capture attempts and correctness history.
- Calculate hit rate and trend metrics.
- Build employee review UI and supervisor performance dashboard.
- Add tests for queue generation and explanation correctness.
- Update docs and trajectory.

Acceptance criteria:

- Daily queue is generated per employee with explainable logic.
- Supervisors can inspect stats and trend lines.
- Schedule behavior is consistent and testable.

---

## Prompt 7 - Attendance, anti-fraud, cross-day calculation, approvals

You are Codex. Implement complete attendance and timekeeping.

Tasks:

- Build check-in/check-out flows (QR/NFC-compatible).
- Add optional GPS coordinates capture and storage.
- Implement configurable tolerance with default +-5 minutes.
- Implement rotating one-time QR token every 30 seconds for kiosk mode.
- Implement device binding checks.
- Implement cross-day shift handling.
- Implement auto break deduction after 6 hours (default 30 minutes).
- Implement late/early penalties (default 0.25h per incident beyond tolerance).
- Build make-up request submission and manager approval with notes.
- Add payroll reconciliation export.
- Add tests for boundary and cross-day scenarios.
- Update docs and trajectory.

Acceptance criteria:

- Fraud-prevention checks are active and effective.
- Attendance calculations are accurate for edge cases.
- Approval and export flow is complete.

---

## Prompt 8 - Dashboard builder, filter linking, drill-down, exports, read-only links

You are Codex. Implement regional dashboards and ad-hoc visualization.

Tasks:

- Build drag-and-drop dashboard builder in Vue.
- Implement reusable widgets and persisted layouts.
- Implement linked filters and drill-down by store/date.
- Build export pipeline for PNG/PDF/CSV.
- Build read-only local network shared links.
- Enforce permission-scoped data in dashboard and shared links.
- Add access/export audit trails.
- Add UI states for loading/empty/error and mobile responsiveness.
- Add tests for link permissions and export validity.
- Update docs and trajectory.

Acceptance criteria:

- Managers can build and share dashboards.
- Exports generate valid files.
- Shared links are read-only and permission-safe.

---

## Prompt 9 - Scheduled KPI jobs, hardening, integration tests, seed data

You are Codex. Implement operations hardening and local analytics jobs.

Tasks:

- Add local scheduler for nightly KPI materialization at 2:00 AM.
- Materialize and persist:
  - conversion rate
  - average order value
  - inventory turnover
- Add scheduler run logs, status tracking, retry/failure handling.
- Add manual backfill command by date range.
- Add realistic seed/demo data for all modules.
- Add integrated end-to-end tests covering critical role journeys.
- Validate sensitive-data masking defaults in logs/exports.
- Update docs with runbook and recovery procedures.
- Update trajectory milestones.

Acceptance criteria:

- Scheduled jobs run locally and update KPI tables.
- Critical integration tests pass.
- Operational docs support local maintenance.

---

## Prompt 10 - Final completion, requirement traceability, release-ready package

You are Codex. Finalize and prove full requirement coverage.

Tasks:

- Run full integration sweep across all modules.
- Close all missing functional gaps.
- Produce requirement traceability matrix mapping each original requirement to:
  - backend implementation
  - frontend implementation
  - database implementation
  - test evidence
  - doc references
- Verify all code remains within fullstack/.
- Verify root deliverables exist and are complete:
  - prompt.md
  - trajectory.json or sessions folder form
  - questions.md
  - docs/design.md
  - docs/api-spec.md
- Produce release checklist and known limitations.
- Ensure app can run locally end-to-end with setup instructions.

Acceptance criteria:

- App is fully functional (UI + backend + data flow) by end of this prompt.
- All original prompt requirements are implemented and evidenced.
- Packaging and documentation rules are fully compliant.

---

## Mandatory quality gates after every prompt

Codex must execute these gates before claiming completion:

- Build passes (frontend/backend).
- Tests pass for newly implemented behavior.
- API spec is updated for added/changed endpoints.
- Design doc updated with architecture/domain decisions.
- trajectory.json updated with milestone notes.
- questions.md updated with newly discovered ambiguity and selected assumptions.

## Definition of done for the whole app

The app is done only if:

- All 10 prompts are completed in order.
- Every functional module is working end-to-end in local environment.
- Security, RBAC, auditability, and masking are active.
- Inventory and redemption consistency guarantees are enforced transactionally.
- Attendance and spaced-repetition logic are explainable and test-backed.
- Dashboard builder, exports, shared links, and scheduled KPIs are operational.
- Packaging structure exactly matches required submission format.
