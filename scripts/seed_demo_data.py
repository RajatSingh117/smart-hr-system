"""
Smart HR & Employee Management System
Seed Demo Data Script (M1 Deliverable - Week 3 & 4)

Usage:
    python scripts/seed_demo_data.py
"""

import os
import sys
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

# -----------------------------------------------------------------------------
# 1. Django Environment Setup
# -----------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

User = get_user_model()

# Model imports (with fallback support for common field name conventions)
try:
    from apps.employees.models import Department, Employee, JobTitle
except ImportError:
    from employees.models import Department, Employee, JobTitle

try:
    from apps.attendance.models import Attendance
except ImportError:
    from attendance.models import Attendance

try:
    from apps.leave_management.models import LeaveRequest
except ImportError:
    from leave_management.models import LeaveRequest

try:
    from apps.payroll.models import (
        PayrollPeriod,
        SalaryComponent,
        Payslip,
        NotificationLog,
    )
except ImportError:
    from payroll.models import (
        PayrollPeriod,
        SalaryComponent,
        Payslip,
        NotificationLog,
    )


# -----------------------------------------------------------------------------
# 2. Seed Logic
# -----------------------------------------------------------------------------
@transaction.atomic
def seed_database():
    print("=" * 60)
    print("Starting Database Seeding for Smart HR System...")
    print("=" * 60)

    # 1. Clean existing records (Optional - maintains idempotent test runs)
    print("\n[1/6] Cleaning existing demo records...")
    Payslip.objects.all().delete()
    SalaryComponent.objects.all().delete()
    PayrollPeriod.objects.all().delete()
    NotificationLog.objects.all().delete()
    LeaveRequest.objects.all().delete()
    Attendance.objects.all().delete()
    Employee.objects.all().delete()
    JobTitle.objects.all().delete()
    Department.objects.all().delete()
    User.objects.filter(is_superuser=False).delete()

    # 2. Create Departments & Job Titles
    print("\n[2/6] Seeding Departments and Job Titles...")
    dept_data = {
        "Engineering": ["Senior Software Engineer", "Backend Developer", "DevOps Engineer", "QA Specialist"],
        "Human Resources": ["HR Lead", "Talent Acquisition Specialist", "People Operations Associate"],
        "Finance": ["Financial Analyst", "Accountant"],
        "Operations": ["Operations Manager", "Technical Support Specialist"],
    }

    dept_objs = {}
    title_objs = {}
    for d_name, titles in dept_data.items():
        dept = Department.objects.create(name=d_name, description=f"{d_name} Department")
        dept_objs[d_name] = dept
        for t_name in titles:
            title = JobTitle.objects.create(title=t_name, department=dept)
            title_objs[t_name] = title

    print(f"Created {len(dept_objs)} departments and {len(title_objs)} job titles.")

    # 3. Create Users and Employees (Admin, HR, and Staff)
    print("\n[3/6] Seeding Users and Employee Profiles...")
    demo_people = [
        # Admin
        {
            "username": "admin_rajat",
            "email": "admin@smarthr.local",
            "first_name": "Rajat",
            "last_name": "Singh",
            "role": "ADMIN",
            "dept": "Engineering",
            "title": "DevOps Engineer",
            "salary": Decimal("125000.00"),
        },
        # HR
        {
            "username": "hr_priya",
            "email": "priya.hr@smarthr.local",
            "first_name": "Priya",
            "last_name": "Sharma",
            "role": "HR",
            "dept": "Human Resources",
            "title": "HR Lead",
            "salary": Decimal("85000.00"),
        },
        # Regular Employees
        {
            "username": "emp_aarav",
            "email": "aarav.patel@smarthr.local",
            "first_name": "Aarav",
            "last_name": "Patel",
            "role": "EMPLOYEE",
            "dept": "Engineering",
            "title": "Senior Software Engineer",
            "salary": Decimal("110000.00"),
        },
        {
            "username": "emp_sneha",
            "email": "sneha.verma@smarthr.local",
            "first_name": "Sneha",
            "last_name": "Verma",
            "role": "EMPLOYEE",
            "dept": "Engineering",
            "title": "Backend Developer",
            "salary": Decimal("75000.00"),
        },
        {
            "username": "emp_rohit",
            "email": "rohit.gupta@smarthr.local",
            "first_name": "Rohit",
            "last_name": "Gupta",
            "role": "EMPLOYEE",
            "dept": "Finance",
            "title": "Accountant",
            "salary": Decimal("65000.00"),
        },
        {
            "username": "emp_ananya",
            "email": "ananya.iyer@smarthr.local",
            "first_name": "Ananya",
            "last_name": "Iyer",
            "role": "EMPLOYEE",
            "dept": "Operations",
            "title": "Technical Support Specialist",
            "salary": Decimal("55000.00"),
        },
    ]

    employees = []
    hr_user = None

    for idx, p in enumerate(demo_people, start=101):
        user = User.objects.create_user(
            username=p["username"],
            email=p["email"],
            password="DemoPassword123!",
            first_name=p["first_name"],
            last_name=p["last_name"],
        )
        if hasattr(user, "role"):
            user.role = p["role"]
            user.save()

        if p["role"] == "HR" and not hr_user:
            hr_user = user

        emp = Employee.objects.create(
            user=user,
            employee_id=f"EMP{idx}",
            department=dept_objs[p["dept"]],
            job_title=title_objs[p["title"]],
            employment_status="ACTIVE",
            date_of_joining=date(2025, 1, 15) + timedelta(days=idx * 2),
            phone_number=f"+91 98765 43{idx}",
        )
        # Store metadata for payroll step
        emp._base_salary = p["salary"]
        employees.append(emp)

    print(f"Created {len(employees)} user accounts and linked employee profiles.")

    # 4. Seed Attendance Records (Previous 30 Days)
    print("\n[4/6] Seeding Attendance Records (Last 30 Days)...")
    today = date.today()
    start_date = today - timedelta(days=30)
    attendance_count = 0

    statuses = ["PRESENT", "PRESENT", "PRESENT", "PRESENT", "LATE", "HALF_DAY", "ABSENT"]

    for emp in employees:
        curr = start_date
        while curr <= today:
            # Exclude weekends (Saturday = 5, Sunday = 6)
            if curr.weekday() < 5:
                chosen_status = random.choice(statuses)

                if chosen_status == "PRESENT":
                    check_in = time(9, random.randint(0, 15))
                    check_out = time(18, random.randint(0, 30))
                elif chosen_status == "LATE":
                    check_in = time(10, random.randint(15, 45))
                    check_out = time(18, 30)
                elif chosen_status == "HALF_DAY":
                    check_in = time(9, 30)
                    check_out = time(13, 30)
                else:  # ABSENT
                    check_in = None
                    check_out = None

                # Build datetime objects if check-in exists
                dt_in = timezone.make_aware(datetime.combine(curr, check_in)) if check_in else None
                dt_out = timezone.make_aware(datetime.combine(curr, check_out)) if check_out else None

                Attendance.objects.create(
                    employee=emp,
                    date=curr,
                    check_in=dt_in,
                    check_out=dt_out,
                    status=chosen_status,
                )
                attendance_count += 1
            curr += timedelta(days=1)

    print(f"Created {attendance_count} attendance punch records.")

    # 5. Seed Leave Requests & Status Workflow
    print("\n[5/6] Seeding Leave Requests and Status Transitions...")
    leave_scenarios = [
        ("CASUAL", 18, 19, "PENDING", None, None),
        ("SICK", 25, 26, "APPROVED", hr_user, "Medical certificate submitted and verified."),
        ("PAID", 10, 12, "APPROVED", hr_user, "Annual leave planned in advance."),
        ("CASUAL", 5, 5, "REJECTED", hr_user, "Department team is on a critical release freeze."),
    ]

    leave_count = 0
    for emp in employees:
        for l_type, start_day, end_day, status, approver, remarks in leave_scenarios:
            req = LeaveRequest.objects.create(
                employee=emp,
                leave_type=l_type,
                start_date=date(today.year, today.month, min(start_day, 28)),
                end_date=date(today.year, today.month, min(end_day, 28)),
                reason=f"Demo reason for {l_type.lower()} leave request.",
                status=status,
                approved_by=approver,
                approver_remarks=remarks or "",
            )
            leave_count += 1

            # Log corresponding notification if approved or rejected
            if status in ["APPROVED", "REJECTED"]:
                NotificationLog.objects.create(
                    recipient=emp.user.email,
                    subject=f"Leave Request {status.capitalize()}: {req.leave_type}",
                    message=f"Your leave request for {req.start_date} has been {status.lower()}.\nRemarks: {remarks}",
                    status="SUCCESS",
                )

    print(f"Created {leave_count} leave requests with corresponding audit/notification records.")

    # 6. Seed Payroll Periods, Salary Components, and Payslips
    print("\n[6/6] Seeding Payroll Periods, Components, and Generated Payslips...")
    # Seed 2 payroll periods: Previous Month and Current Month
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    periods = [
        PayrollPeriod.objects.create(
            name=last_month_start.strftime("%B %Y"),
            start_date=last_month_start,
            end_date=last_month_end,
            is_closed=True,
        ),
        PayrollPeriod.objects.create(
            name=first_of_this_month.strftime("%B %Y"),
            start_date=first_of_this_month,
            end_date=today,
            is_closed=False,
        ),
    ]

    payslip_count = 0
    for emp in employees:
        base = emp._base_salary
        hra = (base * Decimal("0.20")).quantize(Decimal("0.01"))
        special_allowance = (base * Decimal("0.10")).quantize(Decimal("0.01"))
        pf_deduction = (base * Decimal("0.12")).quantize(Decimal("0.01"))
        tax_deduction = (base * Decimal("0.08")).quantize(Decimal("0.01"))

        # Configure salary components for employee
        comp_data = [
            ("Basic Salary", "EARNING", base),
            ("House Rent Allowance (HRA)", "EARNING", hra),
            ("Special Allowance", "EARNING", special_allowance),
            ("Provident Fund (PF)", "DEDUCTION", pf_deduction),
            ("Income Tax (TDS)", "DEDUCTION", tax_deduction),
        ]

        for c_name, c_type, amount in comp_data:
            SalaryComponent.objects.create(
                employee=emp,
                name=c_name,
                component_type=c_type,
                amount=amount,
            )

        # Generate closed payslips for previous month
        gross = base + hra + special_allowance
        total_deductions = pf_deduction + tax_deduction
        net = gross - total_deductions

        Payslip.objects.create(
            employee=emp,
            payroll_period=periods[0],
            gross_salary=gross,
            total_deductions=total_deductions,
            net_salary=net,
            status="GENERATED",
            pdf_file_path=f"payslips/{periods[0].name.replace(' ', '_')}_{emp.employee_id}.pdf",
        )
        payslip_count += 1

        NotificationLog.objects.create(
            recipient=emp.user.email,
            subject=f"Payslip Available for {periods[0].name}",
            message=f"Dear {emp.user.first_name}, your payslip for {periods[0].name} has been generated.",
            status="SUCCESS",
        )

    print(f"Created {len(periods)} payroll periods and {payslip_count} finalized payslip records.")
    print("\n" + "=" * 60)
    print("SUCCESS: Demo data seeding complete!")
    print("Admin Login:    admin@smarthr.local  / DemoPassword123!")
    print("HR Login:       priya.hr@smarthr.local / DemoPassword123!")
    print("Employee Login: aarav.patel@smarthr.local / DemoPassword123!")
    print("=" * 60)


if __name__ == "__main__":
    seed_database()