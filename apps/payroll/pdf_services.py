import uuid
import logging
from io import BytesIO

from django.core.files.base import ContentFile
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .models import Payslip
from .tasks import send_notification_task


logger = logging.getLogger(__name__)


def generate_payslip_pdf(payroll_record):
    """
    Generate a PDF payslip for a payroll record.

    Returns:
        Payslip: The generated or updated payslip record.
    """

    payslip = None

    try:
        # Create or retrieve the payslip record.
        payslip, _ = Payslip.objects.get_or_create(
            payroll_record=payroll_record,
            defaults={
                "payslip_number": f"PAY-{uuid.uuid4().hex[:10].upper()}",
                "status": Payslip.Status.FAILED,
            },
        )

        # Create an in-memory PDF.
        buffer = BytesIO()

        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "PayslipTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=18,
            spaceAfter=20,
        )

        normal_style = styles["Normal"]

        elements = []

        # Title
        elements.append(
            Paragraph("EMPLOYEE PAYSLIP", title_style)
        )

        elements.append(Spacer(1, 10))

        employee = payroll_record.employee
        period = payroll_record.payroll_period

        # Employee details
        employee_data = [
            ["Employee ID", str(employee.employee_id)],
            ["Employee Name", str(employee.full_name)],
            ["Payroll Period", str(period.name)],
            ["Period Start", str(period.start_date)],
            ["Period End", str(period.end_date)],
            ["Payslip Number", payslip.payslip_number],
            [
                "Generated On",
                timezone.localtime().strftime("%d-%m-%Y"),
            ],
        ]

        employee_table = Table(
            employee_data,
            colWidths=[55 * mm, 100 * mm],
        )

        employee_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 8),
            ])
        )

        elements.append(employee_table)
        elements.append(Spacer(1, 25))

        # Salary details
        salary_data = [
            ["Description", "Amount"],
            [
                "Basic Salary",
                f"Rs. {payroll_record.basic_salary:,.2f}",
            ],
            [
                "Total Allowances",
                f"Rs. {payroll_record.total_allowances:,.2f}",
            ],
            [
                "Gross Salary",
                f"Rs. {payroll_record.gross_salary:,.2f}",
            ],
            [
                "Total Deductions",
                f"Rs. {payroll_record.total_deductions:,.2f}",
            ],
            [
                "Net Salary",
                f"Rs. {payroll_record.net_salary:,.2f}",
            ],
        ]

        salary_table = Table(
            salary_data,
            colWidths=[90 * mm, 65 * mm],
        )

        salary_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 10),
            ])
        )

        elements.append(salary_table)
        elements.append(Spacer(1, 30))

        elements.append(
            Paragraph(
                "This is a computer-generated payslip.",
                normal_style,
            )
        )

        # Build the PDF.
        document.build(elements)

        pdf_content = buffer.getvalue()
        buffer.close()

        # Save the generated PDF.
        filename = f"{payslip.payslip_number}.pdf"

        payslip.pdf_file.save(
            filename,
            ContentFile(pdf_content),
            save=False,
        )

        # Mark payslip as generated.
        payslip.status = Payslip.Status.GENERATED
        payslip.save()

    except Exception:
        # Mark as failed only if PDF generation or saving fails.
        if payslip is not None:
            payslip.status = Payslip.Status.FAILED
            payslip.save(update_fields=["status"])

        logger.exception(
            "Payslip PDF generation failed for payroll record ID %s",
            payroll_record.pk,
        )
        raise

        # Queue notification only after successful PDF generation.
    # Notification failure must not change the payslip status.
    employee = payroll_record.employee
    period = payroll_record.payroll_period

    if employee.email:
        try:
            send_notification_task.delay(
                notification_name="payslip_ready",
                recipient=employee.email,
                context={
                    "employee_name": employee.full_name,
                    "payroll_period": period.name,
                    "payslip_number": payslip.payslip_number,
                    "net_salary": (
                        f"Rs. {payroll_record.net_salary:,.2f}"
                    ),
                },
                subject="Your Payslip Is Ready",
            )

        except Exception:
            logger.exception(
                "Failed to queue payslip notification for payroll "
                "record ID %s",
                payroll_record.pk,
            )
    return payslip
