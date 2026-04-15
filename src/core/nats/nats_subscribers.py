from typing import Any

from nats.aio.client import Client as NATSClient

from src.action.action_controller import ActionController, ExecuteActionPayload
from src.app_controller import AppController
from src.core.nats.interfaces.nats_interface import NatsSubscriber
from src.core.nats.nats_client import nats_handler
from src.core.settings.env import ROBOTICS_MS
from src.sequence.interfaces.sequence_interface import (
    PcaScanPayload,
    SaveSequencePayload,
    SequenceByNamePayload,
    SequenceChainStartPayload,
    SequencePlaybackPayload,
)
from src.sequence.sequence_controller import SequenceController, StopSequencePayload
from src.voice.voice_service import SpeakPayload, VoiceService


def create_subscribers(nats_client: NATSClient) -> list[NatsSubscriber]:
    _ = nats_client
    action_controller = ActionController()
    sequence_controller = SequenceController()
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
            controller=sequence_controller.list_arduinos,
            subject=f"{ROBOTICS_MS}.sequenceService.listArduinos",
        ),
        NatsSubscriber(
            controller=lambda data: sequence_controller.scan_pcas(
                PcaScanPayload.model_validate(data)
            ),
            subject=f"{ROBOTICS_MS}.sequenceService.scanPcas",
        ),
        NatsSubscriber(
            controller=sequence_controller.list_sequences,
            subject=f"{ROBOTICS_MS}.sequenceService.listSequences",
        ),
        NatsSubscriber(
            controller=lambda data: sequence_controller.get_sequence(
                SequenceByNamePayload.model_validate(data)
            ),
            subject=f"{ROBOTICS_MS}.sequenceService.getSequence",
        ),
        NatsSubscriber(
            controller=lambda data: sequence_controller.save_sequence(
                SaveSequencePayload.model_validate(data)
            ),
            subject=f"{ROBOTICS_MS}.sequenceService.saveSequence",
        ),
        NatsSubscriber(
            controller=lambda data: sequence_controller.delete_sequence(
                SequenceByNamePayload.model_validate(data)
            ),
            subject=f"{ROBOTICS_MS}.sequenceService.deleteSequence",
        ),
        NatsSubscriber(
            controller=lambda data: sequence_controller.start_playback(
                SequencePlaybackPayload.model_validate(data)
            ),
            subject=f"{ROBOTICS_MS}.sequenceService.startPlayback",
        ),
        NatsSubscriber(
            controller=lambda data: sequence_controller.stop_playback(
                StopSequencePayload.model_validate(data)
            ),
            subject=f"{ROBOTICS_MS}.sequenceService.stopPlayback",
        ),
        NatsSubscriber(
            controller=lambda data: sequence_controller.start_chain(
                SequenceChainStartPayload.model_validate(data)
            ),
            subject=f"{ROBOTICS_MS}.sequenceService.startChain",
        ),
        NatsSubscriber(
            controller=lambda data: sequence_controller.stop_chain(
                StopSequencePayload.model_validate(data)
            ),
            subject=f"{ROBOTICS_MS}.sequenceService.stopChain",
        ),
        NatsSubscriber(
            controller=sequence_controller.chain_status,
            subject=f"{ROBOTICS_MS}.sequenceService.chainStatus",
        ),
        NatsSubscriber(
            controller=lambda data: voice_service.speak_only(
                SpeakPayload.model_validate(data).message
            ),
            subject=f"{ROBOTICS_MS}.voiceService.speak",
        ),
    ]
    return subscribers
