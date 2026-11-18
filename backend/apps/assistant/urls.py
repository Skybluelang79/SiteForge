from django.urls import path

from .views import (
    AssistantChatView,
    AssistantContextView,
    AssistantConversationDetailView,
    AssistantConversationListView,
)

urlpatterns = [
    path("assistant/chat/", AssistantChatView.as_view(), name="assistant-chat"),
    path("assistant/context/", AssistantContextView.as_view(), name="assistant-context"),
    path(
        "assistant/conversations/",
        AssistantConversationListView.as_view(),
        name="assistant-conversations",
    ),
    path(
        "assistant/conversations/<uuid:pk>/",
        AssistantConversationDetailView.as_view(),
        name="assistant-conversation-detail",
    ),
]
