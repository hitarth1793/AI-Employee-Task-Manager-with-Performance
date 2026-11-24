from django.contrib.auth.views import LogoutView
from django.urls import path
from .views import RoleLoginView, employee_create, employee_edit, employee_list, profile_view, register_view

app_name = "accounts"
urlpatterns = [
    path("login/", RoleLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", register_view, name="register"),
    path("profile/", profile_view, name="profile"),
    path("employees/", employee_list, name="employees"),
    path("employees/add/", employee_create, name="employee_create"),
    path("employees/<int:user_id>/edit/", employee_edit, name="employee_edit"),
]
