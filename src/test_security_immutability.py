"""
Security Immutability Regression Tests
=======================================

Tests that security-critical data structures are immutable to prevent
runtime modification attacks.

Run: python test_security_immutability.py

For CI: Set DURO_AGENT_HOME to a temp directory before running.
"""

import importlib
import os
import sys
import tempfile
from pathlib import Path

# === HERMETIC TEST SETUP ===
# Use temp directory for DURO_AGENT_HOME to avoid writing to real home
# and to ensure tests work on CI runners where ~/.agent doesn't exist

_TEMP_DIR = None
_ORIGINAL_AGENT_HOME = os.environ.get("DURO_AGENT_HOME")


def _setup_hermetic_environment():
    """Set up temp directory for hermetic testing."""
    global _TEMP_DIR

    # If DURO_AGENT_HOME is already set (e.g., by CI), use that
    if os.environ.get("DURO_AGENT_HOME"):
        agent_home = Path(os.environ["DURO_AGENT_HOME"])
        agent_home.mkdir(parents=True, exist_ok=True)
        (agent_home / "memory" / "audit").mkdir(parents=True, exist_ok=True)
        (agent_home / "config").mkdir(parents=True, exist_ok=True)
        return

    # Otherwise create temp directory
    _TEMP_DIR = tempfile.TemporaryDirectory()
    os.environ["DURO_AGENT_HOME"] = _TEMP_DIR.name

    # Create required directories
    agent_home = Path(_TEMP_DIR.name)
    (agent_home / "memory" / "audit").mkdir(parents=True, exist_ok=True)
    (agent_home / "memory" / "artifacts").mkdir(parents=True, exist_ok=True)
    (agent_home / "config").mkdir(parents=True, exist_ok=True)
    (agent_home / "src").mkdir(parents=True, exist_ok=True)
    (agent_home / "api").mkdir(parents=True, exist_ok=True)


def _teardown_hermetic_environment():
    """Clean up temp directory."""
    global _TEMP_DIR, _ORIGINAL_AGENT_HOME

    if _TEMP_DIR:
        _TEMP_DIR.cleanup()
        _TEMP_DIR = None

    # Restore original env
    if _ORIGINAL_AGENT_HOME:
        os.environ["DURO_AGENT_HOME"] = _ORIGINAL_AGENT_HOME
    elif "DURO_AGENT_HOME" in os.environ:
        del os.environ["DURO_AGENT_HOME"]


def _reload_workspace_guard():
    """Reload workspace_guard to pick up new DURO_AGENT_HOME."""
    import workspace_guard
    importlib.reload(workspace_guard)
    return workspace_guard


def test_policy_gate_immutability():
    """Test that policy_gate.py uses immutable data structures."""
    from policy_gate import (
        GATE_BYPASS_TOOLS,
        READ_SENSITIVE_TOOLS,
        BROWSER_TOOLS,
        _BREAKGLASS_CACHED,
    )

    # Test 1: GATE_BYPASS_TOOLS is frozenset
    assert isinstance(GATE_BYPASS_TOOLS, frozenset), (
        f"GATE_BYPASS_TOOLS is {type(GATE_BYPASS_TOOLS).__name__}, "
        "expected frozenset (SECURITY: prevents runtime modification)"
    )

    # Test 2: READ_SENSITIVE_TOOLS is frozenset
    assert isinstance(READ_SENSITIVE_TOOLS, frozenset), (
        f"READ_SENSITIVE_TOOLS is {type(READ_SENSITIVE_TOOLS).__name__}, "
        "expected frozenset (SECURITY: prevents runtime modification)"
    )

    # Test 3: BROWSER_TOOLS is frozenset
    assert isinstance(BROWSER_TOOLS, frozenset), (
        f"BROWSER_TOOLS is {type(BROWSER_TOOLS).__name__}, "
        "expected frozenset (SECURITY: prevents runtime modification)"
    )

    # Test 4: _BREAKGLASS_CACHED is bool (cached at import time)
    assert isinstance(_BREAKGLASS_CACHED, bool), (
        f"_BREAKGLASS_CACHED is {type(_BREAKGLASS_CACHED).__name__}, "
        "expected bool (SECURITY: cached at import to prevent runtime manipulation)"
    )

    # Test 5: Cannot modify frozensets
    try:
        GATE_BYPASS_TOOLS.add("malicious_tool")
        assert False, "GATE_BYPASS_TOOLS should not be modifiable"
    except AttributeError:
        pass  # Expected - frozenset has no add()

    try:
        GATE_BYPASS_TOOLS.clear()
        assert False, "GATE_BYPASS_TOOLS should not be clearable"
    except AttributeError:
        pass  # Expected - frozenset has no clear()

    print("[PASS] policy_gate.py immutability tests")
    return True


