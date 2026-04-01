# Blocker-Level Ambiguities and Execution Assumptions

This document captures only ambiguities that can block implementation start or cause major rework.

## 1) Campaign Scope vs Store Scope

### The Gap

The prompt defines regional dashboards and role-based data scope, but does not explicitly define whether campaigns are global, region-level, or store-level entities.

### The Interpretation

Campaigns are region-configured but enforced per store at redemption time. A campaign can be assigned to one or more stores.

### Proposed Implementation

Use `campaigns` as core entity and `campaign_store_scopes` as join table (`campaign_id`, `store_id`).
At redemption, validate coupon campaign against checkout store id before other rule checks.

## 2) Checkout Order Lifecycle for Reservation Release

### The Gap

Inventory rules require reservations and release on cancellation/fulfillment, but order state transitions are not explicitly specified.

### The Interpretation

Use a minimal order lifecycle with states: `created`, `reserved`, `completed`, `cancelled`.

### Proposed Implementation

Create `orders` + `order_lines` + `inventory_reservations`.
On `reserved`, create reservation ledger entries; on `completed` or `cancelled`, release reservation in one transaction using row-level locking.

## 3) QR/NFC Attendance Input Contract

### The Gap

Prompt requires QR/NFC check-in/out but does not define payload structure or how NFC is represented without external hardware integration.

### The Interpretation

Treat NFC as an alternate token source to QR; both resolve to the same attendance token validation pipeline.

### Proposed Implementation

Single endpoint contract with `check_method` enum (`qr`, `nfc`) and `token_value`.
Token validator checks rotation window, one-time use, and user/device binding before opening or closing shifts.

## 4) Device Binding Enrollment and Recovery

### The Gap

Anti-fraud requires device binding but does not define first-time registration flow or recovery if device is replaced.

### The Interpretation

First successful attendance check binds the device to employee; manager/admin can reset binding.

### Proposed Implementation

Table `device_bindings` (`user_id`, `device_fingerprint`, `active`, `updated_by`).
Add admin endpoint to rotate/reset binding with audit log entry.

## 5) Spaced-Repetition Algorithm Parameters

### The Gap

Prompt requires daily review queue, difficulty weighting, and explainable recommendations, but does not define scheduling formula.

### The Interpretation

Use a simple SM-2-inspired interval model with bounded factors and explicit reason generation.

### Proposed Implementation

Store `spaced_repetition_state` per employee/topic (`ease_factor`, `interval_days`, `last_result`, `next_review_date`).
Queue job selects due items each day and writes recommendation text from deterministic rules (miss streak, interval growth, difficulty weight).

## 6) Dashboard Builder Component Catalog

### The Gap

Prompt requires drag-and-drop ad-hoc visualizations, but does not define which component types are mandatory.

### The Interpretation

Support a minimal stable catalog for v1: KPI card, trend line, table, pie chart.

### Proposed Implementation

Persist dashboard layouts as JSON widgets (`id`, `kind`, `metric`, `dimension`, `x`, `y`, `w`, `h`, `config`).
Frontend builder exposes draggable palette; backend validates allowed widget kinds and metric enums.

## 7) Export Fidelity Requirements (PNG/PDF/CSV)

### The Gap

Prompt mandates PNG/PDF/CSV export but does not define required visual fidelity or whether synthetic placeholders are acceptable.

### The Interpretation

CSV must be raw tabular export; PNG/PDF must be generated from real dashboard data at export time.

### Proposed Implementation

Use server-side chart rendering (matplotlib) for PNG and PDF pages from the same dataset used by dashboard API responses.
Add export regression tests validating MIME type, binary signatures, and non-trivial payload size.

## 8) Read-Only Shared Link Security Boundaries

### The Gap

Prompt asks for read-only local-network sharing but does not specify expiration policy, revocation behavior, or scope filters.

### The Interpretation

Shared links are token-based, default read-only, support optional expiry, and inherit creator's permitted store scope.

### Proposed Implementation

Table `dashboard_share_links` (`token`, `dashboard_id`, `allowed_store_ids`, `expires_at`, `is_active`, `readonly`).
All write routes on shared context return 403; access checks enforce token validity + active flag + store/date scope intersection.

## 9) Role-to-Data Scope Mapping

### The Gap

Prompt defines roles but does not fully define per-role store visibility rules for reports and shared links.

### The Interpretation

Administrator: all stores; Store Manager: assigned stores; Inventory Clerk/Cashier/Employee: operational scope by assigned store only.

### Proposed Implementation

Use `user_store_scopes` table and central authorization service returning effective store ids.
All analytics and exports must filter by effective scope before query execution.

## 10) Encryption Scope and Key Management

### The Gap

Prompt says optional at-rest encryption for stored-value and PII but does not define key source/rotation and fallback behavior.

### The Interpretation

Encryption is feature-flagged by environment key presence; without key, fields remain plaintext with masking still enforced in logs/exports.

### Proposed Implementation

Field-level encryption wrapper using Fernet/AES-GCM with envelope format versioning.
Config keys: `FIELD_ENCRYPTION_KEY`, `ENCRYPTION_ENABLED`; add key-rotation utility and migration-safe decrypt/re-encrypt job.
