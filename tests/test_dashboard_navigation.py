from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.employees.models import Department, Employee
from apps.reports.navigation import menu_for_role


class DashboardNavigationTests(TestCase):
    def setUp(self):
        self.password = "Secr3tP@ssw0rd!"

        # Admin user
        self.admin_user = User.objects.create_user(
            email="admin@test.com",
            password=self.password,
            role=User.Role.ADMIN,
            first_name="Admin",
            last_name="User",
        )

        # HR user
        self.hr_user = User.objects.create_user(
            email="hr@test.com",
            password=self.password,
            role=User.Role.HR,
            first_name="HR",
            last_name="User",
        )

        # Employee user + Employee profile
        self.emp_user = User.objects.create_user(
            email="employee@test.com",
            password=self.password,
            role=User.Role.EMPLOYEE,
            first_name="Emp",
            last_name="User",
        )
        self.department = Department.objects.create(
            name="Engineering",
            description="Tech team",
            is_active=True,
        )
        self.employee_profile = Employee.objects.create(
            user=self.emp_user,
            employee_id="EMP001",
            full_name="Emp User",
            email="employee@test.com",
            department=self.department,
            joining_date=date(2025, 1, 1),
        )

    def test_login_redirect_for_all_roles(self):
        """Verify login redirects users to their appropriate role dashboard."""
        client = Client()

        # Admin login
        resp = client.post(reverse("accounts:login"), {
            "email": "admin@test.com",
            "password": self.password,
        })
        self.assertRedirects(resp, reverse("admin-dashboard"))

        # HR login
        client.logout()
        resp = client.post(reverse("accounts:login"), {
            "email": "hr@test.com",
            "password": self.password,
        })
        self.assertRedirects(resp, reverse("hr-dashboard"))

        # Employee login
        client.logout()
        resp = client.post(reverse("accounts:login"), {
            "email": "employee@test.com",
            "password": self.password,
        })
        self.assertRedirects(resp, reverse("my-dashboard"))

    def test_dashboard_redirect_view_for_all_roles(self):
        """Verify accounts:dashboard_redirect redirects according to role."""
        client = Client()

        # Admin
        client.force_login(self.admin_user)
        resp = client.get(reverse("accounts:dashboard_redirect"))
        self.assertRedirects(resp, reverse("admin-dashboard"))

        # HR
        client.force_login(self.hr_user)
        resp = client.get(reverse("accounts:dashboard_redirect"))
        self.assertRedirects(resp, reverse("hr-dashboard"))

        # Employee
        client.force_login(self.emp_user)
        resp = client.get(reverse("accounts:dashboard_redirect"))
        self.assertRedirects(resp, reverse("my-dashboard"))

    def test_admin_sidebar_visibility(self):
        """Admin dashboard displays all management modules, My Profile, and Django Admin."""
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("admin-dashboard"))
        self.assertEqual(resp.status_code, 200)

        menu_items = resp.context["menu_items"]
        labels = [item["label"] for item in menu_items]

        # Must include all management modules
        self.assertIn("Dashboard", labels)
        self.assertIn("Employees", labels)
        self.assertIn("Departments", labels)
        self.assertIn("Job Titles", labels)
        self.assertIn("Attendance", labels)
        self.assertIn("Leave", labels)
        self.assertIn("Reports", labels)
        self.assertIn("Charts", labels)
        self.assertIn("My Profile", labels)
        self.assertIn("Django Admin", labels)

        # Must NOT include un-implemented modules
        self.assertNotIn("Payroll", labels)
        self.assertNotIn("Audit Log", labels)
        self.assertNotIn("My Payslips", labels)

        # No dead "#" links
        for item in menu_items:
            self.assertNotEqual(item["url"], "#")
            self.assertTrue(item["url"].startswith("/"))

    def test_hr_sidebar_visibility(self):
        """HR dashboard displays management modules and My Profile, but not Admin-only links."""
        client = Client()
        client.force_login(self.hr_user)
        resp = client.get(reverse("hr-dashboard"))
        self.assertEqual(resp.status_code, 200)

        menu_items = resp.context["menu_items"]
        labels = [item["label"] for item in menu_items]

        # Must include HR accessible modules
        self.assertIn("Dashboard", labels)
        self.assertIn("Employees", labels)
        self.assertIn("Departments", labels)
        self.assertIn("Job Titles", labels)
        self.assertIn("Attendance", labels)
        self.assertIn("Leave", labels)
        self.assertIn("Reports", labels)
        self.assertIn("Charts", labels)
        self.assertIn("My Profile", labels)

        # Must NOT include Admin-only or un-implemented modules
        self.assertNotIn("Django Admin", labels)
        self.assertNotIn("Audit Log", labels)
        self.assertNotIn("Payroll", labels)
        self.assertNotIn("My Payslips", labels)

        # No dead "#" links
        for item in menu_items:
            self.assertNotEqual(item["url"], "#")
            self.assertTrue(item["url"].startswith("/"))

    def test_employee_sidebar_visibility(self):
        """Employee dashboard displays only permitted self-service modules."""
        client = Client()
        client.force_login(self.emp_user)
        resp = client.get(reverse("my-dashboard"))
        self.assertEqual(resp.status_code, 200)

        menu_items = resp.context["menu_items"]
        labels = [item["label"] for item in menu_items]

        # Permitted self-service modules
        self.assertIn("Dashboard", labels)
        self.assertIn("Attendance", labels)
        self.assertIn("Leave", labels)
        self.assertIn("My Profile", labels)

        # Prohibited management modules
        self.assertNotIn("Employees", labels)
        self.assertNotIn("Departments", labels)
        self.assertNotIn("Reports", labels)
        self.assertNotIn("Charts", labels)
        self.assertNotIn("Django Admin", labels)
        self.assertNotIn("Audit Log", labels)
        self.assertNotIn("Payroll", labels)
        self.assertNotIn("My Payslips", labels)

        # No dead "#" links
        for item in menu_items:
            self.assertNotEqual(item["url"], "#")
            self.assertTrue(item["url"].startswith("/"))

    def test_all_linked_routes_accessible_for_admin(self):
        """Every link in Admin sidebar opens an existing functional page with 200 OK."""
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("admin-dashboard"))
        menu_items = resp.context["menu_items"]

        for item in menu_items:
            url = item["url"]
            res = client.get(url, follow=True)
            self.assertEqual(
                res.status_code, 200,
                f"Failed to load menu URL for {item['label']}: {url} (status: {res.status_code})"
            )

    def test_all_linked_routes_accessible_for_hr(self):
        """Every link in HR sidebar opens an existing functional page with 200 OK."""
        client = Client()
        client.force_login(self.hr_user)
        resp = client.get(reverse("hr-dashboard"))
        menu_items = resp.context["menu_items"]

        for item in menu_items:
            url = item["url"]
            res = client.get(url, follow=True)
            self.assertEqual(
                res.status_code, 200,
                f"Failed to load menu URL for {item['label']}: {url} (status: {res.status_code})"
            )

    def test_all_linked_routes_accessible_for_employee(self):
        """Every link in Employee sidebar opens an existing functional page with 200 OK."""
        client = Client()
        client.force_login(self.emp_user)
        resp = client.get(reverse("my-dashboard"))
        menu_items = resp.context["menu_items"]

        for item in menu_items:
            url = item["url"]
            res = client.get(url, follow=True)
            self.assertEqual(
                res.status_code, 200,
                f"Failed to load menu URL for {item['label']}: {url} (status: {res.status_code})"
            )

    def test_employee_permission_denied_on_management_routes(self):
        """Employee cannot access management or admin dashboards/pages."""
        client = Client()
        client.force_login(self.emp_user)

        self.assertEqual(client.get(reverse("admin-dashboard")).status_code, 403)
        self.assertEqual(client.get(reverse("hr-dashboard")).status_code, 403)
        self.assertEqual(client.get(reverse("employees:list")).status_code, 403)
        self.assertEqual(client.get(reverse("employees:department_list")).status_code, 403)
        self.assertEqual(client.get(reverse("employees:job_title_list")).status_code, 403)
        self.assertEqual(client.get(reverse("reports:exports")).status_code, 403)
        self.assertEqual(client.get(reverse("reports:charts")).status_code, 403)

    def test_sidebar_active_item_accuracy(self):
        """Verify that viewing Job Titles highlights Job Titles and NOT Departments."""
        client = Client()
        client.force_login(self.admin_user)

        # 1. Job Titles Page
        resp = client.get(reverse("employees:job_title_list"))
        self.assertEqual(resp.status_code, 200)
        menu_items = resp.context["menu_items"]
        active_labels = [item["label"] for item in menu_items if item.get("active")]
        self.assertEqual(active_labels, ["Job Titles"], f"Expected only ['Job Titles'] active, got: {active_labels}")

        # 2. Departments Page
        resp = client.get(reverse("employees:department_list"))
        self.assertEqual(resp.status_code, 200)
        menu_items = resp.context["menu_items"]
        active_labels = [item["label"] for item in menu_items if item.get("active")]
        self.assertEqual(active_labels, ["Departments"], f"Expected only ['Departments'] active, got: {active_labels}")

        # 3. Employees Page
        resp = client.get(reverse("employees:list"))
        self.assertEqual(resp.status_code, 200)
        menu_items = resp.context["menu_items"]
        active_labels = [item["label"] for item in menu_items if item.get("active")]
        self.assertEqual(active_labels, ["Employees"], f"Expected only ['Employees'] active, got: {active_labels}")

        # 4. Charts Page
        resp = client.get(reverse("reports:charts"))
        self.assertEqual(resp.status_code, 200)
        menu_items = resp.context["menu_items"]
        active_labels = [item["label"] for item in menu_items if item.get("active")]
        self.assertEqual(active_labels, ["Charts"], f"Expected only ['Charts'] active, got: {active_labels}")

    def test_login_page_enterprise_ui(self):
        """Verify login page renders enterprise split-screen structure and controls."""
        client = Client()
        resp = client.get(reverse("accounts:login"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("auth-split-wrapper", content)
        self.assertIn("auth-brand-side", content)
        self.assertIn("auth-form-side", content)
        self.assertIn("btn-password-toggle", content)
        self.assertIn("btn-theme-toggle", content)

    def test_job_title_empty_state_and_table(self):
        """Verify empty state component and table rendering for Job Titles."""
        from apps.employees.models import JobTitle
        client = Client()
        client.force_login(self.admin_user)

        # 1. Empty state
        JobTitle.objects.all().delete()
        resp = client.get(reverse("employees:job_title_list"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("hr-empty-state", content)
        self.assertIn("No Job Titles Registered", content)

        # 2. Populated table
        JobTitle.objects.create(title="Software Engineer", description="Develops applications")
        resp = client.get(reverse("employees:job_title_list"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("Software Engineer", content)
        self.assertNotIn("No Job Titles Registered", content)

    def test_administrative_unlinked_profile_banners(self):
        """Verify Administrator Attendance View and Leave Management unlinked banners."""
        client = Client()
        client.force_login(self.admin_user)

        # Attendance view
        resp = client.get(reverse("attendance:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Administrator Attendance View", resp.content.decode("utf-8"))

        # Leave view
        resp = client.get(reverse("leave_management:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Management View: Reviewing Organizational Leave Requests", resp.content.decode("utf-8"))

    def test_login_page_no_hardcoded_credentials(self):
        """Verify login page does not leak or display demo credentials or passwords."""
        client = Client()
        resp = client.get(reverse("accounts:login"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertNotIn("admin@hrms.com", content)
        self.assertNotIn("SecurePass123!", content)
        self.assertNotIn("Quick Demo Access", content)

    def test_navigation_and_cards_use_monochrome_bootstrap_icons(self):
        """Verify navigation menu and stat cards use clean vector Bootstrap Icons, not emojis."""
        from apps.reports.views import ADMIN_CARDS, HR_CARDS, EMPLOYEE_CARDS

        # 1. Navigation items
        for role in ["admin", "hr", "employee"]:
            items = menu_for_role(role)
            for item in items:
                icon = item["icon"]
                self.assertTrue(
                    icon.startswith("bi ") or icon.startswith("bi-"),
                    f"Navigation item '{item['label']}' icon '{icon}' must be a Bootstrap Icon."
                )

        # 2. Stat cards
        for card_set in [ADMIN_CARDS, HR_CARDS, EMPLOYEE_CARDS]:
            for card in card_set:
                icon = card["icon"]
                self.assertTrue(
                    icon.startswith("bi ") or icon.startswith("bi-"),
                    f"Stat card '{card['title']}' icon '{icon}' must be a Bootstrap Icon."
                )

    def test_all_pages_render_with_design_system_shell(self):
        """Verify all core pages render with the unified design system shell."""
        client = Client()
        client.force_login(self.admin_user)

        endpoints = [
            reverse("admin-dashboard"),
            reverse("employees:list"),
            reverse("employees:department_list"),
            reverse("employees:job_title_list"),
            reverse("attendance:list"),
            reverse("leave_management:list"),
            reverse("reports:exports"),
            reverse("reports:charts"),
            reverse("accounts:profile"),
            reverse("accounts:password_change"),
        ]

        for url in endpoints:
            resp = client.get(url)
            self.assertEqual(resp.status_code, 200, f"Page {url} failed with status {resp.status_code}")
            content = resp.content.decode("utf-8")
            self.assertIn("hr-navbar", content, f"Missing navbar on {url}")
            self.assertIn("hr-sidebar", content, f"Missing sidebar on {url}")
            self.assertIn("btn-theme-toggle", content, f"Missing theme toggle on {url}")
