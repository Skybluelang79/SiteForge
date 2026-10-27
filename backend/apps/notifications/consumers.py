"""WebSocket consumer for per-user notification streams."""
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Notification


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.group_name = f"notifications_{user.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "event": "connected", "payload": {}})

    async def disconnect(self, code):
        group = getattr(self, "group_name", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong", "event": "pong", "payload": {}})

    async def notification_message(self, event):
        await self.send_json(event["message"])

    async def unread_count(self, event):
        await self.send_json(event["message"])

    @staticmethod
    def _serialize(notification: Notification):
        return {
            "id": str(notification.id),
            "title": notification.title,
            "body": notification.body,
            "level": notification.level,
            "verb": notification.verb,
            "created_at": notification.created_at.isoformat(),
        }
