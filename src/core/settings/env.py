import os

from dotenv import load_dotenv

load_dotenv()

NATS_SERVER: str | None = os.getenv("NATS_SERVER")
if not NATS_SERVER:
    raise ValueError("NATS_SERVER environment variable is NOT set")

ROBOTICS_MS: str = "ROBOTICS_MS"
