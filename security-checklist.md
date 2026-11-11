# Security Deployment Checklist — Smart HRMS

**Version:** 1.0
**Date:** 2026-11-11
**Environment:** Production

---

## Pre-Deployment Checklist

### Environment Configuration
- [ ] `SECRET_KEY` set via environment variable (50+ chars, not `django-insecure-`)
- [ ] `DEBUG=False`
- [ ] `ALLOWED_HOSTS` configured with production domain(s)
- [ ] `CSRF_TRUSTED_ORIGINS` set with `https://` scheme
- [ ] Database: PostgreSQL with SSL (`sslmode=require`)
- [ ] Redis available for cache/rate limiting (`REDIS_URL`)
- [ ] Email SMTP credentials configured
- [ ] `ADMIN_URL` customized (non-default admin path)

### Secrets Management
- [ ] No secrets in `.env.example` (only placeholders)
- [ ] `.env` not committed to version control
- [ ] `trufflehog` scan passes on repo
- [ ] `git-secrets` scan passes on repo
- [ ] CI/CD secrets stored in vault/secrets manager

### Dependencies
- [ ] `safety check` passes (no vulnerable dependencies)
- [ ] `bandit -r apps/` passes (no static analysis issues)
- [ ] `pip-audit` passes
- [ ] All packages pinned in `requirements.txt` / `requirements-security.txt`

---

## Django Security Settings (config/settings/production.py)

### Core Security
- [ ] `SECURE_SSL_REDIRECT = True`
- [ ] `SECURE_HSTS_SECONDS = 31536000` (1 year)
- [ ] `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- [ ] `SECURE_HSTS_PRELOAD = True`
- [ ] `SECURE_CONTENT_TYPE_NOSNIFF = True`
- [ ] `SECURE_BROWSER_XSS_FILTER = True`
- [ ] `X_FRAME_OPTIONS = 'DENY'`
- [ ] `SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'`
- [ ] `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`

### Session Security
- [ ] `SESSION_COOKIE_HTTPONLY = True`
- [ ] `SESSION_COOKIE_SECURE = True`
- [ ] `SESSION_COOKIE_SAMESITE = 'Lax'`
- [ ] `SESSION_EXPIRE_AT_BROWSER_CLOSE = True`
- [ ] `SESSION_COOKIE_AGE = 28800` (8 hours)

### CSRF Security
- [ ] `CSRF_COOKIE_HTTPONLY = True`
- [ ] `CSRF_COOKIE_SECURE = True`
- [ ] `CSRF_COOKIE_SAMESITE = 'Lax'`
- [ ] `CSRF_USE_SESSIONS = True`
- [ ] `CSRF_TRUSTED_ORIGINS` configured

### Content Security Policy
- [ ] `CONTENT_SECURITY_POLICY` configured with:
  - `default-src: 'self'`
  - `script-src: 'self' 'nonce-...'`
  - `style-src: 'self' 'unsafe-inline' 'nonce-...'`
  - `img-src: 'self' data:`
  - `font-src: 'self'`
  - `connect-src: 'self'`
  - `frame-ancestors: 'none'`
  - `form-action: 'self'`
  - `base-uri: 'self'`

### Permissions Policy
- [ ] `PERMISSIONS_POLICY` disabling:
  - geolocation, microphone, camera
  - payment, usb, magnetometer
  - gyroscope, accelerometer

---

## Rate Limiting & Brute Force Protection

- [ ] `django-ratelimit` installed and configured
- [ ] Login: 5 requests/minute per IP
- [ ] Password change: 10 requests/hour per user
- [ ] API GET: 100 requests/hour per user
- [ ] API POST: 20 requests/hour per user
- [ ] `django-axes` configured:
  - `AXES_FAILURE_LIMIT = 5`
  - `AXES_LOCK_OUT_AT_FAILURE = True`
  - `AXES_COOLOFF_TIME = 1` hour
  - `AxesStandaloneBackend` in `AUTHENTICATION_BACKENDS`

---

## Authentication & Authorization

