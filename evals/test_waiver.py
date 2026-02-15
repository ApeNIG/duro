#!/usr/bin/env python3
"""Quick test for waiver protocol."""

import os
import sys
import json
import subprocess
from pathlib import Path

HOME = Path.home()
HOOK_PATH = HOME / '.claude' / 'plugins' / 'cache' / 'claude-plugins-official' / 'hookify' / '96276205880a' / 'hooks' / 'pretooluse.py'

def run_hook(tool_name: str, tool_input: dict, waiver: str = None) -> dict:
    """Run hook and return parsed output."""
    input_data = {"tool_name": tool_name, "tool_input": tool_input}

    env = os.environ.copy()
    if waiver:
        env["DURO_WAIVE"] = waiver

    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=10,
        env=env
    )

    return json.loads(result.stdout) if result.stdout.strip() else {}

def test_waiver():
    """Test waiver protocol."""
    print("=" * 60)
    print("WAIVER PROTOCOL TESTS")
    print("=" * 60)

    # Test 1: Blocked without waiver
    print("\n[Test 1] Force push WITHOUT waiver")
    result = run_hook("Bash", {"command": "git push --force origin main"})
    decision = result.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
    print(f"  Decision: {decision}")
    assert decision == "deny", f"Expected deny, got {decision}"
    print("  PASS: Blocked as expected")

    # Test 2: Allowed WITH valid waiver
    print("\n[Test 2] Force push WITH valid waiver")
    result = run_hook(
        "Bash",
        {"command": "git push --force origin main"},
        waiver="destructive_bash_commands:Force pushing rebased feature branch for testing"
    )
    decision = result.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
    has_waived_msg = "WAIVED" in result.get("systemMessage", "")
    print(f"  Decision: {decision}")
    print(f"  Has WAIVED message: {has_waived_msg}")
    assert decision != "deny", f"Expected allow (waived), got deny"
    assert has_waived_msg, "Expected WAIVED message"
    print("  PASS: Waived as expected")

    # Test 3: Blocked with WRONG rule_id waiver
    print("\n[Test 3] Force push with WRONG rule waiver")
    result = run_hook(
        "Bash",
        {"command": "git push --force origin main"},
        waiver="wrong_rule:Some reason here for testing purposes"
    )
    decision = result.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
    print(f"  Decision: {decision}")
    assert decision == "deny", f"Expected deny (wrong rule), got {decision}"
    print("  PASS: Blocked (waiver mismatch)")

    # Test 4: Blocked with SHORT reason
    print("\n[Test 4] Force push with TOO SHORT reason")
    result = run_hook(
        "Bash",
        {"command": "git push --force origin main"},
        waiver="destructive_bash_commands:short"
    )
    decision = result.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
    print(f"  Decision: {decision}")
    assert decision == "deny", f"Expected deny (short reason), got {decision}"
    print("  PASS: Blocked (reason too short)")

    # Test 5: Blocked for UNWAIVABLE rule (secrets_in_git)
    print("\n[Test 5] Secrets in git (UNWAIVABLE)")
    result = run_hook(
        "Bash",
        {"command": "git add .env"},
        waiver="secrets_in_git:I really need to commit this env file for testing"
    )
    decision = result.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
    print(f"  Decision: {decision}")
    assert decision == "deny", f"Expected deny (unwaivable), got {decision}"
    print("  PASS: Blocked (unwaivable rule)")

    print("\n" + "=" * 60)
    print("ALL WAIVER TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    test_waiver()
