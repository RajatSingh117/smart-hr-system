# Smart HRMS - Member 2 (Auth, RBAC, Audit, Security)

Django 6.1 + DRF authentication system with role-based access control, audit logging, and security hardening.

---

## Quick Start

```bash
# Auto-start (systemd service - survives reboot)
systemctl --user enable --now smart-hrms

# Manual start
cd ~/smart-hrms
source venv/bin/activate
python manage.py runserver

# Run tests
python manage.py test
```

**Server**: http://localhost:8000

---

## Demo Credentials

| Role | Email | Password | Redirect |
|------|-------|----------|----------|
| **Admin** | `admin@hrms.com` | `SecurePass123!` | `/admin-dashboard/` |
| **HR** | `hr@hrms.com` | `SecurePass123!` | `/hr-dashboard/` |
| **Employee** | `emp@hrms.com` | `SecurePass123!` | `/my-dashboard/` |

---

## URLs

| Page | URL | Access |
|------|-----|--------|
| Login | `/accounts/login/` | Public |
| Logout | `/accounts/logout/` | Authenticated |
| Password Change | `/accounts/password/change/` | Authenticated |
| Profile | `/accounts/profile/` | Authenticated |
| Admin Dashboard | `/admin-dashboard/` | Admin only |
| HR Dashboard | `/hr-dashboard/` | HR, Admin |
| Employee Dashboard | `/my-dashboard/` | Employee |
| Django Admin | `/admin/` | Admin only |
| API User Info | `/accounts/api/user/` | Authenticated (JSON) |

---

## Architecture

```
config/
  settings.py          # Django settings (security, DRF, custom user)
  urls.py              # Root URL routing
accounts/
  models.py            # User (AbstractUser) + AuditEvent
  permissions.py       # IsAdmin, IsHR, IsOwnerOrHR, CanAccessPayroll, IsSelfOrHR
  views.py             # Login, logout, password_change, dashboard_redirect, profile, api_user_info
  urls.py              # /accounts/ namespace
  audit.py             # log_audit() helper for M3/M4/M5
  mixins.py            # AuditedModelMixin for auto-audit
  signals.py           # Auto-audit signal handlers
  tests/test_auth.py   # 43 tests (all passing)
templates/
  accounts/login.html
  accounts/password_change.html
  accounts/profile.html
  dashboards/admin.html
  dashboards/hr.html
  dashboards/employee.html
```

---

## Key Features

### Custom User Model (`accounts.models.User`)
- Email as username (no username field)
- Roles: `ADMIN`, `HR`, `EMPLOYEE`
- Helper properties: `is_admin`, `is_hr`, `is_employee`, `can_access_payroll()`, `can_manage_users()`
- `get_initials()` for avatar display

### Permission Classes (`accounts.permissions`)
| Class | Allows | Use Case |
|-------|--------|----------|
| `IsAdmin` | Admin only | User management, system config |
| `IsHR` | Admin + HR | Employee/Leave/Attendance write |
| `IsOwnerOrHR` | Owner + HR/Admin | Employee self-service |
| `CanAccessPayroll` | Admin + HR | Payroll records (M5) |
| `IsSelfOrHR` | Self + HR/Admin | Profile, attendance, leave |

### Audit System (Week 2 foundation)
- `AuditEvent` model: actor, action, generic FK, changes (JSON), IP, UA, timestamp
- `log_audit(actor, action, obj, changes, request)` - call from any app
- `AuditedModelMixin` - inherit for auto-audit on save/delete
- Signals auto-connect when M3/M4/M5 models loaded

### Security
- Password policy: 12+ chars, uppercase, lowercase, digit, special char
- Session: HttpOnly, Secure, SameSite=Lax, expire on browser close
- CSRF: HttpOnly, Secure, SameSite=Lax
- Production headers: HSTS, CSP, X-Frame-Options, SSL redirect
- Rate limiting ready (django-ratelimit)

---

## For Other Members (M3, M4, M5, M6)

