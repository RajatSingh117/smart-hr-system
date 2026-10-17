# Attendance & Leave Management (M4): Week 1

Base table structure for the attendance and leave modules of the Smart HRMS.

**Apps:** `apps/attendance/`, `apps/leave_management/`
**Scope of Week 1:** models, migrations and admin registration. Business logic, views and tests are planned for Week 2.

---

## Status

| Item | Status |
|---|---|
| Attendance model and migration (`0001_initial`) | Done |
| Leave models and migration (`0001_initial`) | Done |
| Migrations applied cleanly on a fresh database | Verified |
| Django admin registration | Done |
| Rules document (`docs/M4_ATTENDANCE_LEAVE_RULES.md`) | Submitted to team lead|
| Views, services, permissions, audit calls, tests | Not started (Week 2) |

---

## Models

### `attendance.Attendance`
One record per employee per day.

| Field | Description |
|---|---|
| `employee` | Link to `employees.Employee` |
| `date` | Attendance date |
| `check_in`, `check_out` | Optional timestamps |
| `status` | `PRESENT`, `ABSENT`, `LATE`, `HALF_DAY`, `ON_LEAVE` |
| `corrected_by`, `corrected_at`, `correction_note` | Correction details (optional) |
| `created_at`, `updated_at` | Timestamps |

### `leave_management.LeaveType`
Names of leave kinds. Values are entered as data; no leave types or quotas are defined in code.

| Field | Description |
|---|---|
| `name` | Unique name |
| `is_active` | Allows a type to be retired without deleting it |

### `leave_management.LeaveBalance`
Remaining leave for one employee, leave type and year.

| Field | Description |
|---|---|
| `employee`, `leave_type` | Links |
| `year` | Balance year |
| `remaining_days` | Decimal (6 digits, 2 decimal places) |
| `updated_at` | Timestamp |

### `leave_management.LeaveRequest`
One leave application and its current status.

| Field | Description |
|---|---|
| `employee`, `leave_type` | Links |
| `start_date`, `end_date`, `reason` | Request details |
| `status` | `PENDING` (default), `APPROVED`, `REJECTED`, `CANCELLED` |
| `approver`, `approver_remarks`, `decided_at` | Decision details (optional) |
| `created_at`, `updated_at` | Timestamps |

### `leave_management.LeaveStatusHistory`
One row for every status change of a leave request.

| Field | Description |
|---|---|
| `leave_request` | Link to the request |
| `old_status`, `new_status` | Status before and after (`old_status` may be blank for the first entry) |
| `changed_by`, `remarks` | Who changed it and why |
| `changed_at` | Timestamp |

---

## Relationships

```
accounts.User <-- employees.Employee (user, optional one-to-one)
                       |
                       +-- Attendance
                       +-- LeaveBalance
                       +-- LeaveRequest <-- LeaveStatusHistory

LeaveType <-- LeaveBalance, LeaveRequest
```

- Records belong to `employees.Employee` (referenced as the string `"employees.Employee"`).
- Fields that record who performed an action (`corrected_by`, `approver`, `changed_by`) point to the user model through `settings.AUTH_USER_MODEL`.
- No code is imported from other apps.
- A logged-in user maps to an employee through `user.employee_profile`. This link is optional, so Week 2 code must handle users without an employee record.

---

## Database rules

| Rule | Where |
|---|---|
| One attendance record per employee per date | `Attendance` unique constraint |
| Check-out must be later than check-in | `Attendance` check constraint |
| Leave end date must not be before start date | `LeaveRequest` check constraint |
| One balance per employee, leave type and year | `LeaveBalance` unique constraint |
| Status values limited to fixed choices | All status fields |

### Delete behaviour

| Link | Behaviour |
|---|---|
| Employee, leave type, leave request (from these tables) | `PROTECT`: deletion is blocked while records exist |
| `corrected_by`, `approver`, `changed_by` | `SET_NULL`: the record stays and only the user link is cleared |

### Indexes
- `Attendance`: `(date, status)`
- `LeaveRequest`: `(employee, start_date, end_date)` and `(status, created_at)`
- `LeaveStatusHistory`: `(leave_request, changed_at)`

---

## Migrations

| App | Migration | Creates |
|---|---|---|
| `attendance` | `0001_initial.py` | `Attendance` |
| `leave_management` | `0001_initial.py` | `LeaveType`, `LeaveBalance`, `LeaveRequest`, `LeaveStatusHistory` |

Both were generated with `makemigrations` and depend on `employees.0001_initial` and the user model migration. They were not written by hand. They include the constraints and indexes listed above.

Checks run on a fresh SQLite database:

```
python manage.py makemigrations --check    # No changes detected
python manage.py migrate                   # all migrations applied without errors
```

To apply locally:

```
python manage.py migrate
```

Migration rule for the team: once merged, `0001_initial.py` in each app should not be edited or deleted. Further schema changes go into new migrations.

---

## Files

| File | Purpose | Status |
|---|---|---|
| `models.py` | Table definitions | Done |
| `migrations/0001_initial.py` | Initial schema | Done |
| `admin.py` | Django admin registration, for viewing and test data | Done |
| `apps.py` | App configuration | Provided in the project skeleton |
| `views.py` | Views and API endpoints | Not started (Week 2) |
| `tests.py` | Unit tests | Not started (Week 2) |

The same files apply to both apps.

Note on admin: changes made in Django admin do not pass through the Week 2 rules (status transitions, overlap and balance checks, audit logging). Use it for viewing and for creating test data only. The leave status history is shown read-only inside the leave request screen.

---

## Not included in Week 1

These are planned for Week 2 and are not implemented:

- Check-in / check-out and duplicate check-in handling
- HR-only attendance corrections with audit logging
- Monthly attendance summary
- Leave apply / approve / reject / cancel with remarks
- Valid status transition checks
- Overlap and balance validation
- Permissions, views and unit tests

Not decided in the project documents, so not assumed in the models: leave types and quotas, how Late and Half-day are determined, how leave days are counted (weekends and holidays), and carry-forward rules.

---

## Notes for other members

- **M5 (notifications):** leave decisions and attendance corrections are stored on `LeaveRequest` and `Attendance`. The event format will be agreed in Week 3.
- **M6 (frontend):** the fields above are the stable base for forms and pages. Status values are stored in upper case (for example `PENDING`).
- **M2 (audit):** audit calls are not wired in yet and will be added in Week 2.
- **Please tell M4 before** renaming `Employee` or changing its primary key, since the foreign keys depend on it.
