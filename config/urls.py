"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

# Placeholder dashboard views (will be replaced by M6)
@login_required
def admin_dashboard(request):
    return TemplateView.as_view(template_name='dashboards/admin.html')(request)

@login_required
def hr_dashboard(request):
    return TemplateView.as_view(template_name='dashboards/hr.html')(request)

@login_required
def my_dashboard(request):
    return TemplateView.as_view(template_name='dashboards/employee.html')(request)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth URLs
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),

    # Dashboard URLs (role-based, will be enhanced by M6)
    path('admin-dashboard/', admin_dashboard, name='admin-dashboard'),
    path('hr-dashboard/', hr_dashboard, name='hr-dashboard'),
    path('my-dashboard/', my_dashboard, name='my-dashboard'),

    # Root redirect to login
    path('', lambda request: redirect('accounts:login')),
]