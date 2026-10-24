# Attendance & Leave Management: Rules Specification

| Field | Details |
|---|---|
| Module | Attendance & Leave (`apps/attendance/`, `apps/leave_management/`) |
| Owner | M4 |
| Phase | Week 1: Requirements and Rules |
| Status | Draft — reviewed by team lead; open decisions remain |

## 1. Purpose and Scope

This specification defines the business rules for the Attendance and Leave modules of the Smart HRMS. It documents attendance statuses, leave states, permitted leave status transitions, data integrity requirements, and access constraints that the implementation must satisfy.

This document is a requirements specification. It does not claim that the corresponding models, migrations, APIs, or tests have been implemented.

### 1.1 Conventions

| Label | Meaning |
|---|---|
| Confirmed | Explicitly stated in the project requirements or agreed upon by the team. |
| Proposed | Recommended by M4 but not yet approved. |
| Open | Not sufficiently specified to implement without a team decision. |

Proposed and Open items must not be treated as approved company policy until the team confirms them.

## 2. Attendance Rules

### 2.1 Attendance Statuses

| Status | Definition | Status |
|---|---|---|
| Present | The employee is recorded as having attended on the given day. | Confirmed |
| Absent | The employee is not recorded as having attended on the given day. | Confirmed |
| Late | The employee attended after the expected start time. | Confirmed |
| Half-day | The employee is recorded as having worked a partial day. | Confirmed |
| On-leave | The employee is on leave on the given day. | Confirmed |

The criteria distinguishing Late from Half-day remain open and must be agreed upon before the relevant validation rules are implemented.

### 2.2 Attendance Requirements

| ID | Requirement | Status |
|---|---|---|
| ATT-01 | Employees can record check-in and check-out. | Confirmed |
| ATT-02 | At most one check-in is permitted per employee per day. | Confirmed |
| ATT-03 | Attendance corrections are restricted to HR. | Confirmed |
| ATT-04 | Every attendance correction is audited. | Confirmed |
| ATT-05 | A monthly attendance summary is produced. | Confirmed |
| ATT-06 | A correction records who made the change and when. | Proposed |
| ATT-07 | Employees can view only their own attendance; HR and Admin can view all attendance records. | Proposed |

**Implementation notes:**

- Duplicate check-in attempts must not create multiple attendance records for the same employee and day.
- The handling of repeated check-out attempts, missing check-outs, and attendance records spanning midnight remains open unless specified elsewhere in the project requirements.
- The system must enforce the confirmed HR-only attendance correction rule. The effective permission must be checked against the existing role and permission implementation.
- The relationship between attendance records and the shared Employee/User models must be confirmed before finalizing model fields and migrations.

## 3. Leave Rules

### 3.1 Leave Statuses

| Status | Definition | Status |
|---|---|---|
| Pending | The request has been submitted and awaits a decision. | Confirmed |
| Approved | The request has been accepted. | Confirmed |
| Rejected | The request has been declined. | Confirmed |
| Cancelled | The request has been withdrawn. | Confirmed |

### 3.2 Permitted State Transitions

The only permitted transitions originate from `Pending`. Any other status transition must be rejected with a validation error.

| From \ To | Pending | Approved | Rejected | Cancelled |
|---|---|---|---|---|
| Pending | Not applicable | Permitted | Permitted | Permitted |
| Approved | Denied | Not applicable | Denied | Denied |
| Rejected | Denied | Denied | Not applicable | Denied |
| Cancelled | Denied | Denied | Denied | Not applicable |

Approved, Rejected, and Cancelled are terminal states under the current specification.

The transition rules must be enforced server-side and must not be bypassed by alternate API endpoints, views, or other application code paths.

Cancellation of an already Approved, Rejected, or Cancelled request is not permitted under the current rules. Any change to this policy requires an explicit team decision and an update to this specification before implementation.

### 3.3 Leave Requirements

| ID | Requirement | Status |
|---|---|---|
| LV-01 | Employees can apply for leave. | Confirmed |
| LV-02 | Leave requests can be approved, rejected, or cancelled. The authorization rules and remark requirements must be confirmed by the team lead. | Actions confirmed; policy details open |
| LV-03 | A status history is retained for each leave request. | Confirmed |
| LV-04 | Invalid status transitions raise a validation error. | Confirmed |
| LV-05 | Overlapping leave dates are detected. | Confirmed |
| LV-06 | Leave balance is checked. | Confirmed |
| LV-07 | A leave decision emits an event used for email notification. | Confirmed |
| LV-08 | The end date must not precede the start date. | Proposed |
| LV-09 | Each status change is recorded in history with a timestamp and the acting user. | Proposed |

**Implementation notes:**

