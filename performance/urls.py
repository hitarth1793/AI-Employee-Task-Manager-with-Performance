from django.urls import path

from .views import performance_detail, performance_list

app_name = "performance"

urlpatterns = [
    path("", performance_list, name="list"),
    path("employee/<int:user_id>/", performance_detail, name="detail"),
]