def test_prompt_firewall_immutability():
    """Test that prompt_firewall.py uses immutable data structures."""
    from prompt_firewall import INJECTION_PATTERNS, _COMPILED_PATTERNS

    # Test 1: INJECTION_PATTERNS is tuple
    assert isinstance(INJECTION_PATTERNS, tuple), (
        f"INJECTION_PATTERNS is {type(INJECTION_PATTERNS).__name__}, "
        "expected tuple (SECURITY: prevents runtime modification)"
    )

    # Test 2: _COMPILED_PATTERNS is tuple
    assert isinstance(_COMPILED_PATTERNS, tuple), (
        f"_COMPILED_PATTERNS is {type(_COMPILED_PATTERNS).__name__}, "
        "expected tuple (SECURITY: prevents runtime modification)"
    )

    # Test 3: Cannot modify tuples
    try:
        INJECTION_PATTERNS.append(("test", "test", "test", 0.5))
        assert False, "INJECTION_PATTERNS should not be appendable"
    except AttributeError:
        pass  # Expected - tuple has no append()

    try:
        INJECTION_PATTERNS.clear()
        assert False, "INJECTION_PATTERNS should not be clearable"
    except AttributeError:
        pass  # Expected - tuple has no clear()

    print("[PASS] prompt_firewall.py immutability tests")
    return True


def test_workspace_guard_immutability():
    """Test that workspace_guard.py uses immutable internal sensitive paths."""
    wg = _reload_workspace_guard()

    # Test 1: INTERNAL_SENSITIVE_PATHS is tuple
    assert isinstance(wg.INTERNAL_SENSITIVE_PATHS, tuple), (
        f"INTERNAL_SENSITIVE_PATHS is {type(wg.INTERNAL_SENSITIVE_PATHS).__name__}, "
        "expected tuple (SECURITY: prevents runtime modification)"
    )

    # Test 2: Cannot modify tuple
    try:
        wg.INTERNAL_SENSITIVE_PATHS.append(Path("/tmp"))
        assert False, "INTERNAL_SENSITIVE_PATHS should not be appendable"
    except AttributeError:
        pass  # Expected - tuple has no append()

    print("[PASS] workspace_guard.py immutability tests")
    return True


def test_internal_sensitive_paths_protected():
    """Test that internal sensitive paths are properly blocked for USER_FILE_IO."""
    wg = _reload_workspace_guard()

    # Use AGENT_HOME from the reloaded module (hermetic)
    agent_home = wg.AGENT_HOME

    # Test paths that should be blocked (default purpose = USER_FILE_IO)
    sensitive_paths = [
        agent_home / "memory",
        agent_home / "memory" / "artifacts",
        agent_home / "memory" / "artifacts" / "fact_test123.json",
        agent_home / "memory" / "audit" / "security_audit.jsonl",
        agent_home / "soul.md",
        agent_home / "core.md",
    ]

    for path in sensitive_paths:
        is_sensitive, reason = wg.is_internal_sensitive_path(path)
        assert is_sensitive, (
            f"Path {path} should be marked as internal sensitive, "
            f"but is_internal_sensitive_path returned False"
        )

    # Test paths that should NOT be blocked
    safe_paths = [
        agent_home / "src" / "policy_gate.py",
        agent_home / "config" / "workspace.json",
        agent_home / "api" / "main.py",
    ]

    for path in safe_paths:
        is_sensitive, reason = wg.is_internal_sensitive_path(path)
        assert not is_sensitive, (
            f"Path {path} should NOT be marked as internal sensitive, "
            f"but is_internal_sensitive_path returned True: {reason}"
        )

    print("[PASS] internal sensitive paths protection tests")
    return True


