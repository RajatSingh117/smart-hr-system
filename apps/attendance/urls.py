from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("", views.AttendanceListView.as_view(), name="list"),
    path("check/", views.AttendanceCheckView.as_view(), name="check"),
    path("summary/", views.MonthlySummaryView.as_view(), name="summary"),
    path("correct/", views.AttendanceCorrectionView.as_view(), name="correct"),
]