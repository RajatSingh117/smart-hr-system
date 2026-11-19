from collections import Counter
from django.views.generic import TemplateView

from apps.attendance.models import Attendance
from apps.employees.models import Department, Employee
from apps.employees.queries import (
    get_department_employee_counts,
    get_headcount_summary,
    get_job_title_distribution,
    get_status_distribution,
)

from . import real_data
from .access import RoleRequiredMixin, user_role
from .navigation import menu_for_role


def _split(counter):
    labels = sorted(counter)
    return labels, [counter[label] for label in labels]


class ChartsPage(RoleRequiredMixin, TemplateView):
    template_name = "reports/charts.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        role = user_role(self.request.user)
        context["menu_items"] = menu_for_role(role, self.request.path, valid_only=True)
        context["role"] = role

        # 1. Departments breakdown using real_data (preserves test mock compatibility)
        by_department = Counter(
            e["department"] or "No department" for e in real_data.get_employees()
        )
        dept_labels, dept_values = _split(by_department)

        # 2. Attendance trends (Present days per month)
        by_month = Counter(
            str(a["date"])[:7]
            for a in real_data.get_attendance()
            if str(a["status"]).lower() == "present"
        )
        month_labels, month_values = _split(by_month)

        # 3. Leave statistics (by status)
        by_status = Counter(
            str(lv["status"]).title() for lv in real_data.get_leaves()
        )
        leave_labels, leave_values = _split(by_status)

        # Real headcount and KPIs
        try:
            headcount = get_headcount_summary()
            total_emp = headcount["total"]
            active_emp = headcount["active"]
            on_leave_emp = headcount["on_leave"]
            term_emp = headcount["terminated"]
            total_dept = Department.objects.filter(is_active=True).count()
            total_att = Attendance.objects.count()
        except Exception:
            total_emp = len(dept_values)
            active_emp = total_emp
            on_leave_emp = 0
            term_emp = 0
            total_dept = len(dept_labels)
            total_att = sum(month_values)

        context["kpis"] = {
            "total_employees": total_emp,
            "active_employees": active_emp,
            "on_leave": on_leave_emp,
            "terminated": term_emp,
            "total_departments": total_dept,
            "total_attendance": total_att,
        }

        # 4. Employment status distribution
        try:
            status_dist = get_status_distribution()
            status_labels = ["Active", "On Leave", "Terminated"]
            status_values = [
                status_dist.get(Employee.EmploymentStatus.ACTIVE.value, 0),
                status_dist.get(Employee.EmploymentStatus.ON_LEAVE.value, 0),
                status_dist.get(Employee.EmploymentStatus.TERMINATED.value, 0),
            ]
        except Exception:
            status_labels, status_values = [], []

        # 5. Job title distribution
        try:
            job_counts = get_job_title_distribution(active_only=False, include_empty=False)
            job_labels = [j["title"] for j in job_counts]
            job_values = [j["count"] for j in job_counts]
        except Exception:
            job_labels, job_values = [], []

        # 6. Salary aggregation by department (if authorized)
        can_see_salary = False
        salary_labels, salary_values = [], []
        user = getattr(self.request, "user", None)
        if user and hasattr(user, "can_access_payroll") and user.can_access_payroll():
            can_see_salary = True
            try:
                dept_counts = get_department_employee_counts(active_only=False, include_empty=False)
                for d in dept_counts:
                    sal = float(d.get("total_salary", 0) or 0)
                    if sal > 0:
                        salary_labels.append(d["name"])
                        salary_values.append(sal)
            except Exception:
                pass

        context["can_see_salary"] = can_see_salary
        context["chart_data"] = {
            "departments": {"labels": dept_labels, "values": dept_values},
            "status": {"labels": status_labels, "values": status_values},
            "job_titles": {"labels": job_labels, "values": job_values},
            "attendance": {"labels": month_labels, "values": month_values},
            "leaves": {"labels": leave_labels, "values": leave_values},
            "salaries": {"labels": salary_labels, "values": salary_values},
        }
        return context
