# Attendance & Leave Management (M4): Weeks 1 and 2

Attendance and leave modules of the Smart HRMS.

**Apps:** `apps/attendance/`, `apps/leave_management/`
**Scope so far:** models, migrations and service functions (business logic) with unit tests. Views, endpoints and events for notifications are planned for later weeks.

---

## Status

| Item | Status |
|---|---|
| Models and migrations (`0001_initial` in both apps) | Done |
| Attendance workflows (check-in, check-out, correction, monthly summary) | Done |
| Leave workflows (apply, approve, reject, cancel, history) | Done |
| Leave balance deduction and restoration | Done |
| Working-day calculation with weekends, public holidays and year split | Done |
| Unit tests | Done (see Tests) |
| Django admin registration | Done |
| Rules document (`docs/M4_ATTENDANCE_LEAVE_RULES.md`) | Updated for Week 2 |
| Views, URLs and permission classes on views | Not started |
| Quotas and carry-forward settings | Not started |
| Events for email notifications (M5) | Not started (Week 3) |
| Dashboard aggregates | Not started (Week 4) |

---

## Service functions

The business rules live in `services.py` in each app. Other code should call these functions and not change statuses or balances directly.

### `apps/attendance/services.py`

| Function | What it does |
|---|---|
| `check_in(employee)` | Creates today's attendance record with status `PRESENT`. Only active employees; one record per employee per day. |
| `check_out(employee)` | Sets today's check-out time. Requires an earlier check-in the same day; rejects a second check-out. |
| `correct_attendance(attendance_id, actor, *, status, check_in, check_out, reason)` | HR or Admin only. Requires a reason. Validates the status and the time order, stores who corrected it, when and why, and the audit event is recorded automatically on save by the audit mixin. |
| `get_monthly_attendance_summary(employee, year, month)` | Returns a count for each status, the total days, and the employee ID, year and month. |

### `apps/leave_management/services.py`

| Function | What it does |
|---|---|
| `create_leave_request(employee, leave_type, start_date, end_date, reason)` | Rejects an end date before the start date, and overlap with the employee's Pending or Approved requests. Creates a `PENDING` request. |
| `change_leave_status(leave_request_id, new_status, changed_by, remarks)` | Applies a status change (see rules below) and writes a history row. |
| `calculate_working_days(start_date, end_date)` | Counts Monday to Friday days, excluding public holidays. |
| `calculate_working_days_by_year(start_date, end_date)` | Same count, split by calendar year. |
| `deduct_leave_balance(leave_request)` | Deducts the working days from each year's balance; deducts nothing unless every year has enough. |
| `get_unused_leave_days(leave_request)` | Works out which days can be restored on cancellation; returns `None` when attendance records are missing or unclear. |
| `restore_leave_balance(leave_request, unused_days)` | Adds the unused days back. Runs at most once per request and never updates only some years. |

### Rules applied by `change_leave_status`

- Transitions: `Pending` to `Approved`, `Rejected` or `Cancelled`; `Approved` to `Cancelled`. Anything else raises a validation error.
- Only HR or Admin can approve or reject, and nobody can approve or reject their own request.
- Remarks are required to approve or reject.
- Approving deducts the balance. If the balance is not enough, the request becomes `Rejected` with a note.
- Approver, approver remarks and decision time are stored only for approvals and rejections. A cancellation does not overwrite them.
- Cancelling an approved request restores the eligible unused days. If attendance data is missing or unclear, the request is flagged with `restoration_status = HR_REVIEW` and the balance is left unchanged.

How unused days are decided: days after today are unused. For earlier days, a `Present` or `Late` record counts as unused leave (the employee worked), an `On-leave` record counts as taken leave, and a missing record sends the request to HR review.

---

## Models

### `attendance.Attendance`
One record per employee per day: employee, date, check-in, check-out, status (`PRESENT`, `ABSENT`, `LATE`, `HALF_DAY`, `ON_LEAVE`), correction details (`corrected_by`, `corrected_at`, `correction_note`), timestamps.

