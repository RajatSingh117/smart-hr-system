from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from apps.accounts.models import User


@csrf_protect
@require_http_methods(['GET', 'POST'])
def login_view(request):
    """
    Login view with role-based redirect:
    - Admin → /admin-dashboard/
    - HR → /hr-dashboard/
    - Employee → /my-dashboard/
    """
    if request.user.is_authenticated:
        return redirect('accounts:dashboard_redirect')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me') == 'on'

        user = authenticate(request, username=email, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)

                if not remember_me:
                    request.session.set_expiry(0)  # Session expires on browser close

                messages.success(request, f'Welcome back, {user.get_full_name() or user.email}!')

                # Role-based redirect
                if user.role == User.Role.ADMIN:
                    return redirect('admin-dashboard')
                elif user.role == User.Role.HR:
                    return redirect('hr-dashboard')
                else:
                    return redirect('my-dashboard')
            else:
                messages.error(request, 'Your account is disabled. Please contact HR.')
        else:
            messages.error(request, 'Invalid email or password.')

    return render(request, 'accounts/login.html')


@login_required
@require_http_methods(['GET', 'POST'])
def logout_view(request):
    """Logout view with next-page handling."""
    user_name = request.user.get_full_name() or request.user.email
    logout(request)
    messages.success(request, f'Goodbye, {user_name}! You have been logged out.')
    return redirect('accounts:login')


@login_required
@require_http_methods(['GET', 'POST'])
def password_change_view(request):
    """Password change view with custom template."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            messages.success(request, 'Your password has been updated successfully.')
            return redirect('accounts:dashboard_redirect')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'accounts/password_change.html', {'form': form})


@login_required
def dashboard_redirect_view(request):
    """
    Redirect user to appropriate dashboard based on role.
    """
    user = request.user
    if user.role == User.Role.ADMIN:
        return redirect('admin-dashboard')
    elif user.role == User.Role.HR:
        return redirect('hr-dashboard')
    else:
        return redirect('my-dashboard')


@login_required
def profile_view(request):
    """User profile view - read only for now."""
    return render(request, 'accounts/profile.html', {'user': request.user})


@login_required
def api_user_info(request):
    """API endpoint for current user info."""
    user = request.user
    return JsonResponse({
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'full_name': user.get_full_name(),
        'initials': user.get_initials(),
        'role': user.role,
        'role_display': user.get_role_display(),
        'department': user.department,
        'employee_id': user.employee_id,
        'phone': user.phone,
        'is_admin': user.is_admin,
        'is_hr': user.is_hr,
        'is_employee': user.is_employee,
        'can_access_payroll': user.can_access_payroll(),
        'can_manage_users': user.can_manage_users(),
    })