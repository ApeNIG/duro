"""
Tests for progress callbacks in skill_runner.

Tests cover:
- ProgressUpdate dataclass
- ProgressReporter class
- AggregateProgressReporter class
- SkillRunner integration with progress callbacks
- Helper functions (report_progress, create_progress_reporter)
- Edge cases (no callback, callback errors)
"""

import pytest
import sys
import time
from pathlib import Path
from typing import List
from unittest.mock import Mock, patch

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from skill_runner import (
    ProgressEvent,
    ProgressUpdate,
    ProgressCallback,
    ProgressReporter,
    AggregateProgressReporter,
    SkillRunner,
    SkillResult,
    report_progress,
    create_progress_reporter,
)


class TestProgressUpdate:
    """Test ProgressUpdate dataclass."""

    def test_basic_creation(self):
        update = ProgressUpdate(
            event=ProgressEvent.PROGRESS,
            current=50,
            total=100,
            message="Half done",
            percentage=50.0,
            elapsed_ms=1000.0
        )
        assert update.current == 50
        assert update.total == 100
        assert update.percentage == 50.0

    def test_is_terminal_completed(self):
        update = ProgressUpdate(
            event=ProgressEvent.COMPLETED,
            current=100,
            total=100,
            message="Done",
            percentage=100.0,
            elapsed_ms=2000.0
        )
        assert update.is_terminal is True

    def test_is_terminal_error(self):
        update = ProgressUpdate(
            event=ProgressEvent.ERROR,
            current=50,
            total=100,
            message="Failed",
            percentage=50.0,
            elapsed_ms=1500.0
        )
        assert update.is_terminal is True

    def test_is_terminal_progress(self):
        update = ProgressUpdate(
            event=ProgressEvent.PROGRESS,
            current=50,
            total=100,
            message="Working",
            percentage=50.0,
            elapsed_ms=1000.0
        )
        assert update.is_terminal is False

    def test_to_dict(self):
        update = ProgressUpdate(
            event=ProgressEvent.STARTED,
            current=0,
            total=100,
            message="Starting",
            percentage=0.0,
            elapsed_ms=0.0,
            metadata={"key": "value"}
        )
        d = update.to_dict()
        assert d["event"] == "started"
        assert d["metadata"] == {"key": "value"}


class TestProgressReporter:
    """Test ProgressReporter class."""

    def test_basic_usage(self):
        updates: List[ProgressUpdate] = []
        def callback(update: ProgressUpdate):
            updates.append(update)

        reporter = ProgressReporter(total=10, callback=callback)
        reporter.start("Starting...")
        reporter.update(5, "Halfway")
        reporter.complete("Done!")

        assert len(updates) == 3
        assert updates[0].event == ProgressEvent.STARTED
        assert updates[1].event == ProgressEvent.PROGRESS
        assert updates[1].current == 5
        assert updates[2].event == ProgressEvent.COMPLETED

    def test_no_callback(self):
        reporter = ProgressReporter(total=10, callback=None)
        # Should not raise
        reporter.start()
        reporter.update(5)
        reporter.complete()
        assert reporter.current == 10

    def test_percentage_calculation(self):
        updates: List[ProgressUpdate] = []
        reporter = ProgressReporter(total=100, callback=lambda u: updates.append(u))
        reporter.update(25)
        assert updates[0].percentage == 25.0

    def test_substep(self):
        updates: List[ProgressUpdate] = []
        reporter = ProgressReporter(total=10, callback=lambda u: updates.append(u))
        reporter.update(5, "Processing file")
        reporter.substep("parsing", "Parsing content")

        assert updates[-1].event == ProgressEvent.SUBSTEP
        assert updates[-1].substep == "parsing"

    def test_error_event(self):
        updates: List[ProgressUpdate] = []
        reporter = ProgressReporter(total=10, callback=lambda u: updates.append(u))
        reporter.update(5)
        reporter.error("Something went wrong")

        assert updates[-1].event == ProgressEvent.ERROR
        assert "wrong" in updates[-1].message

    def test_estimated_remaining(self):
        updates: List[ProgressUpdate] = []
        reporter = ProgressReporter(total=100, callback=lambda u: updates.append(u))
        reporter.start()
        time.sleep(0.05)  # Small delay to get measurable elapsed time
        reporter.update(50, "Half done")

        # Should have an estimate
        assert updates[-1].estimated_remaining_ms is not None

    def test_history(self):
        reporter = ProgressReporter(total=10, callback=None)
        reporter.start()
        reporter.update(5)
        reporter.complete()

        history = reporter.history
        assert len(history) == 3
        assert history[0].event == ProgressEvent.STARTED
        assert history[-1].event == ProgressEvent.COMPLETED

    def test_callback_error_handled(self):
        def failing_callback(update: ProgressUpdate):
            raise ValueError("Callback error")

        reporter = ProgressReporter(total=10, callback=failing_callback)
        # Should not raise - callback errors are swallowed
        reporter.start()
        reporter.update(5)
        reporter.complete()

    def test_zero_total(self):
        updates: List[ProgressUpdate] = []
        reporter = ProgressReporter(total=0, callback=lambda u: updates.append(u))
        reporter.update(0, "Processing")
        # Should handle gracefully
        assert updates[0].percentage == 0.0


