from django.urls import path

from . import views

app_name = "organization"
urlpatterns = [
    path("departments/", views.department_list, name="departments"),
    path("departments/create/", views.department_create, name="department_create"),
    path(
        "departments/<int:pk>/edit/",
        views.department_edit,
        name="department_edit",
    ),
    path(
        "departments/<int:pk>/delete/",
        views.department_delete,
        name="department_delete",
    ),
    path("teams/", views.team_list, name="teams"),
    path("teams/create/", views.team_create, name="team_create"),
    path("teams/<int:pk>/", views.team_detail, name="team_detail"),
    path("teams/<int:pk>/edit/", views.team_edit, name="team_edit"),
    path("projects/", views.project_list, name="projects"),
    path("projects/create/", views.project_create, name="project_create"),
    path("projects/<int:pk>/edit/", views.project_edit, name="project_edit"),
    path("projects/<int:pk>/archive/", views.project_archive, name="project_archive"),
]