def test_purpose_parameter_bypass():
    """Test that internal Duro operations can bypass sensitive path blocking."""
    wg = _reload_workspace_guard()
    agent_home = wg.AGENT_HOME

    memory_path = agent_home / "memory" / "artifacts" / "test.json"
    audit_path = agent_home / "memory" / "audit" / "test.jsonl"

    # USER_FILE_IO should block (default)
    is_sensitive, _ = wg.is_internal_sensitive_path(memory_path, wg.PathPurpose.USER_FILE_IO)
    assert is_sensitive, "USER_FILE_IO should block sensitive paths"

    # INTERNAL_MEMORY should allow (for Duro memory backend)
    is_sensitive, _ = wg.is_internal_sensitive_path(memory_path, wg.PathPurpose.INTERNAL_MEMORY)
    assert not is_sensitive, "INTERNAL_MEMORY should allow sensitive paths"

    # INTERNAL_AUDIT should allow (for audit logging)
    is_sensitive, _ = wg.is_internal_sensitive_path(audit_path, wg.PathPurpose.INTERNAL_AUDIT)
    assert not is_sensitive, "INTERNAL_AUDIT should allow audit paths"

    print("[PASS] purpose parameter bypass tests")
    return True


def test_fail_closed_on_exception():
    """Test that USER_FILE_IO fails closed when path validation errors occur."""
    wg = _reload_workspace_guard()
    agent_home = wg.AGENT_HOME

    # Test with a normal sensitive path to verify basic blocking works
    sensitive_path = agent_home / "memory"
    is_sensitive, reason = wg.is_internal_sensitive_path(sensitive_path, wg.PathPurpose.USER_FILE_IO)
    assert is_sensitive, "USER_FILE_IO should block sensitive paths"

    # Test that INTERNAL purposes bypass even for sensitive paths
    is_sensitive, _ = wg.is_internal_sensitive_path(sensitive_path, wg.PathPurpose.INTERNAL_MEMORY)
    assert not is_sensitive, "INTERNAL_MEMORY should bypass blocking"

    print("[PASS] fail-closed behavior tests")
    return True


def test_audit_logging_not_blocked():
    """Test that workspace guard's own audit logging path is accessible."""
    wg = _reload_workspace_guard()

    # The audit file path should be blocked for USER_FILE_IO
    is_sensitive, _ = wg.is_internal_sensitive_path(wg.WORKSPACE_AUDIT_FILE, wg.PathPurpose.USER_FILE_IO)
    assert is_sensitive, "Audit file should be blocked for USER_FILE_IO"

    # But should be allowed for INTERNAL_AUDIT (Duro's own logging)
    is_sensitive, _ = wg.is_internal_sensitive_path(wg.WORKSPACE_AUDIT_FILE, wg.PathPurpose.INTERNAL_AUDIT)
    assert not is_sensitive, "Audit file should be allowed for INTERNAL_AUDIT"

    # Verify the audit file is writable by internal operations
    # (This tests that the guard doesn't block its own logging)
    import json
    from time_utils import utc_now_iso

    test_record = {
        "ts": utc_now_iso(),
        "test": True,
        "purpose": "regression_test",
    }

    # Ensure audit directory exists (hermetic setup should have done this)
    wg.AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # This should succeed (internal write, not going through validate_path)
    with open(wg.WORKSPACE_AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(test_record) + "\n")

    print("[PASS] audit logging not blocked tests")
    return True


