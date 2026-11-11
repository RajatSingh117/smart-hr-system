
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.employees.models import Employee
from apps.reports.navigation import menu_for_role

from .aggregates import get_monthly_attendance_by_employee
from .models import Attendance
from .services import check_in, check_out, correct_attendance

PAGE_SIZE = 20


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


class AttendanceListView(LoginRequiredMixin, View):
    """Attendance records. HR/Admin see everyone, employees see only
    their own. Also shows today's check-in/out card."""

    template_name = "attendance/attendance_list.html"

    def get(self, request):
        user = request.user
        my_employee = _get_employee(user)

        records = Attendance.objects.select_related("employee")
        if not user.is_hr:
            records = (
                records.filter(employee=my_employee)
                if my_employee is not None
                else records.none()
            )

        q = request.GET.get("q", "").strip()
        if q:
            records = records.filter(
                Q(employee__full_name__icontains=q)
                | Q(employee__employee_id__icontains=q)
            )
        status = request.GET.get("status", "").strip().upper()
        if status in Attendance.Status.values:
            records = records.filter(status=status)
        else:
            status = ""

        page_obj = Paginator(records, PAGE_SIZE).get_page(request.GET.get("page"))
        page_obj.object_list = [
            {
                "id": record.pk,
                "date": record.date,
                "employee": record.employee.full_name,
                "check_in": record.check_in,
                "check_out": record.check_out,
                "status": record.get_status_display(),
                "status_code": record.status,
            }
            for record in page_obj.object_list
        ]

        today_record = None
        if my_employee is not None:
            today_record = Attendance.objects.filter(
                employee=my_employee, date=timezone.localdate()
            ).first()

        context = _base_context(request)
        context.update(
            {
                "page_obj": page_obj,
                "q": q,
                "status": status,
                "status_choices": Attendance.Status.choices,
                "has_employee_profile": my_employee is not None,
                "today_record": today_record,
                "checked_in_today": bool(today_record and today_record.check_in),
                "checked_out_today": bool(today_record and today_record.check_out),
                "can_correct": user.role == User.Role.HR,
            }
        )
        return render(request, self.template_name, context)


@method_decorator(require_POST, name="dispatch")
class AttendanceCheckView(LoginRequiredMixin, View):
    """POST only. The buttons on the list page send action=check_in or
    action=check_out."""

    def post(self, request):
        employee = _get_employee(request.user)
        action = request.POST.get("action")

        if employee is None:
            messages.error(request, "Your account has no employee profile.")
            return redirect("attendance:list")

        try:
            if action == "check_in":
                check_in(employee, request.user)
                messages.success(request, "Checked in.")
            elif action == "check_out":
                check_out(employee, request.user)
                messages.success(request, "Checked out.")
            else:
                messages.error(request, "Unknown action.")
        except ValidationError as exc:
            _flash_validation_error(request, exc)
        return redirect("attendance:list")


class MonthlySummaryView(LoginRequiredMixin, View):
    """Per-employee counts for one month (?month=YYYY-MM). HR/Admin see
    every employee, employees see only themselves."""

    template_name = "attendance/monthly_summary.html"

    def get(self, request):
        user = request.user
        today = timezone.localdate()
        year, month = today.year, today.month

        month_param = request.GET.get("month", "").strip()
        if month_param:
            try:
                parsed = datetime.strptime(month_param, "%Y-%m")
                year, month = parsed.year, parsed.month
            except ValueError:
                messages.error(request, "Choose a valid month.")

        if user.is_hr:
            summary = get_monthly_attendance_by_employee(year, month)
        else:
            my_employee = _get_employee(user)
            summary = (
                get_monthly_attendance_by_employee(year, month, employee=my_employee)
                if my_employee is not None
                else []
            )

        keys = {status: status.lower() for status in Attendance.Status.values}
        rows = [
            {"employee": item["employee"]}
            | {keys[status]: item[status] for status in keys}
            for item in summary
        ]
        totals = {key: sum(row[key] for row in rows) for key in keys.values()}

        context = _base_context(request)
        context.update(
            {"month": f"{year}-{month:02d}", "rows": rows, "totals": totals}
        )
        return render(request, self.template_name, context)


class AttendanceCorrectionView(LoginRequiredMixin, View):
    """HR corrects one employee's record for one date.

    Only the HR role may correct attendance, matching
    services.correct_attendance (Admin is refused there too).
    """

    template_name = "attendance/correction_form.html"
    fields = ("employee", "date", "status", "reason")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != User.Role.HR:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def _render(self, request, values=None, errors=None):
        values, errors = _form_state(self.fields, values, errors)
        context = _base_context(request)
        context.update(
            {
                "people": [
                    (str(pk), label)
                    for pk, label in Employee.objects.order_by("full_name")
                    .values_list("pk", "full_name")
                ],
                "statuses": Attendance.Status.choices,
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

        employee = None
        if not values["employee"]:
            errors["employee"] = "Select an employee."
        else:
            try:
                employee = Employee.objects.filter(pk=int(values["employee"])).first()
            except ValueError:
                employee = None
            if employee is None:
                errors["employee"] = "Select a valid employee."

        day = None
        if not values["date"]:
            errors["date"] = "Enter the date to correct."
        else:
            try:
                day = date.fromisoformat(values["date"])
            except ValueError:
                errors["date"] = "Enter a valid date."

        if values["status"] not in Attendance.Status.values:
            errors["status"] = "Select a valid status."
        if not values["reason"]:
            errors["reason"] = "A reason is required."

        record = None
        if employee is not None and day is not None:
            record = Attendance.objects.filter(employee=employee, date=day).first()
            if record is None:
                errors["date"] = "No attendance record exists for this employee on that date."

        if errors:
            return self._render(request, values, errors)

        try:
            correct_attendance(
                record.pk,
                request.user,
                status=values["status"],
                reason=values["reason"],
            )
        except ValidationError as exc:
            _flash_validation_error(request, exc)
            return self._render(request, values)

        messages.success(request, "Attendance corrected.")
        return redirect("attendance:list")