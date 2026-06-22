"""NotificationProducer — round lifecycle effects → Realtime Notifier publishes.

The backend producer (PRD module 5): it consumes the *same* engine lifecycle
side-effects the room/persistence layers already react to, classifies each into a
presentation **severity** (the only vocabulary the Notifier knows) and publishes it
through an injected client, carrying the Bene's **Scope** so only participants whose
Active Workshop is that Bene see the toast / hear the sound (CONTEXT.md).

A **Vote carries no Notification**: a non-closing Vote emits no engine effect at
all, so it never reaches here — confirming a Vote is purely local widget feedback.
"""

from src.engine.round_engine import ConsensusReached, RoundClosed, RoundOpened

# Bene Scope axis (the selection-bus axis the Notifier matches client-side): a
# Notification scoped to ``{axis: WORKSHOP_AXIS, value: poiId}`` reaches only the
# participants whose Active Workshop is that Bene.
WORKSHOP_AXIS = "workshop"


def _bene_scope(poi_id) -> dict:
    return {"axis": WORKSHOP_AXIS, "value": str(poi_id)}


def _notification_for(effect) -> dict | None:
    """Map one lifecycle effect to the Notification to publish, or ``None`` for an
    effect that carries no shared lifecycle moment."""
    if isinstance(effect, RoundOpened):
        return {
            "severity": "info",
            "title": "Nuovo round",
            "body": "È iniziato un nuovo round di votazione.",
            "scope": _bene_scope(effect.poi_id),
        }
    if isinstance(effect, RoundClosed):
        return {
            "severity": "info",
            "title": "Round chiuso",
            "body": "Tutti hanno votato: il round è chiuso.",
            "scope": _bene_scope(effect.poi_id),
        }
    if isinstance(effect, ConsensusReached):
        return {
            "severity": "success",
            "title": "Consenso raggiunto",
            "body": "Il gruppo ha raggiunto il consenso totale.",
            "scope": _bene_scope(effect.poi_id),
        }
    return None


class NotificationProducer:
    """Wraps a Notifier client (real HTTP adapter, or a recording fake in tests)
    and publishes the Notification a lifecycle effect maps to."""

    def __init__(self, client):
        self._client = client

    async def react(self, effect) -> None:
        notification = _notification_for(effect)
        if notification is not None:
            await self._client.publish(notification)