- Leave balance validation must use the leave types and balance rules agreed upon by the team.
- Overlapping date validation must be implemented consistently with the final policy for leave dates and statuses.
- The team must clarify whether cancellation restores leave balance, which days are eligible for restoration, and how the restoration is calculated.
- Notification events must be triggered for the decisions specified in the agreed requirements. The event payload and notification behavior must be consistent with the existing notification architecture.
- The required remarks for approval, rejection, and cancellation remain open until the team confirms the policy.

## 4. Data Integrity and Access Control

### 4.1 Confirmed Requirements

- Authentication and least-privilege authorization apply to protected operations.
- Access boundaries must be tested explicitly.
- Attendance corrections are restricted to HR and must be audited.
- Invalid leave transitions must be rejected with a validation error.

### 4.2 Proposed Requirements

The following recommendations require team approval before being treated as finalized requirements:

- All business validation is enforced server-side. Client-side validation is advisory only.
- Leave transition logic is centralized so that no application code path can bypass the permitted-transition rules.
- Permissions for approving, rejecting, and cancelling leave follow the role-permission matrix once it is finalized.
- Records are not hard-deleted; changes remain traceable through history or audit events.
- Attendance correction history records the acting user, timestamp, and details needed to identify the correction.

### 4.3 Permission Enforcement

- The implementation must follow the confirmed HR-only attendance correction rule.
- The existing `IsHR` permission must be inspected to determine whether Admin users also satisfy that permission.
- If Admin currently satisfies `IsHR`, the implementation must not unintentionally grant Admin attendance correction access unless the team explicitly approves that policy.
- Leave approval, rejection, and cancellation permissions must remain configurable according to the agreed role-permission matrix.

## 5. Open Items for Team Lead Decision

The following items are not fully specified in the requirements available to M4. They must remain open until explicitly decided by the team.

| ID | Question | Required clarification |
|---|---|---|
| OPEN-01 | What differentiates `Late` and `Half-day`? | Define the applicable time thresholds or other criteria. |
| OPEN-02 | How is `On-leave` assigned? | Confirm whether approved leave automatically determines attendance status or whether manual assignment is allowed. |
| OPEN-03 | Who can approve or reject leave requests? | Confirm the permitted roles and authorization rules. |
| OPEN-04 | Who can cancel a leave request? | Confirm the permitted roles. Under the current transition matrix, only Pending requests can be cancelled. |
| OPEN-05 | Are remarks mandatory? | Confirm whether remarks are required for approval, rejection, and cancellation. |
| OPEN-06 | Which leave types and balances apply? | Define leave categories, allocation, balance calculation, and restoration rules. |
| OPEN-07 | How are weekends and holidays treated? | Confirm whether non-working days count toward leave duration and balance deductions. |
| OPEN-08 | What format is required for the monthly attendance summary? | Confirm the required fields, grouping, and output format. |
| OPEN-09 | Can Admin correct attendance? | Resolve the interaction between the HR-only rule and the existing `IsHR` permission. |
| OPEN-10 | Which audit action represents leave cancellation? | Inspect the current `AuditEvent` action choices and agree on the appropriate action before implementing cancellation auditing. |
| OPEN-11 | Should attendance and leave records reference `Employee` or `User`? | Inspect the shared model definitions and agree on the correct relationship before finalizing foreign keys. |
| OPEN-12 | What happens when leave is cancelled after approval? | Confirm balance restoration and audit requirements if the team later changes the current terminal-state policy. |
| OPEN-13 | How should missing or duplicate attendance events be handled? | Define the expected behavior for repeated check-ins, repeated check-outs, and missing check-outs. |

Open items must be tracked and resolved before implementing the functionality they affect. Decisions should be reflected in this document so that implementation and tests follow a single agreed specification.

## 6. Implementation Boundaries

- This document defines rules and requirements. It does not claim that models, migrations, APIs, or tests have been implemented.
- Django model relationships and field definitions must match the agreed shared `User` and `Employee` models.
- Database constraints and application-level validation must be selected according to the final model design and confirmed requirements.
- Authorization must be enforced server-side for every protected operation.
- Migrations and tests must be generated and executed in the project environment before implementation is reported as verified.
- Tests must cover permitted and denied leave transitions, overlapping leave dates, balance validation, access control, and attendance correction auditing as applicable to the finalized requirements.
- Requirements marked Proposed or listed under Open Items must not be treated as approved company policy until confirmed by the team lead.
- Changes to confirmed rules must be documented and reviewed before they are implemented.

## 7. Review and Decision Tracking

This document is a draft requirements specification reviewed by the team lead. Review of the draft does not mean that every proposed rule or open policy question has been approved.

| Item | Status |
|---|---|
| Initial specification | Documented |
| Team lead review | In progress until review comment is submitted |
| Open policy decisions | Pending team confirmation |
| Implementation | Not verified by this document |

Once the team confirms a policy decision, update the relevant rule and its status in this document. Keep unresolved items explicitly marked as Open until a decision is recorded.