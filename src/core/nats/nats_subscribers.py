from typing import Any

from nats.aio.client import Client as NATSClient

from src.action.action_controller import ActionController
from src.app_controller import AppController
from src.core.nats.interfaces.nats_interface import NatsSubscriber
from src.core.settings.env import ROBOTICS_MS


def create_subscribers(nats_client: NATSClient) -> list[dict[str, Any]]:
    _ = nats_client
    action_controller = ActionController()
    app_controller = AppController()

    subscribers = [
        NatsSubscriber(
            controller=app_controller.health,
            subject=f"{ROBOTICS_MS}.healthService.health",
        ),
        NatsSubscriber(
            controller=action_controller.get_actions,
            subject=f"{ROBOTICS_MS}.actionService.getActions",
        ),
        NatsSubscriber(
            controller=action_controller.execute_action,
            subject=f"{ROBOTICS_MS}.actionService.executeAction",
        ),
    ]
    return [subscriber.model_dump() for subscriber in subscribers]
