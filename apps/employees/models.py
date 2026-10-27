from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.mixins import AuditedModelMixin


class Department(AuditedModelMixin):
    """
    Department within the organization.
    Supports assigning an Employee as the department head.
    """
    name = models.CharField(
        _('department name'),
        max_length=100,
        unique=True,
        help_text=_('Unique name of the department'),
    )
    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_('Detailed overview of the department functions'),
    )
    department_head = models.ForeignKey(
        'Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='headed_departments',
        verbose_name=_('department head'),
        help_text=_('Current head of this department'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_('Indicates whether this department is currently operational'),
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('department')
        verbose_name_plural = _('departments')
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.department_head_id:
            try:
                head = self.department_head
            except Employee.DoesNotExist:
                head = None
            if head and head.employment_status != Employee.EmploymentStatus.ACTIVE:
                raise ValidationError({
                    'department_head': _('Only active employees may be selected as department head.')
                })


class JobTitle(AuditedModelMixin):
    """
    Job designation / role title within the organization.
    """
    title = models.CharField(
        _('job title'),
        max_length=100,
        unique=True,
        help_text=_('Unique name of the job title or position'),
    )
    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_('Responsibilities and scope associated with this title'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_('Indicates whether this job title is actively in use'),
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('job title')
        verbose_name_plural = _('job titles')
        ordering = ['title']

    def __str__(self):
        return self.title


class Employee(AuditedModelMixin):
    """
    Core employee profile representing an organization member.
    Links to auth User for credentials, Department, and JobTitle.
    Includes a 10-point completeness score calculator.
    """

    class EmploymentStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active')
        ON_LEAVE = 'ON_LEAVE', _('On Leave')
        TERMINATED = 'TERMINATED', _('Terminated')

    # Backward-compatible alias
    Status = EmploymentStatus

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='employee_profile',
        null=True,
        blank=True,
        verbose_name=_('user account'),
        help_text=_('Associated authentication user account'),
    )
    employee_id = models.CharField(
        _('employee ID'),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_('Unique identifier code (e.g., EMP001)'),
    )
    full_name = models.CharField(
        _('full name'),
        max_length=150,
        help_text=_('Full legal name of the employee'),
    )
    email = models.EmailField(
        _('email address'),
        unique=True,
        db_index=True,
        help_text=_('Official primary email address'),
    )
    phone = models.CharField(
        _('phone number'),
        max_length=25,
        blank=True,
        help_text=_('Primary contact telephone number'),
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='employees',
        null=True,
        blank=True,
        verbose_name=_('department'),
        help_text=_('Department this employee belongs to'),
    )
    job_title = models.ForeignKey(
        JobTitle,
        on_delete=models.PROTECT,
        related_name='employees',
        null=True,
        blank=True,
        verbose_name=_('job title'),
        help_text=_('Designated job title or designation'),
    )
    joining_date = models.DateField(
        _('joining date'),
        help_text=_('Date when the employee commenced employment'),
    )
    employment_status = models.CharField(
        _('employment status'),
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.ACTIVE,
        db_index=True,
    )
    base_salary = models.DecimalField(
        _('base salary'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Monthly base salary in currency units'),
    )
    address = models.TextField(
        _('residential address'),
        blank=True,
        help_text=_('Residential / mailing address'),
    )
    emergency_contact = models.CharField(
        _('emergency contact'),
        max_length=100,
        blank=True,
        help_text=_('Emergency contact name and phone number'),
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('employee')
        verbose_name_plural = _('employees')
        ordering = ['full_name']
        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['email']),
            models.Index(fields=['employment_status']),
            models.Index(fields=['department', 'employment_status']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.employee_id})"

    @property
    def is_active_employee(self):
        """Returns True if the employee is currently in ACTIVE status."""
        return self.employment_status == self.EmploymentStatus.ACTIVE

    def calculate_profile_completeness(self):
        """
        Calculates profile completeness percentage based on 10 profile dimensions:
        1. full_name
        2. email
        3. phone
        4. department_id
        5. job_title_id
        6. joining_date
        7. base_salary (> 0)
        8. address
        9. emergency_contact
        10. user_id (linked user account)
        """
        metrics = [
            bool(self.full_name),
            bool(self.email),
            bool(self.phone),
            bool(self.department_id),
            bool(self.job_title_id),
            bool(self.joining_date),
            bool(self.base_salary and self.base_salary > Decimal('0.00')),
            bool(self.address),
            bool(self.emergency_contact),
            bool(self.user_id),
        ]
        completed = sum(1 for m in metrics if m)
        return int((completed / len(metrics)) * 100)
