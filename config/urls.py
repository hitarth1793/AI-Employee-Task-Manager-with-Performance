from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("accounts:login")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("dashboard/", include("dashboard.urls")),
    path("accounts/", include("accounts.urls")),
    path("organization/", include("organization.urls")),
    path("tasks/", include("tasks.urls")),
    path("scrum/", include("scrum.urls")),
    path("assistant/", include("assistant_app.urls")),
    path("notifications/", include("notifications.urls")),
    path("reports/", include("reports.urls")),
    path("calendar/", include("calendar_app.urls")),
    path("chat/", include("chat.urls")),
    path("leave/", include("leave_attendance.urls")),
    path("performance/", include("performance.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
