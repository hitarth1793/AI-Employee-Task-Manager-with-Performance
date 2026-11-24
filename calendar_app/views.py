from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from .forms import EventForm
from .models import CalendarEvent

@login_required
def calendar_home(request):
    events = CalendarEvent.objects.all().order_by("start")
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            event.save()
            messages.success(request, "Calendar event created.")
            return redirect("calendar")
    else:
        form = EventForm()
    return render(request, "calendar_app/home.html", {"events": events, "form": form})
