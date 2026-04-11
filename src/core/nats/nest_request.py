"""Request/reply compatible with NestJS ClientNats + NatsRecordSerializer / response JSON codec."""

from __future__ import annotations

import json
import logging
import secrets
import string
from typing import Any

from nats.aio.client import Client as NATSClient

logger = logging.getLogger(__name__)


class NestRpcError(Exception):
    """Error field returned by Nest microservice NATS reply."""

    def __init__(self, err: Any) -> None:
        super().__init__(str(err))
        self.err = err


def _random_packet_id() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def _build_request_body(pattern: str, data: dict[str, Any]) -> bytes:
    packet = {
        "id": _random_packet_id(),
        "pattern": pattern,
        "data": data,
    }
    return json.dumps(packet).encode("utf-8")


def _extract_response_payload(decoded: dict[str, Any]) -> dict[str, Any]:
    """Parse Nest NATS server reply (NatsRecordSerializer + handler result)."""
    if decoded.get("err") is not None:
        raise NestRpcError(decoded["err"])
    if "response" in decoded and decoded["response"] is not None:
        resp = decoded["response"]
        if isinstance(resp, dict):
            return resp
        if isinstance(resp, str):
            return {"_raw": resp}
    # Single-shot reply may omit wrapper in edge cases
    if "reply" in decoded:
        return decoded  # type: ignore[return-value]
    raise ValueError(f"Unexpected NATS reply shape: {decoded!r}")


async def nest_request(
    nc: NATSClient,
    pattern: str,
    data: dict[str, Any],
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Send a Nest-compatible request and return the `response` object (e.g. chat `{reply}`).

    Subject must equal `pattern` (same string Nest uses after transformPatternToRoute).
    """
    payload = _build_request_body(pattern, data)
    msg = await nc.request(pattern, payload, timeout=timeout)
    raw = msg.data.decode("utf-8")
    if not raw:
        raise ValueError("Empty reply from Nest microservice")
    decoded: dict[str, Any] = json.loads(raw)
    return _extract_response_payload(decoded)
