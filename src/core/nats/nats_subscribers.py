from typing import Any

from nats.aio.client import Client as NATSClient

from src.action.action_controller import ActionController, ExecuteActionPayload
from src.app_controller import AppController
from src.core.nats.interfaces.nats_interface import NatsSubscriber
from src.core.nats.nats_client import nats_handler
from src.core.settings.env import ROBOTICS_MS
from src.voice.voice_service import SpeakPayload, VoiceService


def create_subscribers(nats_client: NATSClient) -> list[NatsSubscriber]:
    _ = nats_client
    action_controller = ActionController()
    app_controller = AppController()
    voice_service = VoiceService(nats_handler.req_nc)

    subscribers: list[NatsSubscriber] = [
        NatsSubscriber(
            controller=app_controller.health,
            subject=f"{ROBOTICS_MS}.healthService.health",
        ),
        NatsSubscriber(
            controller=action_controller.get_actions,
            subject=f"{ROBOTICS_MS}.actionService.getActions",
        ),
        NatsSubscriber(
            controller=lambda data: action_controller.execute_action(
                ExecuteActionPayload.model_validate(data)
            ),
            subject=f"{ROBOTICS_MS}.actionService.executeAction",
        ),
        NatsSubscriber(
            controller=lambda data: voice_service.speak_only(
                SpeakPayload.model_validate(data).message
            ),
            subject=f"{ROBOTICS_MS}.voiceService.speak",
        ),
    ]
    return subscribers
