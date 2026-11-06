"""CSV exports of the real M3/M4 data. Admin/HR only."""
import csv
from datetime import date
from xml.sax.saxutils import escape

from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from django.http import Http404, HttpResponse
from django.views import View
from . import real_data
from .access import RoleRequiredMixin

# dataset name -> (function name in real_data, [(column header, row key), ...])
DATASETS = {
    "employees": ("get_employees", [
        ("Name", "name"), ("Email", "email"), ("Department", "department"),
        ("Designation", "designation"), ("Join date", "join_date"), ("Status", "status"),
    ]),
    "attendance": ("get_attendance", [
        ("Employee", "employee"), ("Date", "date"), ("Check in", "check_in"),
        ("Check out", "check_out"), ("Status", "status"),
    ]),
    "leaves": ("get_leaves", [
        ("Employee", "employee"), ("Leave type", "leave_type"), ("Start date", "start_date"),
        ("End date", "end_date"), ("Reason", "reason"), ("Status", "status"),
    ]),
}


def safe_cell(value):
    """Stop spreadsheet formula injection: a cell starting with = + - @ becomes text."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def get_dataset(name):
    if name not in DATASETS:
        raise Http404("Unknown dataset")
    func_name, columns = DATASETS[name]
    return getattr(real_data, func_name)(), columns


class ExportCSVView(RoleRequiredMixin, View):
    def get(self, request, dataset):
        rows, columns = get_dataset(dataset)
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{dataset}.csv"'
        response.write("\ufeff")  # so Excel reads the file as UTF-8
        writer = csv.writer(response)
        writer.writerow([header for header, _ in columns])
        for row in rows:
            writer.writerow([safe_cell(row.get(key)) for _, key in columns])
        return response

class ExportExcelView(RoleRequiredMixin, View):
    def get(self, request, dataset):
        rows, columns = get_dataset(dataset)
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = dataset.title()[:31]
        sheet.append([header for header, _ in columns])
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in rows:
            sheet.append([safe_cell(row.get(key)) for _, key in columns])
        for index, (header , key) in enumerate(columns, start=1):
            longest = max((len(str(r.get(key) or "")) for r in rows), default=0)
            sheet.column_dimensions[get_column_letter(index)].width = min(40, max(len(header), longest) + 2)
        buffer = BytesIO()
        workbook.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openpyxlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{dataset}.xlsx"'
        return response

class ExportPDFView(RoleRequiredMixin, View):
    def get(self, request, dataset):
        rows, columns = get_dataset(dataset)
        styles = getSampleStyleSheet()
        small = styles["BodyText"]
        small.fontSize = 8
        small.leading = 10

        def cell(value, bold=False):
            text = escape("" if value is None else str(value))
            return Paragraph(f"<b>{text}</b>" if bold else text, small)

        data = [[cell(header, bold=True) for header, _ in columns]]
        for row in rows:
            data.append([cell(row.get(key)) for _, key in columns])
        if not rows:
            data.append([cell("No data")] + [""] * (len(columns) - 1))

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))

        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer, pagesize=landscape(A4), title=f"{dataset.title()} report",
            leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        )
        document.build([
            Paragraph(f"{dataset.title()} report", styles["Title"]),
            Paragraph(f"Generated on {date.today().isoformat()}", styles["Normal"]),
            table,
        ])
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{dataset}.pdf"'
        return response