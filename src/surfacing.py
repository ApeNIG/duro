# C:\Users\sibag\.agent\src\surfacing.py
"""
Surfacing layer for autonomous insights.

Handles:
- Result buffering with deduplication
- Quiet mode calculation (reputation, frequency, feedback, context)
- Feedback tracking for learning interruption preferences
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class QuietModeState:
    """
    decision:
      - "normal": ok to surface buffered insights
      - "quiet": minimize interruptions (surface nothing unless user explicitly pulls)
      - "critical-only": only surface priority>=90 items
    """
    decision: str
    quiet_score: float
    factors: Dict[str, float]
    override: Optional[Dict[str, Any]] = None


class ResultBuffer:
    """
    Buffers autonomy results for later surfacing.

    Storage model: persisted "events" with dedupe_key to prevent repeat spam.

    Expected event schema:
      {
        "id": str(uuid),
        "type": "pending_decisions" | "stale_facts" | "health_alert" | ...,
        "priority": int (0-100),
        "payload": dict,
        "created_at_unix": int,
        "updated_at_unix": int,
        "dedupe_key": Optional[str],
      }
    """

    MAX_EVENTS = 200

    def __init__(self, load_state_cb: Callable, save_state_cb: Callable):
        self._load_state = load_state_cb
        self._save_state = save_state_cb

        self._queue: List[Dict[str, Any]] = []
        self._by_dedupe: Dict[str, str] = {}  # dedupe_key -> event_id
        self._hydrate()

    def _hydrate(self) -> None:
        data = self._load_state("autonomy.buffer", default={"queue": []}) or {"queue": []}
        self._queue = list(data.get("queue", []))
        self._rebuild_dedupe_index()

    def _persist(self) -> None:
        self._save_state("autonomy.buffer", {"queue": self._queue})

    def _rebuild_dedupe_index(self) -> None:
        self._by_dedupe = {}
        for ev in self._queue:
            dk = ev.get("dedupe_key")
            if dk:
                self._by_dedupe[str(dk)] = ev["id"]

    def _sort_trim(self) -> None:
        # Higher priority first; newer first
        self._queue.sort(key=lambda x: (-int(x.get("priority", 0)), -int(x.get("updated_at_unix", 0))))
        if len(self._queue) > self.MAX_EVENTS:
            self._queue = self._queue[: self.MAX_EVENTS]

    def enqueue(
        self,
        event_type: str,
        payload: Dict[str, Any],
        priority: int = 50,
        dedupe_key: Optional[str] = None,
    ) -> str:
        now = int(time.time())
        dedupe_key = str(dedupe_key) if dedupe_key else None

        # Dedupe: update existing event instead of adding new
        if dedupe_key and dedupe_key in self._by_dedupe:
            ev_id = self._by_dedupe[dedupe_key]
            for ev in self._queue:
                if ev["id"] == ev_id:
                    ev["payload"] = payload
                    ev["priority"] = int(priority)
                    ev["updated_at_unix"] = now
                    self._sort_trim()
                    self._persist()
                    return ev_id

        ev_id = str(uuid.uuid4())
        ev = {
            "id": ev_id,
            "type": str(event_type),
            "priority": int(priority),
            "payload": payload or {},
            "created_at_unix": now,
            "updated_at_unix": now,
            "dedupe_key": dedupe_key,
        }
        self._queue.append(ev)
        if dedupe_key:
            self._by_dedupe[dedupe_key] = ev_id

        self._sort_trim()
        self._persist()
        return ev_id

    def peek(self, max_items: int = 3) -> List[Dict[str, Any]]:
        self._sort_trim()
        return list(self._queue[: max(0, int(max_items))])

    def pop_for_surfacing(
        self,
        max_items: int = 3,
        *,
        type_filter: Optional[List[str]] = None,
        min_priority: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Pop the top items, optionally filtering by type and/or min priority.
        """
        self._sort_trim()

        filtered = self._queue
        if type_filter:
            allowed = set(type_filter)
            filtered = [ev for ev in filtered if ev.get("type") in allowed]
        if min_priority is not None:
            mp = int(min_priority)
            filtered = [ev for ev in filtered if int(ev.get("priority", 0)) >= mp]

        picked = filtered[: max(0, int(max_items))]
        if not picked:
            return []

        picked_ids = {ev["id"] for ev in picked}
        self._queue = [ev for ev in self._queue if ev["id"] not in picked_ids]
        self._rebuild_dedupe_index()
        self._persist()
        return picked

    def size(self) -> int:
        """Return current queue size."""
        return len(self._queue)

    def clear(self) -> int:
        """Clear all events. Returns count cleared."""
        count = len(self._queue)
        self._queue = []
        self._by_dedupe = {}
        self._persist()
        return count


class FeedbackTracker:
    """
    Tracks explicit feedback on surfacings.
    Used to compute negative feedback rate for quiet mode.

    Persisted key: autonomy.feedback
    Schema:
      {"items": [{"surfacing_id","feedback","notes","ts_unix"}]}
    """

    MAX_ITEMS = 200
    NEGATIVE = {"distracting", "wrong"}

    def __init__(self, load_state_cb: Callable, save_state_cb: Callable):
        self._load_state = load_state_cb
        self._save_state = save_state_cb

    def record_explicit_feedback(self, surfacing_id: str, feedback: str, notes: Optional[str] = None) -> None:
        now = int(time.time())
        data = self._load_state("autonomy.feedback", default={"items": []}) or {"items": []}
        items = list(data.get("items", []))

        items.append(
            {
                "surfacing_id": str(surfacing_id),
                "feedback": str(feedback),
                "notes": notes,
                "ts_unix": now,
            }
        )

        items = items[-self.MAX_ITEMS :]
        self._save_state("autonomy.feedback", {"items": items})

    def negative_feedback_rate(self, window: int = 50) -> float:
        data = self._load_state("autonomy.feedback", default={"items": []}) or {"items": []}
        items = list(data.get("items", []))
        if not items:
            return 0.0

        tail = items[-max(1, int(window)) :]
        neg = sum(1 for x in tail if x.get("feedback") in self.NEGATIVE)
        return float(neg) / float(len(tail))

    def get_feedback_stats(self) -> Dict[str, Any]:
        """Return feedback statistics."""
        data = self._load_state("autonomy.feedback", default={"items": []}) or {"items": []}
        items = list(data.get("items", []))

        counts = {"helpful": 0, "neutral": 0, "distracting": 0, "wrong": 0}
        for item in items:
            fb = item.get("feedback", "")
            if fb in counts:
                counts[fb] += 1

        return {
            "total": len(items),
            "counts": counts,
            "negative_rate": self.negative_feedback_rate(),
        }