class TestAggregateProgressReporter:
    """Test AggregateProgressReporter class."""

    def test_basic_aggregation(self):
        updates: List[ProgressUpdate] = []
        agg = AggregateProgressReporter(callback=lambda u: updates.append(u))

        agg.add_stage("download", total=100, weight=1)
        agg.add_stage("process", total=100, weight=1)

        download = agg.get_reporter("download")
        download.update(50)

        # 50% of download (weight 1) = 25% overall
        assert len(updates) == 1
        assert 24 <= updates[-1].percentage <= 26  # Allow small variance

    def test_weighted_aggregation(self):
        updates: List[ProgressUpdate] = []
        agg = AggregateProgressReporter(callback=lambda u: updates.append(u))

        # Download is 1/4 of total, process is 3/4
        agg.add_stage("download", total=100, weight=1)
        agg.add_stage("process", total=100, weight=3)

        download = agg.get_reporter("download")
        download.update(100)  # Complete download

        # 100% of download (weight 1 of 4) = 25%
        assert 24 <= updates[-1].percentage <= 26

    def test_unknown_stage_raises(self):
        agg = AggregateProgressReporter()
        with pytest.raises(ValueError):
            agg.get_reporter("unknown")

    def test_stage_metadata(self):
        updates: List[ProgressUpdate] = []
        agg = AggregateProgressReporter(callback=lambda u: updates.append(u))
        agg.add_stage("test", total=100)

        reporter = agg.get_reporter("test")
        reporter.update(50)

        assert updates[-1].metadata["stage"] == "test"