- [ ] Custom User model with role field (ADMIN, HR, EMPLOYEE)
- [ ] Password validators:
  - Minimum 12 characters
  - Uppercase, lowercase, digit, special char required
  - No common passwords
  - No numeric-only passwords
  - No user attribute similarity
- [ ] Permission classes:
  - `IsAdmin` — Admin only
  - `IsHR` — Admin + HR
  - `IsOwnerOrHR` — Object owner or HR/Admin
  - `CanAccessPayroll` — Payroll-specific access
  - `IsSelfOrHR` — Self or HR/Admin
- [ ] Object-level permissions on all DetailView/RetrieveAPIView
- [ ] List endpoints filtered by ownership
- [ ] URL ID manipulation returns 403/404 (no info leak)

---

## Audit Logging

- [ ] `AuditEvent` model with indexes on `(content_type, object_id)` and `(actor, timestamp)`
- [ ] `log_audit()` helper captures actor, action, changes, IP, user agent
- [ ] `AuditedModelMixin` on all sensitive models (15 models)
- [ ] Signals auto-log CREATE/UPDATE/DELETE
- [ ] Audit log retention policy defined

---

## Infrastructure & Network

- [ ] HTTPS enforced (TLS 1.2+)
- [ ] HSTS preload submitted (optional)
- [ ] WAF configured (Cloudflare/AWS WAF/ModSecurity)
- [ ] Rate limiting at edge (Cloudflare rate limiting)
- [ ] DDoS protection enabled
- [ ] Security headers verified via `securityheaders.com`
- [ ] SSL Labs grade A+

---

## Monitoring & Logging

- [ ] Structured JSON logging configured (`python-json-logger`)
- [ ] Log rotation: 10MB files, 10 backups
- [ ] Security events logged to separate file (`security.log`)
- [ ] Error notifications via email (`AdminEmailHandler`)
- [ ] Sentry/APM integration for error tracking
- [ ] Audit log aggregation (ELK/Splunk)
- [ ] Failed login alerts (Axes + monitoring)

---

## Backup & Recovery

- [ ] Automated daily database backups
- [ ] Backup encryption at rest
- [ ] Backup integrity verified weekly
- [ ] Point-in-time recovery tested
- [ ] RPO/RTO documented

---

## Post-Deployment Verification

### Automated Checks
- [ ] `python manage.py check --deploy --settings=config.settings.production` → 0 issues
- [ ] All tests pass: `python manage.py test --verbosity=1` → 317/317 OK
- [ ] Health check endpoint returns 200
- [ ] Admin panel accessible at custom `ADMIN_URL`

### Manual Verification
- [ ] Login works for all roles with correct redirects
- [ ] Password change enforces complexity
- [ ] Rate limiting triggers on login (5 attempts → 429)
- [ ] Axes lockout works (5 failures → 1hr lockout)
- [ ] CSRF token required on all forms
- [ ] Security headers present (check via browser dev tools)
- [ ] CSP headers present (check via browser dev tools)
- [ ] Employee cannot access other employee's data
- [ ] HR/Admin can access all data
- [ ] Audit log entries created on mutations
- [ ] `.env` not accessible via web
- [ ] Debug toolbar not present
- [ ] No server version headers exposed

---

## Incident Response

- [ ] Security incident runbook documented
- [ ] Contact list for security team
- [ ] Log retention: 90 days minimum
- [ ] Breach notification procedure (GDPR/local law)
- [ ] Rollback procedure tested

---

## Compliance

- [ ] GDPR: Data processing agreement, right to deletion, data portability
- [ ] Data minimization: Only necessary fields collected
- [ ] Encryption at rest: Database, backups, logs
- [ ] Encryption in transit: TLS 1.2+ everywhere
- [ ] Access control: Principle of least privilege
- [ ] Audit trail: All sensitive actions logged

---

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Security Engineer | | | |
| DevOps Engineer | | | |
| Application Owner | | | |
| CISO / Security Lead | | | |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-11-11 | M2 Security Sprint | Initial release |