import json
from channels.generic.websocket import AsyncWebsocketConsumer

class TelemetryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.device_id = self.scope['url_route']['kwargs']['device_id']
        self.room_group_name = f'device_{self.device_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from room group
    async def telemetry_update(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'telemetry_update',
            'data': event['data']
        }))
        
    async def risk_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'risk_update',
            'data': event['data']
        }))
