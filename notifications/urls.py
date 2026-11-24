from django.urls import path
from .views import mark_read, notification_list

urlpatterns = [
    path("", notification_list, name="notifications"),
    path("<int:pk>/read/", mark_read, name="notification_read"),
]
