from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from .forms import MessageForm
from .models import Message

@login_required
def chat_home(request):
    if request.method == "POST":
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.save()
            return redirect("chat")
    else:
        form = MessageForm()
    messages = Message.objects.filter(sender=request.user) | Message.objects.filter(recipient=request.user)
    return render(request, "chat/home.html", {"form": form, "messages": messages.order_by("-created_at")[:50]})
