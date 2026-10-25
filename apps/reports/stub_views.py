from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import Http404

from . import stubs


class StubListView(LoginRequiredMixin, TemplateView):
    """Base for list previews: search, status filter and pagination."""
    items = []
    search_fields = ("name",)
    context_name = "items"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = self.request.GET.get("q", "")
        status = self.request.GET.get("status", "")
        filtered = stubs.filter_items(self.items, q, status, self.search_fields)
        page_obj = stubs.paginate(self.request, filtered)
        ctx.update({"page_obj": page_obj, self.context_name: page_obj, "q": q, "status": status})
        return ctx


class EmployeeListPreview(StubListView):
    template_name = "employees/employee_list.html"
    items = stubs.EMPLOYEES
    search_fields = ("name", "email", "department")
    context_name = "employees"


class DepartmentListPreview(StubListView):
    template_name = "employees/department_list.html"
    items = stubs.DEPARTMENTS
    context_name = "departments"


class AttendanceListPreview(StubListView):
    template_name = "attendance/attendance_list.html"
    items = stubs.ATTENDANCE
    search_fields = ("employee",)
    context_name = "records"


class LeaveListPreview(StubListView):
    template_name = "leave/leave_list.html"
    items = stubs.LEAVES
    search_fields = ("employee", "leave_type")
    context_name = "leaves"


class MonthlySummaryPreview(LoginRequiredMixin, TemplateView):
    template_name = "attendance/monthly_summary.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["summary"] = stubs.MONTHLY_SUMMARY
        return ctx


class SimplePreview(LoginRequiredMixin, TemplateView):
    """Form pages that just need to render (no data)."""


class StubObjectView(LoginRequiredMixin, TemplateView):
    """Detail/edit/review previews: picks one stub row by id."""
    items = []
    context_name = "object"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = next((i for i in self.items if i["id"] == self.kwargs["pk"]), None)
        if obj is None:
            raise Http404("Stub row not found")
        ctx[self.context_name] = obj
        return ctx


class EmployeeDetailPreview(StubObjectView):
    template_name = "employees/employee_detail.html"
    items = stubs.EMPLOYEES
    context_name = "employee"


class EmployeeEditPreview(StubObjectView):
    template_name = "employees/employee_form.html"
    items = stubs.EMPLOYEES
    context_name = "employee"


class LeaveReviewPreview(StubObjectView):
    template_name = "leave/leave_review.html"
    items = stubs.LEAVES
    context_name = "leave"