import logging
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.nats.nats_client import nats_handler

# Subscribers
from src.core.nats.nats_subscribers import create_subscribers

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("pba-ms-robotics")
logger.info("[INFO] Iniciando aplicación PBA - MS - Robotics")


@asynccontextmanager
async def app_lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    await nats_handler.connect()

    # Expose dedicated request connection on the main client for downstream usage
    try:
        setattr(nats_handler.nc, "req_nc", nats_handler.req_nc)
    except Exception:
        pass

    subscribers = create_subscribers(nats_handler.nc)

    for subscriber in subscribers:
        await nats_handler.subscribe(subscriber["subject"], subscriber["controller"])

    yield
    await nats_handler.disconnect()


lifespan = app_lifespan

app = FastAPI(lifespan=app_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

logger.info("[INFO] - PBA-MS-Robotics listo para recibir solicitudes")
