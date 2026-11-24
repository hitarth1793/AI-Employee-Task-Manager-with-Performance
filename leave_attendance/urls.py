from django.urls import path
from .views import attendance_home, leave_approvals, leave_decide, leave_home

urlpatterns = [
    path("", leave_home, name="leave"),
    path("attendance/", attendance_home, name="attendance"),
    path("approvals/", leave_approvals, name="leave_approvals"),
    path("approvals/<int:pk>/<str:decision>/", leave_decide, name="leave_decide"),
]