class TestSkillRunnerProgress:
    """Test SkillRunner integration with progress callbacks."""

    def test_callback_receives_started(self):
        updates: List[ProgressUpdate] = []
        runner = SkillRunner(
            project_root=Path.home() / ".agent",
            allowed_roots=[Path.home() / ".agent"]
        )

        def simple_skill(**kwargs):
            return SkillResult(success=True, summary="Done", run_id="", timestamp="")

        runner.run(
            simple_skill,
            args={},
            progress_callback=lambda u: updates.append(u)
        )

        assert any(u.event == ProgressEvent.STARTED for u in updates)

    def test_callback_receives_completed(self):
        updates: List[ProgressUpdate] = []
        runner = SkillRunner(
            project_root=Path.home() / ".agent",
            allowed_roots=[Path.home() / ".agent"]
        )

        def simple_skill(**kwargs):
            return SkillResult(success=True, summary="Done", run_id="", timestamp="")

        runner.run(
            simple_skill,
            args={},
            progress_callback=lambda u: updates.append(u)
        )

        assert any(u.event == ProgressEvent.COMPLETED for u in updates)

    def test_callback_receives_error_on_exception(self):
        updates: List[ProgressUpdate] = []
        runner = SkillRunner(
            project_root=Path.home() / ".agent",
            allowed_roots=[Path.home() / ".agent"]
        )

        def failing_skill(**kwargs):
            raise ValueError("Skill error")

        runner.run(
            failing_skill,
            args={},
            progress_callback=lambda u: updates.append(u)
        )

        assert any(u.event == ProgressEvent.ERROR for u in updates)

    def test_callback_passed_to_skill(self):
        received_callback = [None]
        runner = SkillRunner(
            project_root=Path.home() / ".agent",
            allowed_roots=[Path.home() / ".agent"]
        )

        def skill_checks_callback(**kwargs):
            received_callback[0] = kwargs.get("_progress_callback")
            return SkillResult(success=True, summary="Done", run_id="", timestamp="")

        callback = lambda u: None
        runner.run(skill_checks_callback, args={}, progress_callback=callback)

        assert received_callback[0] is callback

    def test_no_callback_works(self):
        runner = SkillRunner(
            project_root=Path.home() / ".agent",
            allowed_roots=[Path.home() / ".agent"]
        )

        def simple_skill(**kwargs):
            return SkillResult(success=True, summary="Done", run_id="", timestamp="")

        # Should not raise
        result = runner.run(simple_skill, args={})
        assert result.success is True


class TestHelperFunctions:
    """Test helper functions for skills."""

    def test_report_progress_with_reporter(self):
        updates: List[ProgressUpdate] = []
        reporter = ProgressReporter(total=10, callback=lambda u: updates.append(u))

        tools = {"_progress_reporter": reporter}
        report_progress(tools, current=5, total=10, message="Halfway")

        assert len(updates) == 1
        assert updates[0].current == 5

    def test_report_progress_no_reporter(self):
        tools = {}
        # Should not raise
        report_progress(tools, current=5, total=10)

    def test_create_progress_reporter(self):
        callback = Mock()
        tools = {"_progress_callback": callback}

        reporter = create_progress_reporter(tools, total=100, label="test")
        reporter.update(50)

        callback.assert_called_once()

    def test_create_progress_reporter_no_callback(self):
        tools = {}
        reporter = create_progress_reporter(tools, total=100)
        # Should work, just with no-op callback
        reporter.update(50)
        assert reporter.current == 50


class TestProgressEventEnum:
    """Test ProgressEvent enum."""

    def test_all_events(self):
        events = [e.value for e in ProgressEvent]
        assert "started" in events
        assert "progress" in events
        assert "substep" in events
        assert "completed" in events
        assert "error" in events


class TestEdgeCases:
    """Test edge cases."""

    def test_rapid_updates(self):
        updates: List[ProgressUpdate] = []
        reporter = ProgressReporter(total=1000, callback=lambda u: updates.append(u))

        for i in range(1000):
            reporter.update(i + 1)

        assert len(updates) == 1000
        assert updates[-1].percentage == 100.0

    def test_out_of_order_updates(self):
        updates: List[ProgressUpdate] = []
        reporter = ProgressReporter(total=100, callback=lambda u: updates.append(u))

        reporter.update(50)
        reporter.update(25)  # Going backwards
        reporter.update(75)

        # Should record all updates as-is
        assert updates[0].current == 50
        assert updates[1].current == 25
        assert updates[2].current == 75

    def test_large_total(self):
        updates: List[ProgressUpdate] = []
        reporter = ProgressReporter(total=1000000, callback=lambda u: updates.append(u))
        reporter.update(500000)

        assert updates[0].percentage == 50.0

    def test_metadata_preservation(self):
        updates: List[ProgressUpdate] = []
        reporter = ProgressReporter(total=100, callback=lambda u: updates.append(u))
        reporter.update(50, metadata={"file": "test.txt", "count": 42})

        assert updates[0].metadata["file"] == "test.txt"
        assert updates[0].metadata["count"] == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
