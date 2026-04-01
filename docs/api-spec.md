# MeridianOps API Specification (Prompts 1-4)

## API conventions

- Base URL: `http://localhost:8000`
- Version prefix: `/api/v1`
- Content type: `application/json`
- Authentication: local cookie session (`meridianops_session`) from `/auth/login`
- Error format: `{ "detail": "..." }` for validation/auth/business errors

## Implemented endpoint catalog

## 1) Health

### GET `/api/v1/health`

API liveness probe.

### GET `/api/v1/health/database`

API + DB connectivity probe (`503` when DB probe is degraded).

## 2) Authentication and session

### POST `/api/v1/auth/login`

Authenticates username/password, applies lockout policy, sets session cookie.

Request:

```json
{
  "username": "admin",
  "password": "ChangeMeNow123"
}
```

Response `200`:

```json
{
  "message": "Login successful",
  "user": {
    "id": 1,
    "username": "admin",
    "display_name": "Local Administrator",
    "roles": ["administrator"]
  }
}
```

Failure examples:

- `401 Invalid username or password`
- `401 Account locked until <timestamp>`

### POST `/api/v1/auth/logout`

Revokes current session and clears cookie.

### GET `/api/v1/auth/session`

Returns authenticated user context from cookie session.

## 3) RBAC verification endpoints

Protected test/reference endpoints:

- `GET /api/v1/secure/administrator`
- `GET /api/v1/secure/store-manager`
- `GET /api/v1/secure/inventory-clerk`
- `GET /api/v1/secure/cashier`
- `GET /api/v1/secure/employee`

Return `401` when unauthenticated, `403` when role disallowed.

## 4) Members and loyalty (Prompt 3)

### Member tiers

Supported: `base`, `silver`, `gold`.

### GET `/api/v1/members?search=`

Role: administrator/store_manager/cashier.

Returns member list with live balances:

```json
[
  {
    "id": 1,
    "member_code": "MEM-001",
    "full_name": "Jane Store",
    "tier": "silver",
    "stored_value_enabled": true,
    "points_balance": 15,
    "wallet_balance": "29.75"
  }
]
```

### POST `/api/v1/members`

Role: administrator/store_manager.

Creates member and optional wallet account.

### GET `/api/v1/members/{member_code}`

Role: administrator/store_manager/cashier.

Member lookup for checkout operations.

### PATCH `/api/v1/members/{member_code}`

Role: administrator/store_manager.

Updates name/tier/stored-value toggle.

### POST `/api/v1/members/{member_code}/points/accrue`

Role: administrator/store_manager/cashier.

Request:

```json
{
  "pre_tax_amount": "19.99",
  "reason": "purchase"
}
```

Rule: points = `floor(pre_tax_amount)`.

### POST `/api/v1/members/{member_code}/points/adjust`

Role: administrator/store_manager.

Manual positive/negative adjustments.

### POST `/api/v1/members/{member_code}/wallet/credit`

Role: administrator/store_manager/cashier.

Credits stored value.

### POST `/api/v1/members/{member_code}/wallet/debit`

Role: administrator/store_manager/cashier.

Debits stored value with insufficient-funds protection.

### GET `/api/v1/members/{member_code}/points-ledger`

Role: administrator/store_manager/cashier.

Returns points ledger entries.

### GET `/api/v1/members/{member_code}/wallet-ledger`

Role: administrator/store_manager/cashier.

Returns wallet ledger entries with running balance.

## 5) Campaigns and coupon lifecycle (Prompt 4)

### Campaign types

- `percent_off`
- `fixed_amount`
- `full_reduction` (threshold + fixed amount)

### POST `/api/v1/campaigns`

Role: administrator/store_manager.

Creates campaign with defaults:

- daily cap default `200`
- per-member daily limit default `1`

### GET `/api/v1/campaigns`

Role: administrator/store_manager.

Lists campaigns.

### GET `/api/v1/campaigns/{campaign_id}`

Role: administrator/store_manager/cashier.

Returns campaign detail.

### PATCH `/api/v1/campaigns/{campaign_id}`

Role: administrator/store_manager.

Updates campaign settings/active status.

### POST `/api/v1/campaigns/issue`

Role: administrator/store_manager.

Issuance methods:

- `account_assignment` (requires valid member code)
- `printable_qr` (returns local QR payload string)

Response:

```json
{
  "coupon_code": "CPN-ABC123...",
  "campaign_id": 10,
  "issuance_method": "printable_qr",
  "qr_payload": "coupon:CPN-ABC123..."
}
```

### POST `/api/v1/campaigns/redeem`

Role: administrator/store_manager/cashier.

Request:

```json
{
  "coupon_code": "CPN-...",
  "member_code": "MEM-001",
  "pre_tax_amount": "88.50",
  "order_reference": "ORDER-001"
}
```

Behavior:

- enforces campaign active date window
- enforces campaign daily cap
- enforces per-member daily limit
- enforces assignment/member matching when applicable
- supports idempotent replay for same successful `coupon + order_reference`
- returns reason codes for failures

Common reason codes:

- `SUCCESS`
- `IDEMPOTENT_REPLAY`
- `COUPON_NOT_FOUND`
- `ALREADY_REDEEMED`
- `CAMPAIGN_INACTIVE`
- `DAILY_CAP_REACHED`
- `MEMBER_DAILY_LIMIT_REACHED`
- `MEMBER_MISMATCH`
- `MEMBER_REQUIRED`
- `THRESHOLD_NOT_MET`

## 6) Auditability and traceability

Events captured for Prompt 3-4 flows:

- member creation/update
- points accrual/adjustment
- wallet credit/debit
- coupon issuance/redemption

Traceability fields include actor, resource id, event action, timestamp, and masked sensitive detail payload.

## 7) Inventory integrity workflows (Prompt 5 - implemented in this pass)

### POST `/api/v1/inventory/items`

Role: administrator/store_manager/inventory_clerk.

Creates inventory item master with optional batch/expiry tracking flags.

### POST `/api/v1/inventory/locations`

Role: administrator/store_manager/inventory_clerk.

Creates inventory location.

### POST `/api/v1/inventory/receiving`

Role: administrator/store_manager/inventory_clerk.

Posts receiving document and append-only positive `inventory_ledger` entries.

### POST `/api/v1/inventory/transfers`

Role: administrator/store_manager/inventory_clerk.

Posts transfer document after available-stock validation.
Writes paired append-only ledger entries: `transfer_out` + `transfer_in`.

### POST `/api/v1/inventory/counts`

Role: administrator/store_manager/inventory_clerk.

Posts count session and variance adjustment entries (`count_adjustment`) against current on-hand.

### POST `/api/v1/inventory/reservations`

Role: administrator/store_manager/inventory_clerk.

Creates open-order stock reservation if available stock is sufficient.
Reservation impact is recorded as append-only `reservation_create` ledger entry.

### POST `/api/v1/inventory/reservations/release`

Role: administrator/store_manager/inventory_clerk.

Releases remaining reserved quantity for a reservation and records `reservation_release` ledger entry.

### GET `/api/v1/inventory/positions`

Role: administrator/store_manager/inventory_clerk/cashier.

Returns position snapshot with:

- on-hand quantity
- reserved quantity
- available quantity

### GET `/api/v1/inventory/positions/{sku}/{location_code}`

Role: administrator/store_manager/inventory_clerk/cashier.

Returns one SKU/location position snapshot.

### GET `/api/v1/inventory/ledger?limit=...`

Role: administrator/store_manager/inventory_clerk/cashier.

Returns recent append-only ledger rows for operational traceability.

## 8) Training and spaced repetition workflows

### GET `/api/v1/training/topics`

Role: administrator/store_manager/employee.

Lists quiz topics.

### POST `/api/v1/training/topics`

Role: administrator/store_manager.

Creates quiz topic with difficulty weighting.

### POST `/api/v1/training/questions`

Role: administrator/store_manager.

Creates topic question with answer choices.

### POST `/api/v1/training/assignments`

Role: administrator/store_manager.

Assigns topic to employee and initializes spaced repetition state.

### GET `/api/v1/training/review-queue`

Role: administrator/store_manager/employee.

Returns employee queue with explainable recommendations.

### POST `/api/v1/training/attempts`

Role: administrator/store_manager/employee.

Submits quiz attempt and updates spaced repetition schedule.

### GET `/api/v1/training/stats`

Role: administrator/store_manager.

Returns per-topic attempts, correctness, and hit rate.

### GET `/api/v1/training/trends?days=14`

Role: administrator/store_manager.

Returns trend points for attempts/hit rate.

## 9) Attendance and anti-fraud workflows

### GET `/api/v1/attendance/rules`

Role: administrator/store_manager/employee.

Returns tolerance, break, and penalty configuration.

### PATCH `/api/v1/attendance/rules`

Role: administrator/store_manager.

Updates attendance calculation rules.

### POST `/api/v1/attendance/qr/rotate`

Role: administrator/store_manager.

Creates one-time QR token expiring in 30 seconds.

### POST `/api/v1/attendance/check-in`

Role: administrator/store_manager/employee.

Validates QR + device binding and opens shift.

### POST `/api/v1/attendance/check-out`

Role: administrator/store_manager/employee.

Validates QR + device binding, closes shift, computes:

- worked hours
- automatic break deduction
- late/early incidents
- penalty hours

### GET `/api/v1/attendance/me/shifts`

Role: administrator/store_manager/employee.

Lists current user shifts.

### POST `/api/v1/attendance/makeup-requests`

Role: administrator/store_manager/employee.

Submits attendance correction request.

### GET `/api/v1/attendance/makeup-requests`

Role: administrator/store_manager/employee.

Managers/admins see all; employees see own requests.

### POST `/api/v1/attendance/makeup-requests/{request_id}/approve`

Role: administrator/store_manager.

Approves request with manager note.

### GET `/api/v1/attendance/payroll-export?start_date=...&end_date=...`

Role: administrator/store_manager.

Exports reconciliation CSV from daily attendance results.

## 10) Security controls

### GET `/api/v1/auth/security-policy`

Role: administrator/store_manager.

Returns active auth policy values (min password length, lockout, session) and local security defaults.
