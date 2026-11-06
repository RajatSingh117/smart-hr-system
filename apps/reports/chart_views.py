from collections import Counter

from django.views.generic import TemplateView

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
        context["menu_items"] = menu_for_role(user_role(self.request.user), self.request.path)
        by_department = Counter(
            e["department"] or "No department" for e in real_data.get_employees()
        )
        dept_labels, dept_values = _split(by_department)

        by_month = Counter(
            str(a["date"])[:7]
            for a in real_data.get_attendance()
            if str(a["status"]).lower() == "present"
        )
        month_labels, month_values = _split(by_month)

        by_status = Counter(
            str(lv["status"]).title() for lv in real_data.get_leaves()
        )
        leave_labels, leave_values = _split(by_status)

        context["chart_data"] = {
            "departments": {"labels": dept_labels, "values": dept_values},
            "attendance": {"labels": month_labels, "values": month_values},
            "leaves": {"labels": leave_labels, "values": leave_values},
        }
        return context