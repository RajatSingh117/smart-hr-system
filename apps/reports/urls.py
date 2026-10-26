
from django.urls import path

from apps.reports import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_dashboard, name="dashboard"),
]