class QuietModeCalculator:
    """
    Computes quiet mode as a weighted score in [0,1].

    Inputs:
      - reputation in [0,1]
      - frequency factor from surfacings in last 30 minutes
      - negative feedback rate over last N surfacings
      - context busyness heuristic

    Quiet override:
      - stored in autonomy.quiet_override
      - {"enabled": True, "until_unix": ...}
    """

    WEIGHTS = {
        "reputation": 0.30,
        "frequency": 0.25,
        "feedback": 0.25,
        "context": 0.20,
    }

    def __init__(self, load_state_cb: Callable, save_state_cb: Callable, feedback_tracker: FeedbackTracker):
        self._load_state = load_state_cb
        self._save_state = save_state_cb
        self._feedback = feedback_tracker

    # ---------- override controls ----------

    def set_override(self, enabled: bool, duration_minutes: int = 60) -> None:
        if not enabled:
            self._save_state("autonomy.quiet_override", {"enabled": False})
            return
        until = int(time.time()) + max(1, int(duration_minutes)) * 60
        self._save_state("autonomy.quiet_override", {"enabled": True, "until_unix": until})

    def get_override(self) -> Optional[Dict[str, Any]]:
        ovr = self._load_state("autonomy.quiet_override", default={"enabled": False}) or {"enabled": False}
        if not ovr.get("enabled"):
            return None
        until = int(ovr.get("until_unix", 0))
        if until <= int(time.time()):
            self._save_state("autonomy.quiet_override", {"enabled": False})
            return None
        return ovr

    # ---------- frequency tracking ----------

    def record_surfaced(self, surfacing_ids: List[str]) -> None:
        """
        Store timestamps to compute "surfacings in last 30 minutes".
        """
        data = self._load_state("autonomy.surfacing_stats", default={"shown_ts_unix": []}) or {"shown_ts_unix": []}
        ts = [int(x) for x in data.get("shown_ts_unix", [])]
        now = int(time.time())
        # Add one timestamp per surfaced item (rough but effective)
        ts.extend([now] * max(1, len(surfacing_ids)))
        ts = ts[-200:]
        self._save_state("autonomy.surfacing_stats", {"shown_ts_unix": ts})

    def _frequency_factor(self) -> float:
        data = self._load_state("autonomy.surfacing_stats", default={"shown_ts_unix": []}) or {"shown_ts_unix": []}
        ts = [int(x) for x in data.get("shown_ts_unix", [])]
        now = int(time.time())
        # keep only last 30 min
        ts = [x for x in ts if now - x <= 30 * 60]
        self._save_state("autonomy.surfacing_stats", {"shown_ts_unix": ts})

        cap = 3  # 3 surfacings/30min -> full quiet factor
        return min(1.0, float(len(ts)) / float(cap))

    # ---------- context heuristic ----------

    def _context_busyness(self, context: str) -> float:
        # Dumb on purpose; upgrade later with real signals.
        text = (context or "").lower()
        busy_words = ["urgent", "deadline", "incident", "prod", "hotfix", "broken", "debug", "panic"]
        return 1.0 if any(w in text for w in busy_words) else 0.0

    # ---------- main decision ----------

    def should_be_quiet(self, context: str, reputation: float) -> QuietModeState:
        ovr = self.get_override()
        if ovr:
            return QuietModeState(
                decision="quiet",
                quiet_score=1.0,
                factors={"override": 1.0},
                override=ovr,
            )

        rep = max(0.0, min(1.0, float(reputation)))
        reputation_factor = 1.0 - rep
        frequency_factor = self._frequency_factor()
        feedback_factor = max(0.0, min(1.0, self._feedback.negative_feedback_rate(window=50)))
        context_factor = self._context_busyness(context)

        score = (
            self.WEIGHTS["reputation"] * reputation_factor
            + self.WEIGHTS["frequency"] * frequency_factor
            + self.WEIGHTS["feedback"] * feedback_factor
            + self.WEIGHTS["context"] * context_factor
        )
        score = max(0.0, min(1.0, float(score)))

        if score > 0.85:
            decision = "critical-only"
        elif score > 0.60:
            decision = "quiet"
        else:
            decision = "normal"

        return QuietModeState(
            decision=decision,
            quiet_score=score,
            factors={
                "reputation_factor": reputation_factor,
                "frequency_factor": frequency_factor,
                "feedback_factor": feedback_factor,
                "context_factor": context_factor,
            },
            override=None,
        )

    def get_status(self, context: str = "", reputation: float = 0.5) -> Dict[str, Any]:
        """Get full quiet mode status for debugging/tools."""
        state = self.should_be_quiet(context, reputation)
        return {
            "decision": state.decision,
            "quiet_score": state.quiet_score,
            "factors": state.factors,
            "override": state.override,
            "feedback_stats": self._feedback.get_feedback_stats(),
        }