### `leave_management`

| Model | Purpose |
|---|---|
| `LeaveType` | Names of leave kinds, entered as data (`name`, `is_active`). |
| `LeaveBalance` | Remaining days per employee, leave type and year. |
| `LeaveRequest` | One application: dates, reason, status, approver, approver remarks, decision time, and the restoration fields (`restoration_status`, `restoration_review_reason`, `restoration_completed_at`). |
| `LeaveStatusHistory` | One row for every status change. A signal writes the first row when a request is created. |
| `PublicHoliday` | One row per excluded date (`date`, `name`). |

`LeaveRequest.restoration_status` values: `NOT_REQUIRED` (default), `PENDING`, `COMPLETED`, `HR_REVIEW`.

### Relationships

```
accounts.User <-- employees.Employee (user, optional one-to-one)
                       |
                       +-- Attendance
                       +-- LeaveBalance
                       +-- LeaveRequest <-- LeaveStatusHistory

LeaveType <-- LeaveBalance, LeaveRequest
```

Records belong to `employees.Employee`. Fields that record who performed an action point to the user model through `settings.AUTH_USER_MODEL`.

### Delete behaviour
Employee, leave type and leave request links use `PROTECT`, so deletion is blocked while records exist. User links (`corrected_by`, `approver`, `changed_by`) use `SET_NULL`, so the record stays.

---

## Database rules

| Rule | Where |
|---|---|
| One attendance record per employee per date | `Attendance` unique constraint |
| Check-out later than check-in | `Attendance` check constraint |
| Leave end date not before start date | `LeaveRequest` check constraint |
| One balance per employee, leave type and year | `LeaveBalance` unique constraint |
| One public holiday per date | `PublicHoliday` unique field |

---

## Migrations

| App | Migration | Creates |
|---|---|---|
| `attendance` | `0001_initial.py` | `Attendance` |
| `leave_management` | `0001_initial.py` | `LeaveType`, `LeaveBalance`, `LeaveRequest`, `LeaveStatusHistory` |
| `leave_management` | `0002_publicholiday.py` | `PublicHoliday` |
| `leave_management` | `0003_leaverequest_restoration_completed_at_and_more.py` | Restoration fields on `LeaveRequest` |

All were generated with `makemigrations`. `makemigrations --check` reports no changes. Once merged, an existing migration should not be edited; further changes go into new migrations.

---

## Tests

Run:

```
python manage.py test apps.attendance apps.leave_management
```

| Area | Tests | Covers |
|---|---|---|
| Attendance | 14 | Check-in and check-out rules, duplicate prevention, inactive employees, HR-only correction with a reason, audit event, monthly summary |
| Leave | 43 | Status transitions, role checks, history, validation and overlap, working-day calculation, balance deduction and restoration |

The leave restoration test class inherits the transition tests, so those run twice.

Tests that depend on today's date patch `timezone.localdate`, so they do not change over time.

---

## Known issues
- Changes made in Django admin skip the service rules. Use admin for viewing and test data only.

---

## Not included yet

- Views, URLs and the permission classes (`IsHR`, `IsSelfOrHR`) on views.
- Quota settings per leave type, carry-forward, and a workflow for manual balance adjustments (balances can be edited in Django admin).
- `On-leave` attendance records are not created when leave is approved.
- Events for email notifications (Week 3) and dashboard aggregates (Week 4).
- Automatic assignment of `Late` and `Half-day`, which depends on decisions listed in the rules document.

---

## Notes for other members

- **M5 (notifications):** the leave decision and attendance correction are stored on `LeaveRequest` and `Attendance`. The event format will be agreed in Week 3.
- **M6 (frontend):** call the service functions listed above and do not set statuses directly. Status values are stored in upper case (for example `PENDING`).
- **M2 (audit and permissions):** `correct_attendance` is audited through `AuditedModelMixin`.
- **Please tell M4 before** renaming `Employee` or changing its primary key, since the foreign keys depend on it.
