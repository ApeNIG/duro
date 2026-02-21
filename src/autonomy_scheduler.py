# C:\Users\sibag\.agent\src\autonomy_scheduler.py
"""
Autonomy scheduler for Duro.

Coordinates autonomous behaviors with idempotency:
- Session start with cheap checks + caching
- Background maintenance with jitter + resilience
- Auto-reinforcement with cooldown
- Result buffering to surfacing layer
"""
from __future__ import annotations

import asyncio
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from .autonomy_state import AutonomyStateStore
from .surfacing import QuietModeCalculator, ResultBuffer, FeedbackTracker

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


@dataclass
class MaintenanceTask:
    """Definition of a maintenance task."""
    name: str
    interval: timedelta
    callable: Callable[[], Dict[str, Any]]  # sync callable
    priority: int = 30  # priority for notable results


class MaintenanceScheduler:
    """
    Background maintenance with persistence, jitter, resilience.

    Design:
    - Tasks are injectable sync callables
    - Uses asyncio.to_thread() to avoid blocking
    - Persists last_run timestamps
    - Wraps each task in try/except
    - Initial jitter to avoid thundering herd
    """

    DEFAULT_SCHEDULES: Dict[str, timedelta] = {
        "decay": timedelta(hours=24),
        "decision_review": timedelta(days=7),
        "health_check": timedelta(hours=6),
        "orphan_cleanup": timedelta(days=3),
    }

    def __init__(
        self,
        state: AutonomyStateStore,
        buffer: ResultBuffer,
        tasks: Optional[Dict[str, MaintenanceTask]] = None,
    ):
        self.state = state
        self.buffer = buffer
        self.tasks: Dict[str, MaintenanceTask] = tasks or {}
        self._running: Set[str] = set()
        self._stop_event = asyncio.Event()

    def register_task(
        self,
        name: str,
        callable: Callable[[], Dict[str, Any]],
        interval: Optional[timedelta] = None,
        priority: int = 30,
    ) -> None:
        """Register a maintenance task with a sync callable."""
        interval = interval or self.DEFAULT_SCHEDULES.get(name, timedelta(hours=24))
        self.tasks[name] = MaintenanceTask(
            name=name,
            interval=interval,
            callable=callable,
            priority=priority,
        )

    async def maintenance_loop(self) -> None:
        """
        Background loop. Wrapped in try/except, with jitter.

        Call this as: asyncio.create_task(scheduler.maintenance.maintenance_loop())
        """
        # Initial jitter: 0-60 seconds
        await asyncio.sleep(random.uniform(0, 60))

        while not self._stop_event.is_set():
            try:
                await self._check_and_run_due()
            except Exception as e:
                # Log but don't die
                logger.error(f"Maintenance loop error: {e}", exc_info=True)

            # Check every 5 minutes
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=300)
                break  # Stop event was set
            except asyncio.TimeoutError:
                pass  # Continue looping

    def stop(self) -> None:
        """Signal the maintenance loop to stop."""
        self._stop_event.set()

    async def _check_and_run_due(self) -> None:
        """Check and run any due maintenance tasks."""
        now = utc_now()

        for name, task in self.tasks.items():
            if name in self._running:
                continue

            key = f"maintenance.last_run.{name}"
            last_run_str = self.state.get(key)

            if last_run_str:
                try:
                    last_run = datetime.fromisoformat(str(last_run_str))
                    elapsed = now - last_run
                    if elapsed < task.interval:
                        continue
                except (ValueError, TypeError):
                    pass  # Invalid timestamp, run anyway

            # Run with isolation
            self._running.add(name)
            try:
                result = await self._run_task(task)
                self.state.set(key, utc_now_iso())

                # Queue notable results
                if result and result.get("notable"):
                    self.buffer.enqueue(
                        event_type=f"maintenance_{name}",
                        payload=result,
                        priority=result.get("priority", task.priority),
                        dedupe_key=f"maint:{name}:{now.date()}",
                    )
            except Exception as e:
                logger.error(f"Maintenance task {name} failed: {e}", exc_info=True)
            finally:
                self._running.discard(name)

    async def _run_task(self, task: MaintenanceTask) -> Dict[str, Any]:
        """Run a single task in a thread to avoid blocking."""
        try:
            result = await asyncio.to_thread(task.callable)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as e:
            logger.error(f"Task {task.name} raised: {e}", exc_info=True)
            return {"error": str(e), "notable": False}

    async def run_now(self, task_name: str) -> Dict[str, Any]:
        """Manual trigger for any maintenance task (async version)."""
        if task_name not in self.tasks:
            return {"error": f"Unknown task: {task_name}", "available": list(self.tasks.keys())}

        task = self.tasks[task_name]
        result = await self._run_task(task)

        # Update last_run
        self.state.set(f"maintenance.last_run.{task_name}", utc_now_iso())

        return result

    def run_now_sync(self, task_name: str) -> Dict[str, Any]:
        """Manual trigger for any maintenance task (sync version for thread pool).

        Use this from sync contexts running in a thread pool executor.
        Directly calls the sync callable without async overhead.
        """
        if task_name not in self.tasks:
            return {"error": f"Unknown task: {task_name}", "available": list(self.tasks.keys())}

        task = self.tasks[task_name]

        # Tasks have sync callables - call directly
        try:
            result = task.callable()
            result = result if isinstance(result, dict) else {"result": result}
        except Exception as e:
            logger.error(f"Task {task_name} raised: {e}", exc_info=True)
            result = {"error": str(e), "notable": False}

        # Update last_run
        self.state.set(f"maintenance.last_run.{task_name}", utc_now_iso())

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get maintenance scheduler status."""
        status = {
            "tasks": {},
            "running": list(self._running),
        }

        now = utc_now()
        for name, task in self.tasks.items():
            key = f"maintenance.last_run.{name}"
            last_run_str = self.state.get(key)

            task_status = {
                "interval_hours": task.interval.total_seconds() / 3600,
                "priority": task.priority,
                "last_run": last_run_str,
                "is_running": name in self._running,
            }

            if last_run_str:
                try:
                    last_run = datetime.fromisoformat(str(last_run_str))
                    elapsed = now - last_run
                    task_status["hours_since_run"] = round(elapsed.total_seconds() / 3600, 1)
                    task_status["is_due"] = elapsed >= task.interval
                except (ValueError, TypeError):
                    task_status["is_due"] = True
            else:
                task_status["is_due"] = True

            status["tasks"][name] = task_status

        return status


class AutonomyScheduler:
    """
    Coordinates autonomous behaviors with idempotency.

    Design:
    - ensure_session_started() is idempotent with cache + TTL
    - Cheap checks only in session start (heavy work deferred to maintenance)
    - track_retrieval() with top-3 limit and cooldown
    - Integrates with surfacing layer
    """

    SESSION_CACHE_TTL_SECONDS = 180  # 3 minutes

    def __init__(
        self,
        *,
        state: AutonomyStateStore,
        artifact_store: Any,
        reputation_store: Any,
        index: Any,
        # Callables for fetching data (sync)
        get_pending_decisions: Optional[Callable[[], List[Dict]]] = None,
        get_stale_facts: Optional[Callable[[], List[Dict]]] = None,
    ):
        self.state = state
        self.artifact_store = artifact_store
        self.reputation = reputation_store
        self.index = index

        # Callables for cheap checks
        self._get_pending_decisions = get_pending_decisions
        self._get_stale_facts = get_stale_facts

        # Surfacing layer
        self.feedback = FeedbackTracker(
            load_state_cb=self.state.get,
            save_state_cb=self.state.set,
        )
        self.buffer = ResultBuffer(
            load_state_cb=self.state.get,
            save_state_cb=self.state.set,
        )
        self.quiet_mode = QuietModeCalculator(
            load_state_cb=self.state.get,
            save_state_cb=self.state.set,
            feedback_tracker=self.feedback,
        )

        # Maintenance scheduler
        self.maintenance = MaintenanceScheduler(
            state=self.state,
            buffer=self.buffer,
        )

        # Idempotency guards
        self._session_lock = asyncio.Lock()
        self._session_lock_sync = threading.Lock()  # For sync version
        self._session_cache: Optional[Dict[str, Any]] = None
        self._session_cache_at: Optional[float] = None

    def _is_cache_valid(self) -> bool:
        """Check if session cache is still valid."""
        if self._session_cache is None or self._session_cache_at is None:
            return False
        elapsed = time.time() - self._session_cache_at
        return elapsed < self.SESSION_CACHE_TTL_SECONDS

    async def ensure_session_started(self, context: str = "") -> Dict[str, Any]:
        """
        Idempotent session start. Fast no-op after first call within TTL.

        Returns cached result if within TTL, otherwise runs cheap checks.
        """
        async with self._session_lock:
            # Check cache TTL
            if self._is_cache_valid():
                return {"cached": True, **self._session_cache}

            # First call or cache expired: do real work
            results = await self._run_session_start(context)
            self._session_cache = results
            self._session_cache_at = time.time()
            return {"cached": False, **results}

    async def _run_session_start(self, context: str) -> Dict[str, Any]:
        """
        Cheap checks only. Queue insights, don't block.

        Heavy work (like scanning 500 facts for staleness) is done
        in maintenance loop and cached there.
        """
        pending_decisions: List[Dict] = []
        stale_facts: List[Dict] = []

        # Run cheap checks with timeouts
        try:
            if self._get_pending_decisions:
                pending_decisions = await asyncio.wait_for(
                    asyncio.to_thread(self._get_pending_decisions),
                    timeout=2.0,
                )
        except asyncio.TimeoutError:
            logger.warning("Pending decisions check timed out")
        except Exception as e:
            logger.error(f"Pending decisions check failed: {e}")

        try:
            if self._get_stale_facts:
                stale_facts = await asyncio.wait_for(
                    asyncio.to_thread(self._get_stale_facts),
                    timeout=2.0,
                )
        except asyncio.TimeoutError:
            logger.warning("Stale facts check timed out")
        except Exception as e:
            logger.error(f"Stale facts check failed: {e}")

        # Queue to buffer (don't surface yet)
        for d in pending_decisions[:5]:
            self.buffer.enqueue(
                event_type="pending_decision",
                payload=d,
                priority=70,
                dedupe_key=f"decision:{d.get('id', 'unknown')}",
            )

        for f in stale_facts[:5]:
            self.buffer.enqueue(
                event_type="stale_fact",
                payload=f,
                priority=50,
                dedupe_key=f"stale:{f.get('id', 'unknown')}",
            )

        # Record session start
        self.state.set("session.last_started_at", utc_now_iso())

        return {
            "pending_decisions": len(pending_decisions),
            "stale_facts": len(stale_facts),
            "buffer_size": self.buffer.size(),
        }

    def ensure_session_started_sync(self, context: str = "") -> Dict[str, Any]:
        """
        Sync version of ensure_session_started for thread pool contexts.

        Idempotent session start. Fast no-op after first call within TTL.
        Directly calls sync callables without async overhead.
        """
        with self._session_lock_sync:
            # Check cache TTL
            if self._is_cache_valid():
                return {"cached": True, **self._session_cache}

            # First call or cache expired: do real work
            results = self._run_session_start_sync(context)
            self._session_cache = results
            self._session_cache_at = time.time()
            return {"cached": False, **results}

    def _run_session_start_sync(self, context: str) -> Dict[str, Any]:
        """
        Sync version of cheap checks. Queue insights, don't block.
        """
        pending_decisions: List[Dict] = []
        stale_facts: List[Dict] = []

        # Run cheap checks (sync callables)
        try:
            if self._get_pending_decisions:
                pending_decisions = self._get_pending_decisions() or []
        except Exception as e:
            logger.error(f"Pending decisions check failed: {e}")

        try:
            if self._get_stale_facts:
                stale_facts = self._get_stale_facts() or []
        except Exception as e:
            logger.error(f"Stale facts check failed: {e}")

        # Queue to buffer (don't surface yet)
        for d in pending_decisions[:5]:
            self.buffer.enqueue(
                event_type="pending_decision",
                payload=d,
                priority=70,
                dedupe_key=f"decision:{d.get('id', 'unknown')}",
            )

        for f in stale_facts[:5]:
            self.buffer.enqueue(
                event_type="stale_fact",
                payload=f,
                priority=50,
                dedupe_key=f"stale:{f.get('id', 'unknown')}",
            )

        # Record session start
        self.state.set("session.last_started_at", utc_now_iso())

        return {
            "pending_decisions": len(pending_decisions),
            "stale_facts": len(stale_facts),
            "buffer_size": self.buffer.size(),
        }

    def track_retrieval(
        self,
        results: List[Dict],
        source: str = "unknown",
        max_reinforce: int = 3,
    ) -> int:
        """
        Auto-reinforce top N facts only, with cooldown.

        Args:
            results: List of result objects with at least {id, type}
            source: Source of retrieval (e.g., "semantic_search", "proactive_recall")
            max_reinforce: Maximum number to reinforce (default 3)

        Returns:
            Number of artifacts reinforced
        """
        # Don't reinforce proactive recall - wait for confirmation
        if source == "proactive_recall":
            return 0

        COOLDOWN_MINUTES = 60
        now = utc_now()
        reinforced = 0

        # Filter to facts only using the type from results (no extra lookup)
        facts = [r for r in results if r.get("type") == "fact"]

        for result in facts[:max_reinforce]:
            artifact_id = result.get("id")
            if not artifact_id:
                continue

            # Check cooldown
            key = f"reinforcement.recent.{artifact_id}"
            last_str = self.state.get(key)
            if last_str:
                try:
                    last = datetime.fromisoformat(str(last_str))
                    elapsed_minutes = (now - last).total_seconds() / 60
                    if elapsed_minutes < COOLDOWN_MINUTES:
                        continue
                except (ValueError, TypeError):
                    pass  # Invalid timestamp, proceed

            # Reinforce
            try:
                if hasattr(self.index, 'increment_reinforcement'):
                    self.index.increment_reinforcement(artifact_id)
                    self.state.set(key, utc_now_iso())
                    reinforced += 1
            except Exception as e:
                logger.error(f"Failed to reinforce {artifact_id}: {e}")

        return reinforced

    def get_surfacing_events(
        self,
        max_items: int = 3,
        context: str = "",
        type_filter: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get events for surfacing, respecting quiet mode.

        Returns:
            {
                "events": [...],
                "quiet_mode": {...},
                "surfaced": bool
            }
        """
        # Get reputation score
        rep_score = 0.5
        if hasattr(self.reputation, 'global_score'):
            rep_score = float(self.reputation.global_score or 0.5)

        # Check quiet mode
        quiet_state = self.quiet_mode.should_be_quiet(context, rep_score)

        # If quiet override, return nothing
        if quiet_state.decision == "quiet":
            return {
                "events": [],
                "quiet_mode": {
                    "decision": quiet_state.decision,
                    "quiet_score": quiet_state.quiet_score,
                    "factors": quiet_state.factors,
                },
                "surfaced": False,
            }

        # Determine min_priority based on decision
        min_priority = None
        if quiet_state.decision == "critical-only":
            min_priority = 90

        # Pop events
        events = self.buffer.pop_for_surfacing(
            max_items=max_items,
            type_filter=type_filter,
            min_priority=min_priority,
        )

        # Record that we surfaced
        if events:
            self.quiet_mode.record_surfaced([e.get("id", "") for e in events])

        return {
            "events": events,
            "quiet_mode": {
                "decision": quiet_state.decision,
                "quiet_score": quiet_state.quiet_score,
                "factors": quiet_state.factors,
            },
            "surfaced": len(events) > 0,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get full autonomy scheduler status."""
        rep_score = 0.5
        if hasattr(self.reputation, 'global_score'):
            rep_score = float(self.reputation.global_score or 0.5)

        return {
            "session": {
                "cache_valid": self._is_cache_valid(),
                "cache_age_seconds": (
                    round(time.time() - self._session_cache_at, 1)
                    if self._session_cache_at
                    else None
                ),
                "last_started_at": self.state.get("session.last_started_at"),
            },
            "buffer": {
                "size": self.buffer.size(),
                "peek": self.buffer.peek(max_items=3),
            },
            "quiet_mode": self.quiet_mode.get_status(reputation=rep_score),
            "feedback": self.feedback.get_feedback_stats(),
            "maintenance": self.maintenance.get_status(),
        }