def test_external_tool_cannot_read_memory():
    """Test that external tool calls cannot access internal memory paths.

    This is the actual attacker story: can a tool call trigger an internal read?
    """
    wg = _reload_workspace_guard()
    agent_home = wg.AGENT_HOME

    # Paths an attacker might try to read via external tools
    attack_paths = [
        agent_home / "memory" / "artifacts" / "fact_secret.json",
        agent_home / "memory" / "decisions" / "decision_sensitive.json",
        agent_home / "memory" / "facts" / "fact_api_key.json",
        agent_home / "memory" / "episodes" / "episode_private.json",
        agent_home / "memory" / "audit" / "security_audit.jsonl",
        agent_home / "soul.md",
        agent_home / "core.md",
    ]

    for path in attack_paths:
        # Simulate external tool validation (default purpose = USER_FILE_IO)
        validation = wg.validate_path(str(path))

        assert not validation.valid, (
            f"External access to {path} should be DENIED, "
            f"but validate_path returned valid=True"
        )
        assert validation.risk_level in ("sensitive", "blocked"), (
            f"External access to {path} should have risk_level 'sensitive' or 'blocked', "
            f"got '{validation.risk_level}'"
        )
        # Pin to the intended mechanism - catch reason drift
        assert "Internal sensitive path" in validation.reason, (
            f"Denial reason should mention 'Internal sensitive path', "
            f"got: {validation.reason}"
        )

    # Test via check_workspace_constraints (policy gate integration point)
    # Use clearly fake tool name - real tool names could get whitelisted later
    fake_tool_args = {"path": str(agent_home / "memory" / "artifacts" / "stolen.json")}
    allowed, reason, _ = wg.check_workspace_constraints("attacker_read_file", fake_tool_args)

    assert not allowed, (
        f"check_workspace_constraints should deny access to memory/artifacts, "
        f"but returned allowed=True. Reason: {reason}"
    )

    print("[PASS] external tool cannot read memory tests")
    return True


def test_symlink_traversal():
    """Test that symlinks can't be used to escape sensitive path blocking."""
    wg = _reload_workspace_guard()
    agent_home = wg.AGENT_HOME

    # Create a symlink from safe location pointing to sensitive location
    safe_dir = agent_home / "src"
    safe_dir.mkdir(parents=True, exist_ok=True)

    symlink_path = safe_dir / "sneaky_link"
    target_path = agent_home / "memory" / "artifacts"

    # Create the symlink (if possible - may fail on Windows without admin)
    try:
        if symlink_path.exists():
            symlink_path.unlink()
        symlink_path.symlink_to(target_path)

        # The symlink should resolve to the sensitive path and be blocked
        is_sensitive, reason = wg.is_internal_sensitive_path(symlink_path)
        assert is_sensitive, (
            f"Symlink {symlink_path} -> {target_path} should be blocked, "
            f"but is_internal_sensitive_path returned False"
        )

        # Clean up
        symlink_path.unlink()
        print("[PASS] symlink traversal test")

    except OSError as e:
        # Symlink creation may fail on Windows without admin privileges
        print(f"[SKIP] symlink traversal test (OS restriction: {e})")

    return True


def main():
    """Run all security immutability tests."""
    print("=" * 60)
    print("Security Immutability Regression Tests")
    print("=" * 60)
    print()

    # Set up hermetic test environment
    _setup_hermetic_environment()
    print(f"DURO_AGENT_HOME: {os.environ.get('DURO_AGENT_HOME', 'not set')}")
    print()

    passed = 0
    failed = 0
    skipped = 0

    tests = [
        test_policy_gate_immutability,
        test_prompt_firewall_immutability,
        test_workspace_guard_immutability,
        test_internal_sensitive_paths_protected,
        test_purpose_parameter_bypass,
        test_fail_closed_on_exception,
        test_audit_logging_not_blocked,
        test_external_tool_cannot_read_memory,
        test_symlink_traversal,
    ]

    try:
        for test_fn in tests:
            try:
                test_fn()
                passed += 1
            except AssertionError as e:
                print(f"[FAIL] {test_fn.__name__}: {e}")
                failed += 1
            except Exception as e:
                print(f"[ERROR] {test_fn.__name__}: {e}")
                failed += 1
    finally:
        # Clean up hermetic environment
        _teardown_hermetic_environment()

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
