from django.urls import include, path

urlpatterns = [
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("dashboard/", include("apps.reports.urls")),
]