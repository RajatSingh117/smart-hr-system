from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import Department, Employee, JobTitle


class EmployeeForm(forms.ModelForm):
    """
    Form for creating and editing Employee records.
    Provides custom validation for unique identifiers and enforces
    safe user account linking rules.
    """

    class Meta:
        model = Employee
        fields = [
            'employee_id',
            'full_name',
            'email',
            'phone',
            'department',
            'job_title',
            'joining_date',
            'employment_status',
            'base_salary',
            'address',
            'emergency_contact',
            'user',
        ]
        widgets = {
            'employee_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., EMP001'),
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Full legal name'),
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': _('official.email@company.com'),
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('+1-555-0100'),
            }),
            'department': forms.Select(attrs={
                'class': 'form-select',
            }),
            'job_title': forms.Select(attrs={
                'class': 'form-select',
            }),
            'joining_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
            'employment_status': forms.Select(attrs={
                'class': 'form-select',
            }),
            'base_salary': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Residential address'),
            }),
            'emergency_contact': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Contact person and phone number'),
            }),
            'user': forms.Select(attrs={
                'class': 'form-select',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()

        # Empty labels for dropdowns
        self.fields['department'].empty_label = _('Select department (optional)')
        self.fields['job_title'].empty_label = _('Select job title (optional)')
        self.fields['user'].empty_label = _('Select user account (optional)')
        self.fields['user'].required = False

        # Only allow linking an unlinked user, or the employee's currently linked user during edit
        user_query = Q(employee_profile__isnull=True)
        if self.instance and self.instance.pk and self.instance.user_id:
            user_query |= Q(pk=self.instance.user_id)

        self.fields['user'].queryset = User.objects.filter(user_query).order_by('email')

        # Order department and job title dropdowns alphabetically
        self.fields['department'].queryset = Department.objects.all().order_by('name')
        self.fields['job_title'].queryset = JobTitle.objects.all().order_by('title')

    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if employee_id:
            employee_id = employee_id.strip()
            qs = Employee.objects.filter(employee_id__iexact=employee_id)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    _('An employee with this Employee ID already exists.')
                )
        return employee_id

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.strip().lower()
            qs = Employee.objects.filter(email__iexact=email)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    _('An employee with this email address already exists.')
                )
        return email

    def clean_base_salary(self):
        base_salary = self.cleaned_data.get('base_salary')
        if base_salary is not None and base_salary < Decimal('0.00'):
            raise forms.ValidationError(
                _('Base salary cannot be negative.')
            )
        return base_salary

    def clean_user(self):
        user = self.cleaned_data.get('user')
        if user:
            # Enforce that user is not already linked to another employee
            qs = Employee.objects.filter(user=user)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    _('This user account is already linked to another employee.')
                )
        return user


class DepartmentForm(forms.ModelForm):
    """
    Form for creating and editing Department records.
    Provides validation for unique department names and head assignment.
    """

    class Meta:
        model = Department
        fields = [
            'name',
            'description',
            'department_head',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Engineering, Human Resources'),
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Overview of department functions and scope'),
            }),
            'department_head': forms.Select(attrs={
                'class': 'form-select',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department_head'].empty_label = _('Select department head (optional)')
        self.fields['department_head'].required = False

        active_heads = Employee.objects.filter(
            employment_status=Employee.EmploymentStatus.ACTIVE
        )
        if self.instance and self.instance.pk and self.instance.department_head_id:
            current_head_qs = Employee.objects.filter(pk=self.instance.department_head_id)
            self.fields['department_head'].queryset = (active_heads | current_head_qs).order_by('full_name')
        else:
            self.fields['department_head'].queryset = active_heads.order_by('full_name')

    def clean_department_head(self):
        head = self.cleaned_data.get('department_head')
        if head and head.employment_status != Employee.EmploymentStatus.ACTIVE:
            raise forms.ValidationError(
                _('Only active employees may be selected as department head.')
            )
        return head

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            qs = Department.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    _('A department with this name already exists.')
                )
        return name
