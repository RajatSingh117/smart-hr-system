from django.urls import path

from . import views

app_name = "leave_management"

urlpatterns = [
    path("", views.LeaveListView.as_view(), name="list"),
    path("apply/", views.LeaveApplyView.as_view(), name="apply"),
    path("<int:pk>/", views.LeaveReviewView.as_view(), name="review"),
]