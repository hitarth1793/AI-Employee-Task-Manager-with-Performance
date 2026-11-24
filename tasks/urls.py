from django.urls import path
from .views import add_comment, kanban_update, task_create, task_detail, task_list, task_update

urlpatterns = [
    path("", task_list, name="task_list"),
    path("create/", task_create, name="task_create"),
    path("<int:pk>/", task_detail, name="task_detail"),
    path("<int:pk>/edit/", task_update, name="task_update"),
    path("<int:pk>/comment/", add_comment, name="add_comment"),
    path("kanban/update/", kanban_update, name="kanban_update"),
]
