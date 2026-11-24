from django.urls import path
from .views import (
    ask,
    assistant_page,
    cancel_action,
    check_provider,
    conversation_detail,
    conversations,
    confirm_action,
    delete_conversation,
    propose_action,
)

urlpatterns = [
    path("", assistant_page, name="assistant"),
    path("ask/", ask, name="assistant_ask"),
    path("conversations/", conversations, name="assistant_conversations"),
    path("conversations/<int:conversation_id>/", conversation_detail, name="assistant_conversation_detail"),
    path("conversations/<int:conversation_id>/delete/", delete_conversation, name="assistant_conversation_delete"),
    path("providers/check/", check_provider, name="assistant_provider_check"),
    path("actions/propose/", propose_action, name="assistant_action_propose"),
    path("actions/<uuid:token>/confirm/", confirm_action, name="assistant_action_confirm"),
    path("actions/<uuid:token>/cancel/", cancel_action, name="assistant_action_cancel"),
]
