
from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.employees.models import Employee
from apps.reports.navigation import menu_for_role

from .aggregates import get_employee_leave_dashboard
from .models import LeaveRequest, LeaveStatusHistory, LeaveType
from .services import (
    calculate_working_days,
    change_leave_status,
    create_leave_request,
)

PAGE_SIZE = 20
Status = LeaveRequest.Status


def _get_employee(user):
    """The Employee profile linked to this login, or None (e.g. an admin)."""
    return Employee.objects.filter(user=user).first()


def _base_context(request):
    """What dashboards/dashboard_base.html needs on every page."""
    role = getattr(request.user, "role", None)
    return {"role": role, "menu_items": menu_for_role(role, request.path)}


def _form_state(fields, values=None, errors=None):
    """Every field always has a value and an error key, so the templates
    never look up a missing key."""
    state_values = {name: "" for name in fields}
    state_values.update(values or {})
    state_errors = {name: "" for name in fields}
    state_errors.update(errors or {})
    return state_values, state_errors


def _flash_validation_error(request, exc):
    messages.error(request, " ".join(exc.messages))


def _working_days(leave):
    return calculate_working_days(leave.start_date, leave.end_date)


class LeaveListView(LoginRequiredMixin, View):
    """Leave requests. HR/Admin see everyone, employees see only their own."""

    template_name = "leave/leave_list.html"

    def get(self, request):
        user = request.user
        my_employee = _get_employee(user)

        requests = LeaveRequest.objects.select_related("employee", "leave_type")
        if not user.is_hr:
            requests = (
                requests.filter(employee=my_employee)
                if my_employee is not None
                else requests.none()
            )

        q = request.GET.get("q", "").strip()
        if q:
            requests = requests.filter(
                Q(employee__full_name__icontains=q)
                | Q(employee__employee_id__icontains=q)
            )
        status = request.GET.get("status", "").strip().upper()
        if status in Status.values:
            requests = requests.filter(status=status)
        else:
            status = ""

        page_obj = Paginator(requests, PAGE_SIZE).get_page(request.GET.get("page"))
        page_obj.object_list = [
            {
                "id": leave.pk,
                "employee": leave.employee.full_name,
                "leave_type": leave.leave_type.name,
                "start": leave.start_date,
                "end": leave.end_date,
                "days": _working_days(leave),
                "status": leave.get_status_display(),
                "status_code": leave.status,
            }
            for leave in page_obj.object_list
        ]

        context = _base_context(request)
        context.update(
            {
                "page_obj": page_obj,
                "q": q,
                "status": status,
                "status_choices": Status.choices,
                "can_apply": my_employee is not None,
            }
        )
        return render(request, self.template_name, context)


class LeaveApplyView(LoginRequiredMixin, View):
    """An employee applies for leave for themselves."""

    template_name = "leave/leave_apply.html"
    fields = ("leave_type", "start", "end", "reason")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.employee = _get_employee(request.user)
            if self.employee is None:
                messages.error(request, "Your account has no employee profile.")
                return redirect("leave_management:list")
        return super().dispatch(request, *args, **kwargs)

    def _render(self, request, values=None, errors=None):
        values, errors = _form_state(self.fields, values, errors)
        dashboard = get_employee_leave_dashboard(
            self.employee, timezone.localdate().year
        )
        context = _base_context(request)
        context.update(
            {
                "leave_types": [
                    (str(pk), name)
                    for pk, name in LeaveType.objects.filter(is_active=True)
                    .order_by("name")
                    .values_list("pk", "name")
                ],
                "balance": {
                    item["leave_type"]: item["remaining_days"]
                    for item in dashboard["balances"]
                },
                "values": values,
                "errors": errors,
            }
        )
        return render(request, self.template_name, context)

    def get(self, request):
        return self._render(request)

    def post(self, request):
        values = {name: request.POST.get(name, "").strip() for name in self.fields}
        errors = {}

        leave_type = None
        if not values["leave_type"]:
            errors["leave_type"] = "Select a leave type."
        else:
            try:
                leave_type = LeaveType.objects.filter(
                    pk=int(values["leave_type"]), is_active=True
                ).first()
            except ValueError:
                leave_type = None
            if leave_type is None:
                errors["leave_type"] = "Select a valid leave type."

        dates = {}
        for name, label in (("start", "start"), ("end", "end")):
            if not values[name]:
                errors[name] = f"Enter the {label} date."
                continue
            try:
                dates[name] = date.fromisoformat(values[name])
            except ValueError:
                errors[name] = "Enter a valid date."

        if not values["reason"]:
            errors["reason"] = "A reason is required."

        if errors:
            return self._render(request, values, errors)

        try:
            create_leave_request(
                self.employee,
                leave_type,
                dates["start"],
                dates["end"],
                reason=values["reason"],
            )
        except ValidationError as exc:
            _flash_validation_error(request, exc)
            return self._render(request, values)

        messages.success(request, "Leave request submitted.")
        return redirect("leave_management:list")


