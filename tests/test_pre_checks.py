"""
Tests for pre-check system in skill_runner.py.

Tests cover:
- ffmpeg availability check
- Network connectivity check
- Python dependency checks
- Git repository check
- Caching behavior
- Pre-check runner integration with SkillRunner
"""

import pytest
import sys
import socket
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from skill_runner import (
    PreCheckResult,
    PreCheckRunner,
    get_pre_check_runner,
    run_pre_checks,
    check_ffmpeg,
    SkillRunner,
    SkillResult,
)


class TestPreCheckResult:
    """Test PreCheckResult dataclass."""

    def test_basic_result(self):
        result = PreCheckResult(
            check_name="test_check",
            passed=True,
            message="All good"
        )
        assert result.passed is True
        assert result.check_name == "test_check"

    def test_result_with_details(self):
        result = PreCheckResult(
            check_name="ffmpeg_available",
            passed=True,
            message="ffmpeg 6.0 available",
            details={"version": "6.0", "path": "/usr/bin/ffmpeg"}
        )
        assert result.details["version"] == "6.0"

    def test_to_dict(self):
        result = PreCheckResult(
            check_name="test",
            passed=False,
            message="Failed",
            details={"error": "not found"}
        )
        d = result.to_dict()
        assert d["check_name"] == "test"
        assert d["passed"] is False
        assert d["details"]["error"] == "not found"


