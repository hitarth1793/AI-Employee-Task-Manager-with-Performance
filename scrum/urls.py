from django.urls import path
from .views import board, sprint_create, sprint_list

urlpatterns = [
    path("board/", board, name="scrum_board"),
    path("sprints/", sprint_list, name="sprint_list"),
    path("sprints/create/", sprint_create, name="sprint_create"),
]
