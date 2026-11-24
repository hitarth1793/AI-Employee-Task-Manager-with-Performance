from django.urls import path
from .views import reports_home, task_csv, task_pdf

urlpatterns = [
    path("", reports_home, name="reports"),
    path("tasks.csv", task_csv, name="task_csv"),
    path("tasks.pdf", task_pdf, name="task_pdf"),
]
