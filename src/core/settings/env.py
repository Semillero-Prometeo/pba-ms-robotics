import os

from dotenv import load_dotenv

load_dotenv()

NATS_SERVER: str | None = os.getenv("NATS_SERVER")
if not NATS_SERVER:
    raise ValueError("NATS_SERVER environment variable is NOT set")

ROBOTICS_MS: str = "ROBOTICS_MS"
SEQUENCES_DATA_DIR: str = os.getenv("SEQUENCES_DATA_DIR", "/usr/src/app/data/sequences")
ACTION_DESCRIPTIONS_PATH: str = os.getenv(
    "ACTION_DESCRIPTIONS_PATH",
    "/usr/src/app/data/action-descriptions.json",
)
PHRASES_PATH: str = os.getenv("PHRASES_PATH", "/usr/src/app/data/phrases.json")

# Management MS (OpenAI chat via NATS)
MANAGEMENT_MS: str = "MANAGEMENT_MS"
