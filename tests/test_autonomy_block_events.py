"""
Tests for autonomy_block_events governance audit breadcrumb feature.

Invariants:
1. Block events are recorded when autonomy blocks a tool call
2. The autonomy_block_events list is append-only (only grows during a run)
3. Each event contains: tool_name, domain, risk, reason, timestamp
"""

import pytest
from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Ensure parent is in path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAutonomyBlockEventsField:
    """Test that RunLog has autonomy_block_events field."""

    def test_runlog_has_block_events_field(self):
        """RunLog dataclass should have autonomy_block_events list field."""
        from orchestrator import RunLog

        run = RunLog(
            run_id="test_run",
            started_at="2026-02-18T08:00:00Z",
            finished_at=None,
            intent="test",
            intent_normalized="test",
            args={},
            dry_run=False,
            sensitivity="internal",
            rules_checked=False,
            rules_applicable=[],
            rules_decisions=[]
        )

        # Field exists and is a list
        assert hasattr(run, "autonomy_block_events")
        assert isinstance(run.autonomy_block_events, list)
        assert run.autonomy_block_events == []

    def test_block_events_initialized_empty(self):
        """Block events should start as empty list."""
        from orchestrator import RunLog

        run = RunLog(
            run_id="test_run",
            started_at="2026-02-18T08:00:00Z",
            finished_at=None,
            intent="test",
            intent_normalized="test",
            args={},
            dry_run=False,
            sensitivity="internal",
            rules_checked=False,
            rules_applicable=[],
            rules_decisions=[]
        )

        assert len(run.autonomy_block_events) == 0


class TestAutonomyBlockEventsSerialization:
    """Test that block events are serialized in run logs."""

    def test_run_to_dict_includes_block_events(self):
        """_run_to_dict should include autonomy_block_events in execution section."""
        from orchestrator import Orchestrator, RunLog

        # Create minimal orchestrator
        orchestrator = Orchestrator(
            memory_dir=Path("/tmp/test_duro"),
            rules_module=MagicMock(),
            skills_module=MagicMock(),
            artifact_store=MagicMock()
        )

        # Create run with block events
        run = RunLog(
            run_id="test_run",
            started_at="2026-02-18T08:00:00Z",
            finished_at="2026-02-18T08:00:01Z",
            intent="test",
            intent_normalized="test",
            args={},
            dry_run=False,
            sensitivity="internal",
            rules_checked=True,
            rules_applicable=[],
            rules_decisions=[]
        )
        run.autonomy_block_events = [
            {
                "tool_name": "delete_file",
                "domain": "code_changes",
                "risk": "destructive",
                "reason": "insufficient reputation",
                "timestamp": "2026-02-18T08:00:00.500Z"
            }
        ]

        # Serialize
        result = orchestrator._run_to_dict(run)

        # Check block events are in execution section
        assert "execution" in result
        assert "autonomy_block_events" in result["execution"]
        assert len(result["execution"]["autonomy_block_events"]) == 1
        assert result["execution"]["autonomy_block_events"][0]["tool_name"] == "delete_file"


class TestAppendOnlyInvariant:
    """Test that autonomy_block_events is append-only."""

    def test_block_events_only_grows(self):
        """Block events list should only grow, never shrink."""
        from orchestrator import RunLog

        run = RunLog(
            run_id="test_run",
            started_at="2026-02-18T08:00:00Z",
            finished_at=None,
            intent="test",
            intent_normalized="test",
            args={},
            dry_run=False,
            sensitivity="internal",
            rules_checked=False,
            rules_applicable=[],
            rules_decisions=[]
        )

        # Track sizes
        sizes = [len(run.autonomy_block_events)]

        # Append events
        run.autonomy_block_events.append({
            "tool_name": "tool1",
            "domain": "general",
            "risk": "read",
            "reason": "test1",
            "timestamp": "2026-02-18T08:00:00Z"
        })
        sizes.append(len(run.autonomy_block_events))

        run.autonomy_block_events.append({
            "tool_name": "tool2",
            "domain": "code_changes",
            "risk": "destructive",
            "reason": "test2",
            "timestamp": "2026-02-18T08:00:01Z"
        })
        sizes.append(len(run.autonomy_block_events))

        run.autonomy_block_events.append({
            "tool_name": "tool3",
            "domain": "decisions",
            "risk": "write",
            "reason": "test3",
            "timestamp": "2026-02-18T08:00:02Z"
        })
        sizes.append(len(run.autonomy_block_events))

        # Verify monotonic growth
        for i in range(1, len(sizes)):
            assert sizes[i] >= sizes[i-1], f"List shrank at step {i}: {sizes[i-1]} -> {sizes[i]}"

        # Verify final size
        assert len(run.autonomy_block_events) == 3

    def test_events_preserve_order(self):
        """Events should be in append order (oldest first)."""
        from orchestrator import RunLog

        run = RunLog(
            run_id="test_run",
            started_at="2026-02-18T08:00:00Z",
            finished_at=None,
            intent="test",
            intent_normalized="test",
            args={},
            dry_run=False,
            sensitivity="internal",
            rules_checked=False,
            rules_applicable=[],
            rules_decisions=[]
        )

        # Append in order
        for i in range(5):
            run.autonomy_block_events.append({
                "tool_name": f"tool_{i}",
                "domain": "test",
                "risk": "read",
                "reason": f"reason_{i}",
                "timestamp": f"2026-02-18T08:00:0{i}Z"
            })

        # Verify order preserved
        for i, event in enumerate(run.autonomy_block_events):
            assert event["tool_name"] == f"tool_{i}"
            assert event["reason"] == f"reason_{i}"


class TestBlockEventStructure:
    """Test that block events have required fields."""

    def test_event_has_required_fields(self):
        """Each block event should have all required fields."""
        required_fields = {"tool_name", "domain", "risk", "reason", "timestamp"}

        event = {
            "tool_name": "delete_artifact",
            "domain": "code_changes",
            "risk": "destructive",
            "reason": "L3 requires approval token",
            "timestamp": "2026-02-18T08:00:00.123Z"
        }

        # All required fields present
        assert required_fields.issubset(event.keys())

    def test_timestamp_is_iso_format(self):
        """Timestamp should be ISO 8601 format."""
        from orchestrator import utc_now_iso

        timestamp = utc_now_iso()

        # Should be parseable as ISO datetime
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            parsed = True
        except ValueError:
            parsed = False

        assert parsed, f"Timestamp {timestamp} is not valid ISO format"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
