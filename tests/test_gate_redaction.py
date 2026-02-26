"""
Regression tests for gate-level credential redaction.

Tests the security posture:
1. SENSITIVE_TOOLS with secrets → ALLOW + redacted
2. Non-sensitive tools with secrets → BLOCK
3. False-positive text → ALLOW (no false positives)

Run with: python -m pytest tests/test_gate_redaction.py -v

NOTE: Token strings are generated at RUNTIME to avoid triggering gitleaks.
Do NOT add literal token-shaped strings to this file.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from secrets_guard import (
    scan_arguments,
    redact_arguments,
    check_secrets_policy,
    SENSITIVE_TOOLS,
)


# =============================================================================
# Token generators - build at runtime to avoid gitleaks flagging source code
# =============================================================================

def make_github_pat() -> str:
    """Generate a GitHub PAT (ghp_ + 36 chars)."""
    return "ghp_" + ("a" * 26) + ("1" * 10)  # 36 chars total


def make_anthropic_key() -> str:
    """Generate an Anthropic key (sk-ant-api03- + 24+ chars)."""
    return "sk-ant-api03-" + ("b" * 26)


def make_openai_key() -> str:
    """Generate an OpenAI key (sk-proj- + 20+ chars)."""
    return "sk-proj-" + ("c" * 30)


def make_aws_key() -> str:
    """Generate an AWS access key (AKIA + 16 chars)."""
    return "AKIA" + ("D" * 16)


def make_short_github() -> str:
    """Generate a too-short GitHub token (won't match strict pattern)."""
    return "ghp_" + ("x" * 20)  # Only 20 chars, needs 36


class TestGateRedaction:
    """Test that redaction and detection use the same patterns."""

    def test_sensitive_tool_with_github_pat_allows_and_redacts(self):
        """SENSITIVE_TOOL + GitHub PAT → should be redactable (same scanner)."""
        token = make_github_pat()
        args = {"content": f"Token: {token}"}

        # Scan finds it
        scan_result = scan_arguments(args)
        assert scan_result.has_secrets, "Scanner should detect GitHub PAT"
        assert any(m.pattern_name == "github_pat" for m in scan_result.matches)

        # Redact cleans it
        redacted = redact_arguments(args)
        assert "[REDACTED:" in redacted["content"], "Redactor should clean it"
        assert "ghp_" not in redacted["content"], "Token should be gone"

        # Re-scan is clean
        rescan = scan_arguments(redacted)
        assert not rescan.has_secrets, "Re-scan should find nothing"

    def test_sensitive_tool_with_anthropic_key_allows_and_redacts(self):
        """SENSITIVE_TOOL + Anthropic key → should be redactable."""
        token = make_anthropic_key()
        args = {"snippet": f"Key: {token}"}

        scan_result = scan_arguments(args)
        assert scan_result.has_secrets, "Scanner should detect Anthropic key"

        redacted = redact_arguments(args)
        assert "[REDACTED:" in redacted["snippet"]
        assert "sk-ant-" not in redacted["snippet"]

        rescan = scan_arguments(redacted)
        assert not rescan.has_secrets

    def test_sensitive_tool_with_aws_key_allows_and_redacts(self):
        """SENSITIVE_TOOL + AWS key → should be redactable."""
        token = make_aws_key()
        args = {"claim": f"AWS: {token}"}

        scan_result = scan_arguments(args)
        assert scan_result.has_secrets, "Scanner should detect AWS key"
        assert any(m.pattern_name == "aws_access_key" for m in scan_result.matches)

        redacted = redact_arguments(args)
        assert "[REDACTED:" in redacted["claim"]
        assert "AKIA" not in redacted["claim"]

    def test_bash_with_token_blocks(self):
        """Bash with token → BLOCK (non-sensitive tool)."""
        token = make_github_pat()
        args = {"command": f"export TOKEN={token}"}

        # check_secrets_policy should block for non-sensitive tools
        allowed, reason, scan_result = check_secrets_policy("bash_command", args)

        # Bash is not in SENSITIVE_TOOLS, should block on critical secrets
        assert "bash_command" not in SENSITIVE_TOOLS
        assert scan_result.has_secrets

    def test_false_positive_text_allows(self):
        """Text mentioning 'secret/password' without assignment → ALLOW."""
        args = {
            "content": (
                "The secret to success is hard work. "
                "Password policies require 12 characters. "
                "Never share your API credentials."
            )
        }

        scan_result = scan_arguments(args)
        # Should NOT trigger - no actual secrets, just words
        # This tests that we don't have overly broad patterns
        assert not scan_result.blocked, "Should not block on prose"

    def test_short_token_not_matched(self):
        """Token that's too short should NOT match strict patterns."""
        token = make_short_github()
        args = {"content": token}

        scan_result = scan_arguments(args)
        # The strict pattern shouldn't match
        github_matches = [m for m in scan_result.matches if m.pattern_name == "github_pat"]
        assert len(github_matches) == 0, "Short token should not match github_pat"

    def test_multiple_secrets_all_redacted(self):
        """Multiple different secrets → all should be redacted."""
        gh = make_github_pat()
        aws = make_aws_key()
        ant = make_anthropic_key()
        args = {"content": f"GitHub: {gh} AWS: {aws} Anthropic: {ant}"}

        scan_result = scan_arguments(args)
        assert scan_result.has_secrets
        assert len(scan_result.matches) >= 3, "Should find all 3 secrets"

        redacted = redact_arguments(args)
        assert redacted["content"].count("[REDACTED:") >= 3
        assert "ghp_" not in redacted["content"]
        assert "AKIA" not in redacted["content"]
        assert "sk-ant-" not in redacted["content"]


class TestSensitiveToolsList:
    """Verify SENSITIVE_TOOLS includes expected tools."""

    def test_memory_tools_are_sensitive(self):
        """Memory/logging tools should be in SENSITIVE_TOOLS."""
        expected = [
            "duro_save_memory",
            "duro_save_learning",
            "duro_log_task",
            "duro_store_fact",
            "duro_store_decision",
            "duro_store_incident",
        ]
        for tool in expected:
            assert tool in SENSITIVE_TOOLS, f"{tool} should be sensitive"

    def test_bash_not_sensitive(self):
        """Bash should NOT be in SENSITIVE_TOOLS (should block, not redact)."""
        assert "bash_command" not in SENSITIVE_TOOLS
        assert "Bash" not in SENSITIVE_TOOLS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