class LeaveReviewView(LoginRequiredMixin, View):
    """One leave request with its history. HR/Admin decide here, and the
    owner (or HR/Admin) can cancel a pending request.

    POST sends action=approve, action=reject or action=cancel.
    """

    template_name = "leave/leave_review.html"
    fields = ("remarks",)
    ACTIONS = {
        "approve": Status.APPROVED,
        "reject": Status.REJECTED,
        "cancel": Status.CANCELLED,
    }

    def _get_leave(self, request, pk):
        leave = get_object_or_404(
            LeaveRequest.objects.select_related("employee", "leave_type"), pk=pk
        )
        # Employees may only open their own request; 404 so we don't
        # reveal that other requests exist.
        if not request.user.is_hr and leave.employee.user_id != request.user.pk:
            raise Http404
        return leave

    def _render(self, request, leave, values=None, errors=None):
        values, errors = _form_state(self.fields, values, errors)
        user = request.user
        is_owner = leave.employee.user_id == user.pk
        pending = leave.status == Status.PENDING

        history = [
            {
                "status": LeaveRequest.Status(entry.new_status).label,
                "by": (
                    leave.employee.full_name
                    if entry.old_status == ""
                    else (str(entry.changed_by) if entry.changed_by else "System")
                ),
                "on": entry.changed_at,
                "remarks": entry.remarks,
            }
            for entry in LeaveStatusHistory.objects.filter(
                leave_request=leave
            ).select_related("changed_by")
        ]

        context = _base_context(request)
        context.update(
            {
                "leave": {
                    "id": leave.pk,
                    "employee": leave.employee.full_name,
                    "leave_type": leave.leave_type.name,
                    "start": leave.start_date,
                    "end": leave.end_date,
                    "days": _working_days(leave),
                    "reason": leave.reason,
                    "applied_on": timezone.localtime(leave.created_at).date(),
                    "status": leave.get_status_display(),
                    "status_code": leave.status,
                    "history": history,
                },
                "can_decide": pending and user.is_hr and not is_owner,
                "can_cancel": pending and (is_owner or user.is_hr),
                "values": values,
                "errors": errors,
            }
        )
        return render(request, self.template_name, context)

    def get(self, request, pk):
        return self._render(request, self._get_leave(request, pk))

    def post(self, request, pk):
        leave = self._get_leave(request, pk)
        action = request.POST.get("action", "")
        new_status = self.ACTIONS.get(action)
        remarks = request.POST.get("remarks", "").strip()

        if new_status is None:
            messages.error(request, "Unknown action.")
            return self._render(request, leave, {"remarks": remarks})

        if new_status in (Status.APPROVED, Status.REJECTED):
            if not request.user.is_hr:
                raise PermissionDenied
            if not remarks:
                return self._render(
                    request,
                    leave,
                    {"remarks": remarks},
                    {"remarks": "Remarks are required to approve or reject."},
                )

        try:
            change_leave_status(
                leave.pk, new_status, changed_by=request.user, remarks=remarks
            )
        except ValidationError as exc:
            _flash_validation_error(request, exc)
            return self._render(request, leave, {"remarks": remarks})

        # An approval turns into a rejection when the balance is too low,
        # so report what actually happened.
        leave.refresh_from_db()
        if new_status == Status.APPROVED and leave.status == Status.REJECTED:
            messages.warning(
                request,
                "Not enough leave balance, so the request was rejected.",
            )
        else:
            messages.success(request, f"Leave request {leave.get_status_display().lower()}.")
        return redirect("leave_management:list")