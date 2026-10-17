from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Custom manager for User model with role handling."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        extra_fields.setdefault('role', User.Role.EMPLOYEE)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom User model with role-based access control."""

    class Role(models.TextChoices):
        ADMIN = 'ADMIN', _('Admin')
        HR = 'HR', _('HR')
        EMPLOYEE = 'EMPLOYEE', _('Employee')

    username = None  # Remove username, use email as primary identifier
    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(
        _('role'),
        max_length=10,
        choices=Role.choices,
        default=Role.EMPLOYEE,
    )
    phone = models.CharField(_('phone number'), max_length=20, blank=True)
    department = models.CharField(_('department'), max_length=100, blank=True)
    employee_id = models.CharField(_('employee ID'), max_length=20, unique=True, null=True, blank=True)
    date_joined = models.DateTimeField(_('date joined'), auto_now_add=True)
    is_active = models.BooleanField(_('active'), default=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']

    def __str__(self):
        return f'{self.get_full_name() or self.email} ({self.get_role_display()})'

    def get_initials(self):
        """Return user's initials for avatar display."""
        first = self.first_name[0] if self.first_name else ''
        last = self.last_name[0] if self.last_name else ''
        return (first + last).upper() or self.email[0].upper()

    def get_role_display(self):
        """Return human-readable role."""
        return dict(self.Role.choices).get(self.role, self.role)

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_hr(self):
        return self.role in [self.Role.ADMIN, self.Role.HR]

    @property
    def is_employee(self):
        return self.role == self.Role.EMPLOYEE

    def can_access_payroll(self):
        """Check if user can access payroll data."""
        return self.role in [self.Role.ADMIN, self.Role.HR]

    def can_manage_users(self):
        """Check if user can manage other users."""
        return self.role == self.Role.ADMIN


class AuditEvent(models.Model):
    """
    Audit log model for tracking all sensitive actions across the system.
    Used by M3, M4, M5 for comprehensive audit trail.
    """

    class Action(models.TextChoices):
        CREATE = 'CREATE', _('Create')
        UPDATE = 'UPDATE', _('Update')
        DELETE = 'DELETE', _('Delete')
        VIEW = 'VIEW', _('View')
        EXPORT = 'EXPORT', _('Export')
        APPROVE = 'APPROVE', _('Approve')
        REJECT = 'REJECT', _('Reject')

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events',
        verbose_name=_('actor'),
    )
    action = models.CharField(
        _('action'),
        max_length=10,
        choices=Action.choices,
        db_index=True,
    )
    # Generic foreign key to any model
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        verbose_name=_('content type'),
    )
    object_id = models.PositiveBigIntegerField(_('object ID'), db_index=True)
    # content_object = GenericForeignKey('content_type', 'object_id')  # Access via property
    object_repr = models.CharField(_('object representation'), max_length=200)
    changes = models.JSONField(_('changes'), null=True, blank=True)
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.TextField(_('user agent'), blank=True)
    timestamp = models.DateTimeField(_('timestamp'), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _('audit event')
        verbose_name_plural = _('audit events')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['actor', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        actor_str = self.actor.get_full_name() if self.actor else 'System'
        return f'{actor_str} - {self.get_action_display()} - {self.object_repr}'

    @property
    def content_object(self):
        """Get the actual object being audited."""
        return self.content_type.get_object_for_this_type(pk=self.object_id)