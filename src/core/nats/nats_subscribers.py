from typing import Any

from nats.aio.client import Client as NATSClient

from src.app_controller import AppController
from src.core.settings.env import ROBOTICS_MS


def create_subscribers(nats_client: NATSClient) -> list[dict[str, Any]]:
    return [
        {
            "controller": AppController.health,
            "subject": f"{ROBOTICS_MS}.healthService.health",
        },
    ]
