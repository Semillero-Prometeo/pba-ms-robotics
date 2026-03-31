from nats.aio.client import Client as NATSClient

from src.action.action_controller import ActionController, ExecuteActionPayload
from src.app_controller import AppController
from src.core.nats.interfaces.nats_interface import NatsSubscriber
from src.core.settings.env import ROBOTICS_MS


def create_subscribers(nats_client: NATSClient) -> list[NatsSubscriber]:
    _ = nats_client
    action_controller = ActionController()
    app_controller = AppController()

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
    ]
    return subscribers
