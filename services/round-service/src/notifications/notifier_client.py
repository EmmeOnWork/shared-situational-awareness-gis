"""NotifierClient — the HTTP adapter to the Realtime Notifier's publish ingress.

The one real IO the producer drives: an ``async`` POST of a Notification to the
Notifier's ``/notifications/publish`` (server-to-server, not via the gateway). The
``NotificationProducer`` is the pure mapping; this is the only piece that touches
the network, so the producer stays unit-testable with a recording fake.

The publish is **best-effort**, exactly like ``OutcomesRepository``: the round
process is in-memory and realtime, so a Notifier outage must never break a live
Round — a failed publish is logged and the Round carries on.
"""

import logging

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)


class NotifierClient:
    def __init__(self, url: str | None = None, timeout: float = 2.0):
        self._url = url or get_settings().notifier_publish_url
        self._timeout = timeout

    async def publish(self, notification: dict) -> None:
        """POST one Notification to the publish ingress. Never raises (best-effort)."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                await client.post(self._url, json=notification)
        except Exception as exc:  # noqa: BLE001 — publishing is best-effort
            logger.warning(
                "notifier publish skipped (%s); is %s reachable?", exc, self._url
            )
