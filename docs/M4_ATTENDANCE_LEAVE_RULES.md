Attendance & Leave Management: Rules Specification

|Module| Attendance & Leave ("apps/attendance/", "apps/leave_management/")
Owner| M4
Phase| Week 1: Requirements and Rules
Status| Draft, pending team lead review

---

1. Purpose and Scope

This specification defines the business rules for the Attendance and Leave modules of the Smart HRMS. It documents attendance statuses, leave states, permitted leave status transitions, and the integrity and access constraints that the implementation must satisfy.

1.1 Conventions

Label| Meaning
Confirmed| Stated in the project requirements.
Proposed| A recommendation by M4. Requires team lead approval before it becomes a rule.
Open| Not specified in the project requirements. No assumption has been made.

---

2. Attendance Rules

2.1 Attendance Statuses (Confirmed)

Status| Definition
"Present"| The employee is recorded as having attended on the given day.
"Absent"| The employee is not recorded as having attended on the given day.
"Late"| The employee attended, but after the expected start time.
"Half-day"| The employee is recorded as having worked a partial day.
"On-leave"| The employee is on leave on the given day.

2.2 Attendance Requirements

ID| Requirement| Status
ATT-01| Employees can record check-in and check-out.| Confirmed
ATT-02| At most one check-in is permitted per employee per day.| Confirmed
ATT-03| Attendance corrections may be made by HR only.| Confirmed
ATT-04| Every attendance correction is audited.| Confirmed
ATT-05| A monthly attendance summary is produced.| Confirmed
ATT-06| A correction records who made the change and when.| Proposed
ATT-07| Employees can view only their own attendance; HR and Admin can view all records.| Proposed

---

3. Leave Rules

3.1 Leave Statuses (Confirmed)

Status| Definition
"Pending"| The request has been submitted and awaits a decision.
"Approved"| The request has been accepted.
"Rejected"| The request has been declined.
"Cancelled"| The request has been withdrawn.

3.2 State Transitions (Confirmed)

The only valid transitions originate from "Pending". Any other transition must be rejected with a validation error.

From \ To| Pending| Approved| Rejected| Cancelled
Pending| n/a| Permitted| Permitted| Permitted
Approved| Denied| n/a| Denied| Denied
Rejected| Denied| Denied| n/a| Denied
Cancelled| Denied| Denied| Denied| n/a

"Approved", "Rejected", and "Cancelled" are terminal states.

stateDiagram-v2
    [*] --> Pending
    Pending --> Approved
    Pending --> Rejected
    Pending --> Cancelled
    Approved --> [*]
    Rejected --> [*]
    Cancelled --> [*]

3.3 Leave Requirements

ID| Requirement| Status
LV-01| Employees can apply for leave.| Confirmed
LV-02| Leave requests can be approved, rejected, or cancelled. Remarks must follow the policy confirmed by the team lead.| Confirmed actions; remark requirement needs clarification
LV-03| A status history is retained for each leave request.| Confirmed
LV-04| Invalid status transitions raise a validation error.| Confirmed
LV-05| Overlapping leave dates are detected.| Confirmed
LV-06| Leave balance is checked.| Confirmed
LV-07| A leave decision emits an event used for email notification.| Confirmed
LV-08| The end date must not precede the start date.| Proposed
LV-09| Each status change is recorded in the history with a timestamp and the acting user.| Proposed

---

4. Data Integrity and Access Control

4.1 Confirmed

- Authentication and least-privilege authorization apply to protected operations, and access boundaries are tested explicitly.
- Attendance corrections are restricted to HR and are audited.
- Invalid leave transitions are rejected with a validation error.

4.2 Proposed

- All validation is enforced server-side; client-side checks are advisory only.
- Transition logic is centralized so that no code path can bypass the permitted-transition rules.
- Permissions for approving, rejecting, and cancelling leave follow the role-permission matrix once it is finalized.
- Records are not hard-deleted; changes are traceable through history or audit events.

---

5. Open Items for Team Lead Decision

The following details are not fully specified in the requirements available to M4. No assumptions are made about them.

#| Question
1| What criteria determine "Late" and "Half-day"?
2| How is "On-leave" assigned: automatically from approved leave, or manually?
3| Which roles may approve or reject leave requests?
4| Who may cancel a request, and may an already decided request be cancelled? The currently confirmed transitions permit cancellation from "Pending" only.
5| Are remarks mandatory for approval, rejection, or cancellation?
6| Which leave types and balances apply, and how are weekends and holidays treated?
7| Is a specific format required for the monthly attendance summary?
8| Attendance corrections are restricted to HR, but the current "IsHR" permission also allows Admin. Should Admin also be allowed to correct attendance?
9| The current "AuditEvent" action choices do not include "CANCEL". Which audit action should be recorded when a leave request is cancelled?
10| Should attendance and leave records reference the "Employee" model or the "User" model? Confirm the relationship after the shared model definitions are available.

---

6. Implementation Boundaries

- This document defines rules and requirements; it does not claim that models, migrations, APIs, or tests have been implemented.
- Django model relationships and field definitions must match the actual shared "User" and "Employee" models.
- Database constraints and application-level validation must be selected according to the final model design and confirmed rules.
- Migrations and tests must be generated and executed in the project environment before implementation is reported as verified.
- Requirements marked Proposed or listed under Open Items must not be treated as approved company policy until confirmed by the team lead.