class TestPreCheckRunnerFFmpeg:
    """Test ffmpeg pre-check."""

    @patch('shutil.which')
    def test_ffmpeg_not_found(self, mock_which):
        mock_which.return_value = None
        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("ffmpeg_available")

        assert result.passed is False
        assert "not found" in result.message.lower()

    @patch('subprocess.run')
    @patch('shutil.which')
    def test_ffmpeg_found(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(
            stdout="ffmpeg version 6.0 Copyright (c) 2000-2023",
            returncode=0
        )

        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("ffmpeg_available")

        assert result.passed is True
        assert "6.0" in result.message
        assert result.details["version"] == "6.0"

    @patch('subprocess.run')
    @patch('shutil.which')
    def test_ffmpeg_version_parse_fallback(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(
            stdout="some unusual format",
            returncode=0
        )

        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("ffmpeg_available")

        assert result.passed is True
        assert result.details["version_line"] == "some unusual format"

    @patch('subprocess.run')
    @patch('shutil.which')
    def test_ffmpeg_timeout(self, mock_which, mock_run):
        import subprocess
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 5)

        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("ffmpeg_available")

        assert result.passed is False
        assert "timed out" in result.message.lower()


class TestPreCheckRunnerNetwork:
    """Test network connectivity check."""

    @patch('socket.socket')
    def test_network_available(self, mock_socket_class):
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 0
        mock_socket_class.return_value = mock_socket

        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("network_available")

        assert result.passed is True
        assert "connectivity confirmed" in result.message.lower()

    @patch('socket.socket')
    def test_network_unavailable(self, mock_socket_class):
        mock_socket = MagicMock()
        mock_socket.connect_ex.return_value = 1  # Connection refused
        mock_socket_class.return_value = mock_socket

        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("network_available")

        assert result.passed is False
        assert "no network" in result.message.lower()

    @patch('socket.socket')
    def test_network_check_exception(self, mock_socket_class):
        mock_socket_class.side_effect = socket.error("Network error")

        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("network_available")

        assert result.passed is False


class TestPreCheckRunnerDependency:
    """Test Python dependency checks."""

    def test_installed_package(self):
        # pytest should always be installed when running tests
        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("dependency_installed:pytest")

        assert result.passed is True
        assert "installed" in result.message.lower()

    def test_missing_package(self):
        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("dependency_installed:nonexistent_package_xyz")

        assert result.passed is False
        assert "not installed" in result.message.lower()
        assert "pip install" in result.message.lower()

    def test_package_with_hyphen(self):
        # Test that package name normalization works
        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("dependency_installed:pytest")  # Known installed

        assert result.passed is True


class TestPreCheckRunnerGitRepo:
    """Test git repository check."""

    @patch('subprocess.run')
    @patch('shutil.which')
    @patch('pathlib.Path.is_dir')
    def test_git_repo_via_git_dir(self, mock_is_dir, mock_which, mock_run):
        mock_is_dir.return_value = True  # .git directory exists

        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("git_repo")

        assert result.passed is True
        assert "repository detected" in result.message.lower()

    @patch('subprocess.run')
    @patch('shutil.which')
    @patch('pathlib.Path.is_dir')
    def test_not_git_repo(self, mock_is_dir, mock_which, mock_run):
        mock_is_dir.return_value = False
        mock_which.return_value = "/usr/bin/git"
        mock_run.return_value = MagicMock(returncode=128)  # Not a git repo

        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("git_repo")

        assert result.passed is False
        assert "not a git repository" in result.message.lower()


class TestPreCheckRunnerMCPPencil:
    """Test MCP Pencil check."""

    def test_mcp_pencil_always_passes(self):
        # In skill context, MCP Pencil is assumed available
        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("mcp_pencil_available")

        assert result.passed is True
        assert "assumed available" in result.message.lower()


class TestPreCheckRunnerUnknown:
    """Test unknown check handling."""

    def test_unknown_check(self):
        runner = PreCheckRunner(cache_enabled=False)
        result = runner.run_check("unknown_check_type")

        assert result.passed is False
        assert "unknown pre-check" in result.message.lower()


class TestPreCheckRunnerCaching:
    """Test caching behavior."""

    @patch('shutil.which')
    def test_cache_hit(self, mock_which):
        mock_which.return_value = None

        runner = PreCheckRunner(cache_enabled=True)
        runner.clear_cache()

        # First call
        result1 = runner.run_check("ffmpeg_available")
        # Second call should hit cache
        result2 = runner.run_check("ffmpeg_available")

        assert mock_which.call_count == 1  # Only called once
        assert result1.passed == result2.passed

    def test_cache_disabled(self):
        runner = PreCheckRunner(cache_enabled=False)

        with patch('shutil.which', return_value=None) as mock_which:
            runner.run_check("ffmpeg_available")
            runner.run_check("ffmpeg_available")

            assert mock_which.call_count == 2  # Called each time

    def test_clear_cache(self):
        runner = PreCheckRunner(cache_enabled=True)
        runner.clear_cache()  # Start with clean cache

        with patch('skill_runner.shutil.which', return_value=None) as mock_which:
            runner.run_check("ffmpeg_available")
            runner.clear_cache()
            runner.run_check("ffmpeg_available")

            assert mock_which.call_count == 2  # Called again after clear

    def test_run_multiple_checks(self):
        runner = PreCheckRunner(cache_enabled=False)
        results = runner.run_checks([
            "mcp_pencil_available",  # Always passes
            "dependency_installed:pytest",  # Should pass
        ])

        assert len(results) == 2
        assert all(r.passed for r in results)


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_run_pre_checks(self):
        all_passed, results = run_pre_checks(["mcp_pencil_available"])
        assert all_passed is True
        assert len(results) == 1

    def test_run_pre_checks_with_failure(self):
        all_passed, results = run_pre_checks([
            "mcp_pencil_available",  # Passes
            "dependency_installed:definitely_not_a_real_package"  # Fails
        ])
        assert all_passed is False
        assert len(results) == 2

    @patch('shutil.which')
    def test_check_ffmpeg_not_found(self, mock_which):
        mock_which.return_value = None
        # Clear the global runner's cache
        get_pre_check_runner().clear_cache()

        available, version, error = check_ffmpeg()

        assert available is False
        assert version == ""
        assert error is not None

    @patch('subprocess.run')
    @patch('shutil.which')
    def test_check_ffmpeg_found(self, mock_which, mock_run):
        mock_which.return_value = "/usr/bin/ffmpeg"
        mock_run.return_value = MagicMock(
            stdout="ffmpeg version 6.0 Copyright",
            returncode=0
        )
        get_pre_check_runner().clear_cache()

        available, version, error = check_ffmpeg()

        assert available is True
        assert version == "6.0"
        assert error is None


class TestSkillRunnerWithPreChecks:
    """Test SkillRunner.run_with_pre_checks method."""

    def test_pre_checks_pass(self):
        def dummy_skill(**kwargs):
            return SkillResult(
                success=True,
                summary="Skill completed",
                run_id="test",
                timestamp="2026-02-15T00:00:00Z"
            )

        runner = SkillRunner()
        result = runner.run_with_pre_checks(
            dummy_skill,
            args={},
            pre_checks=["mcp_pencil_available"]  # Always passes
        )

        assert result.success is True

    def test_pre_checks_fail(self):
        def dummy_skill(**kwargs):
            return SkillResult(
                success=True,
                summary="Should not reach here",
                run_id="test",
                timestamp="2026-02-15T00:00:00Z"
            )

        runner = SkillRunner()
        result = runner.run_with_pre_checks(
            dummy_skill,
            args={},
            pre_checks=["dependency_installed:nonexistent_package_abc"]
        )

        assert result.success is False
        assert "pre-checks failed" in result.summary.lower()

    def test_pre_checks_fail_fast(self):
        runner = SkillRunner()

        with patch.object(PreCheckRunner, 'run_check') as mock_check:
            mock_check.side_effect = [
                PreCheckResult("check1", False, "Failed"),
                PreCheckResult("check2", True, "Passed"),
            ]

            result = runner.run_with_pre_checks(
                lambda **k: SkillResult(True, "", "id", "ts"),
                args={},
                pre_checks=["check1", "check2"],
                fail_fast=True
            )

            assert result.success is False
            # With fail_fast=True, should stop at first failure
            assert mock_check.call_count == 1

    def test_pre_checks_no_fail_fast(self):
        runner = SkillRunner()

        with patch.object(PreCheckRunner, 'run_check') as mock_check:
            mock_check.side_effect = [
                PreCheckResult("check1", False, "Failed"),
                PreCheckResult("check2", True, "Passed"),
            ]

            result = runner.run_with_pre_checks(
                lambda **k: SkillResult(True, "", "id", "ts"),
                args={},
                pre_checks=["check1", "check2"],
                fail_fast=False
            )

            assert result.success is False
            # Without fail_fast, should run all checks
            assert mock_check.call_count == 2

    def test_pre_checks_with_progress_callback(self):
        updates = []

        def callback(update):
            updates.append(update)

        runner = SkillRunner()
        result = runner.run_with_pre_checks(
            lambda **k: SkillResult(True, "Done", "id", "ts"),
            args={},
            pre_checks=["dependency_installed:nonexistent_xyz"],
            progress_callback=callback
        )

        assert result.success is False
        # Should have received error progress update
        assert any(u.event.value == "error" for u in updates)


class TestGlobalPreCheckRunner:
    """Test global pre-check runner instance."""

    def test_get_pre_check_runner(self):
        runner1 = get_pre_check_runner()
        runner2 = get_pre_check_runner()

        assert runner1 is runner2  # Same instance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
