import asyncio
import json
import logging
import socket
import time

from nats.aio.client import Client as NATSClient
from nats.aio.errors import ErrNoServers
from nats.aio.msg import Msg as NATSMessage

from src.core.nats.interfaces.nats_interface import NatsSubscriber

# Envs
from src.core.settings.env import NATS_SERVER

logger: logging.Logger = logging.getLogger(__name__)


class NatsHandler:
    def __init__(self) -> None:
        self.nc: NATSClient = NATSClient()
        self.req_nc: NATSClient = NATSClient()
        self.connected: bool = False

    async def connect(self) -> None:
        try:
            logger.info(f"Attempting to connect to NATS at {NATS_SERVER}")

            nats_server = NATS_SERVER
            logger.info(f"Using NATS URL: {nats_server}")

            for i in range(10):
                try:
                    socket.create_connection(("nats-server", 4222), timeout=2)
                    print("NATS is available (TCP level)")
                    break
                except Exception:
                    print(f"Waiting for TCP connection with NATS... attempt {i + 1}")
                    time.sleep(2)

            for attempt in range(10):
                try:
                    await self.nc.connect(
                        servers=["nats://nats-server:4222"],
                        connect_timeout=10,
                        reconnect_time_wait=2,
                        max_reconnect_attempts=10,
                    )
                    if self.nc.is_connected:
                        print("Successfully connected to NATS (application level)")
                        break
                except Exception as e:
                    print(f"Attempt {attempt + 1}: NATS is not responding, retrying... ({e})")
                    await asyncio.sleep(2)
            else:
                raise RuntimeError(
                    "It was not possible to connect with NATS after multiple attempts"
                )

            for attempt in range(10):
                try:
                    await self.req_nc.connect(
                        servers=["nats://nats-server:4222"],
                        connect_timeout=10,
                        reconnect_time_wait=2,
                        max_reconnect_attempts=10,
                    )
                    if self.req_nc.is_connected:
                        print("Successfully connected to NATS (request level)")
                        break
                except Exception as e:
                    print(f"Attempt {attempt + 1} (req): NATS is not responding, retrying... ({e})")
                    await asyncio.sleep(2)
            else:
                raise RuntimeError(
                    "It was not possible to connect with NATS after multiple attempts"
                )

            self.connected = True
            logger.info(f"Successfully connected to NATS at {nats_server}")
        except ErrNoServers as e:
            logger.error(f"Could not connect to NATS server: {e}")
            self.connected = False
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to NATS: {e}")
            self.connected = False
            raise

    async def disconnect(self) -> None:
        if self.connected:
            await self.nc.close()
            try:
                await self.req_nc.close()
            except Exception:
                pass
            self.connected = False
            logger.info("Disconnected from NATS")

    async def subscribe(self, subscriber: NatsSubscriber) -> None:
        async def message_handler(msg: NATSMessage) -> None:
            print(f"Message: {msg}")
            try:
                logger.info(f"Received message on subject: {msg.subject}")
                logger.info(f"Message reply: {msg.reply}")
                logger.info(f"Message data length: {len(msg.data) if msg.data else 0} bytes")

                if msg.reply:
                    logger.info("Processing request-reply pattern")

                    data = json.loads(msg.data.decode())
                    response_data = await subscriber.controller(data["data"])
                    print(f"Response data: {response_data}")

                    logger.info("Sending response back via reply")

                    # NestJS NATS `client.send()` espera un "envelope" interno con `response`
                    # y `isDisposed=true` para poder completar el Observable.
                    # Si devolvemos un JSON plano (por ejemplo {status, response}) sin
                    # `isDisposed`, el gateway puede quedarse esperando indefinidamente.
                    if hasattr(response_data, "model_dump"):
                        response_payload = response_data.model_dump()
                    elif hasattr(response_data, "dict"):
                        # Compatibilidad si algún modelo usa pydantic v1.
                        response_payload = response_data.dict()
                    else:
                        response_payload = response_data

                    await msg.respond(
                        json.dumps({"response": response_payload, "isDisposed": True}).encode()
                    )

                    logger.info("Response sent successfully")
                else:
                    logger.info("Processing regular message")
                    data = json.loads(msg.data.decode())
                    await subscriber.controller(data)

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                if msg.reply:
                    await msg.respond(
                        json.dumps({"err": "Invalid JSON", "isDisposed": True}).encode()
                    )
            except Exception as e:
                logger.error(f"Handler error: {e}")
                if msg.reply:
                    await msg.respond(json.dumps({"err": str(e), "isDisposed": True}).encode())

        logger.info(f"Subscribing to subject: {subscriber.subject}")
        await self.nc.subscribe(subscriber.subject, cb=message_handler)


nats_handler: NatsHandler = NatsHandler()