### Import User Model
```python
from accounts.models import User
# or
from django.contrib.auth import get_user_model
User = get_user_model()
```

### Use Permissions in Views
```python
from accounts.permissions import IsHR, IsOwnerOrHR, CanAccessPayroll

class EmployeeViewSet(ModelViewSet):
    permission_classes = [IsHR]           # Write
    # or per-action:
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsOwnerOrHR()]
        return [IsHR()]
```

### Log Audit Events
```python
from accounts.audit import log_audit, AuditLogger

# Single event
log_audit(request.user, 'CREATE', employee, changes={'name': {'old': None, 'new': 'John'}}, request=request)

# Batch
with AuditLogger(request.user, request) as audit:
    audit.log('CREATE', emp1)
    audit.log('UPDATE', emp2, changes)
```

### Enable Auto-Audit on Your Models
```python
from accounts.mixins import AuditedModelMixin

class Employee(AuditedModelMixin):
    user = models.ForeignKey(User, ...)
    # ...

# In your AppConfig.ready():
from accounts.signals import register_audit_signals
register_audit_signals()
```

---

## Development

### Run Tests
```bash
python manage.py test                    # All tests
python manage.py test accounts.tests.test_auth  # Auth tests only
python manage.py test -v 2               # Verbose
```

### Create Migrations
```bash
python manage.py makemigrations accounts
python manage.py migrate
```

### Django Shell
```bash
python manage.py shell
# or
python manage.py shell_plus  # if django-extensions installed
```

### Create Superuser
```bash
python manage.py createsuperuser
# Or programmatically:
from accounts.models import User
User.objects.create_superuser('admin@hrms.com', 'SecurePass123!')
```

---

## Environment Variables (`.env`)

```bash
SECRET_KEY=your-production-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# PostgreSQL
DB_ENGINE=django.db.backends.postgresql
DB_NAME=hrms
DB_USER=hrms_user
DB_PASSWORD=secure_password
DB_HOST=localhost
DB_PORT=5432

# Email (production)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

Copy `.env.example` to `.env` and fill in values.

---

## Production Deployment Checklist

- [ ] `DEBUG=False`
- [ ] Strong `SECRET_KEY` in `.env`
- [ ] PostgreSQL configured
- [ ] `ALLOWED_HOSTS` set
- [ ] `SECURE_SSL_REDIRECT=True`
- [ ] `SESSION_COOKIE_SECURE=True`
- [ ] `CSRF_COOKIE_SECURE=True`
- [ ] Run `python manage.py check --deploy`
- [ ] Static files: `python manage.py collectstatic`
- [ ] Set up reverse proxy (nginx) + Gunicorn/uWSGI
- [ ] Enable systemd service for production user

---

## Project Structure (Week 1 Complete)

```
smart-hrms/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── accounts/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py          # User + AuditEvent
│   ├── views.py
│   ├── urls.py
│   ├── permissions.py
│   ├── audit.py
│   ├── mixins.py
│   ├── signals.py
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_auth.py   # 43 tests
│   └── migrations/
│       ├── __init__.py
│       └── 0001_initial.py
├── templates/
│   ├── base.html
│   ├── accounts/
│   │   ├── login.html
│   │   ├── password_change.html
│   │   └── profile.html
│   └── dashboards/
│       ├── admin.html
│       ├── hr.html
│       └── employee.html
├── manage.py
├── requirements.txt
├── .env.example
├── start_hrms.sh
└── db.sqlite3 (dev)
```

---

## Next Weeks (Roadmap)

| Week | Focus | Deliverables |
|------|-------|--------------|
| **Week 2** | Audit System & Permission Enforcement | Audit signals connected to M3/M4/M5 models, permissions applied to views |
| **Week 3** | Payroll Access Control & Security Hardening | Payroll access tests, audit hooks, security review sprint |
| **Week 4** | Final Security Audit & Documentation | Full object-level audit, CSRF/secrets/headers/rate-limit verified, security report |

---

## License

Internal project - Smart HRMS Team