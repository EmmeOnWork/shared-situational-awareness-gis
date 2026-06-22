"""OutcomesRepository — the durable record of each closed Round.

The one DML the recap slice writes: an upsert of the closed Round's outcome into
``public.round_outcomes`` — raw per-(Role × Vocazione) counts, N, per-Role and
overall Consensus, and the Round's duration — so the measure is re-derivable
offline and trends are analysable (task 05). The schema/grants come up with the
compose ``round-schema-init`` one-shot, never from the app.

The write is **best-effort**: the round process is in-memory and realtime, so a
DB hiccup must never break a live Round — a failed persist is logged, the recap
still renders. Keyed by (poi_id, round_number); a re-close is an idempotent upsert.
"""

import json
import logging

from src.config.pgsql_config import get_session_context, text

logger = logging.getLogger(__name__)

_UPSERT = text(
    """
    INSERT INTO public.round_outcomes
        (poi_id, round_number, n, votes_by_role, per_role_consensus,
         overall_consensus, duration_seconds)
    VALUES
        (:poi_id, :round_number, :n, CAST(:votes_by_role AS jsonb),
         CAST(:per_role_consensus AS jsonb), :overall_consensus, :duration_seconds)
    ON CONFLICT (poi_id, round_number) DO UPDATE SET
        n = EXCLUDED.n,
        votes_by_role = EXCLUDED.votes_by_role,
        per_role_consensus = EXCLUDED.per_role_consensus,
        overall_consensus = EXCLUDED.overall_consensus,
        duration_seconds = EXCLUDED.duration_seconds,
        recorded_at = now()
    """
)


class OutcomesRepository:
    def save_outcome(self, outcome, duration_seconds) -> bool:
        """Persist one closed Round's outcome. Never raises (best-effort)."""
        params = {
            "poi_id": int(outcome.poi_id),
            "round_number": outcome.round_number,
            "n": outcome.n,
            "votes_by_role": json.dumps(outcome.votes_by_role),
            "per_role_consensus": json.dumps(outcome.per_role_consensus),
            "overall_consensus": outcome.overall_consensus,
            "duration_seconds": duration_seconds,
        }
        try:
            with get_session_context() as session:
                session.execute(_UPSERT, params)
                session.commit()
            return True
        except Exception as exc:  # noqa: BLE001 — persistence is best-effort
            logger.warning(
                "round_outcomes persist skipped for poi=%s round=%s (%s); apply "
                "db/round-schema.sql so the table+grant exist",
                outcome.poi_id,
                outcome.round_number,
                exc,
            )
            return False
