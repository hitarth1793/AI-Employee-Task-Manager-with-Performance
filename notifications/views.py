from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from .models import Notification

@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    return render(request, "notifications/list.html", {"notifications": notifications})

@login_required
def mark_read(request, pk):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    n.is_read = True
    n.save(update_fields=["is_read"])
    return redirect("notifications")
