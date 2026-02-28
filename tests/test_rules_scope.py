"""
Regression tests for rules scope enforcement.

These tests verify that:
1. Rules with `tools` field only apply to specified tools
2. Rules without `tools` field (legacy/global) apply to all tools
3. Trigger keywords in arguments of non-scoped tools don't cause false positives

This test file was created after a real bug where:
- rule_safety_002 had keywords ["delete", "force", "remove"]
- It was missing the `tools` field
- duro_validate_decision with notes containing "delete" was incorrectly blocked
- Fix: Added `tools: ["Bash", "duro_delete_artifact", "duro_batch_delete"]`

Incident: rules_guard false positive blocking duro_validate_decision
Date: 2026-02-27
"""

import sys
import pytest
import tempfile
import json
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rules_guard import check_rules_for_tool, check_rules_layer, load_rules_index


class TestRulesToolScope:
    """Verify that rules with `tools` field only match specified tools."""

    def test_scoped_rule_does_not_match_unscoped_tool(self):
        """
        Regression test: A rule scoped to Bash should NOT block duro_validate_decision,
        even if the arguments contain trigger keywords like 'delete'.

        This was the original bug that caused false positives.
        """
        # Load current rules to check rule_safety_002 is properly scoped
        index = load_rules_index(force_reload=True)

        # Find rule_safety_002 (No Destructive Commands)
        safety_002 = None
        for rule in index.get("active_rules", []):
            if rule.get("id") == "rule_safety_002":
                safety_002 = rule
                break

        # Rule should have tools field
        assert safety_002 is not None, "rule_safety_002 should exist"
        assert "tools" in safety_002, "rule_safety_002 should have a 'tools' field"
        assert isinstance(safety_002["tools"], list), "tools should be a list"

        # duro_validate_decision should NOT be in the scoped tools
        assert "duro_validate_decision" not in safety_002["tools"], \
            "duro_validate_decision should NOT be in rule_safety_002's tools scope"

    def test_validate_decision_with_trigger_keywords_not_blocked(self):
        """
        Calling duro_validate_decision with notes containing 'delete', 'remove', 'drop'
        should NOT be blocked by rule_safety_002.
        """
        # Simulate calling duro_validate_decision with trigger keywords
        result = check_rules_for_tool(
            tool_name="duro_validate_decision",
            arguments={
                "notes": "This note contains delete and remove and drop keywords",
                "status": "validated",
                "result": "success"
            },
            enforce_hard=True
        )

        # Should be allowed - no false positive
        assert result.allowed, f"Should be allowed but got: {result.message}"

        # Check that rule_safety_002 was NOT matched
        matched_rule_ids = [r["rule"]["id"] for r in result.matched_rules]
        assert "rule_safety_002" not in matched_rule_ids, \
            "rule_safety_002 should NOT match duro_validate_decision"

    def test_scoped_rule_still_blocks_intended_tools(self):
        """
        rule_safety_002 should still block Bash commands with destructive keywords.
        Scoping should not break the intended enforcement.
        """
        result = check_rules_for_tool(
            tool_name="Bash",
            arguments={"command": "rm -rf some_directory"},
            enforce_hard=True
        )

        # Should be blocked (or at least matched)
        matched_rule_ids = [r["rule"]["id"] for r in result.matched_rules]

        # The rule should match Bash with destructive command
        # Note: actual blocking depends on enforcement patterns too
        assert "rule_safety_002" in matched_rule_ids, \
            "rule_safety_002 SHOULD match Bash with 'rm -rf'"

    def test_scoped_rule_blocks_delete_artifact(self):
        """
        rule_safety_002 should match duro_delete_artifact when arguments contain
        trigger keywords. Note: underscores in tool names prevent word boundary
        matching, so 'duro_delete_artifact' won't match 'delete' directly.
        The rule triggers when args contain the keyword.
        """
        result = check_rules_for_tool(
            tool_name="duro_delete_artifact",
            arguments={
                "artifact_id": "some_id",
                "reason": "Need to delete this artifact"  # Contains 'delete' keyword
            },
            enforce_hard=True
        )

        # Should be matched (tool is in scope and keyword "delete" is in args)
        matched_rule_ids = [r["rule"]["id"] for r in result.matched_rules]
        assert "rule_safety_002" in matched_rule_ids, \
            "rule_safety_002 SHOULD match duro_delete_artifact with 'delete' in args"


class TestAllActiveRulesHaveToolsScope:
    """
    Verify all active PreToolUse rules have proper tools scoping.
    This prevents future global-scope-by-accident bugs.
    """

    def test_all_pretooluse_rules_have_tools_field(self):
        """
        Every rule with enforcement=PreToolUse should have a `tools` field
        to prevent the global scope false positive bug.
        """
        index = load_rules_index(force_reload=True)

        violations = []

        for rule in index.get("active_rules", []):
            if rule.get("enforcement") == "PreToolUse":
                if "tools" not in rule:
                    violations.append({
                        "id": rule.get("id"),
                        "name": rule.get("name"),
                        "keywords": rule.get("trigger_keywords", [])
                    })

        assert len(violations) == 0, \
            f"PreToolUse rules without `tools` field (global scope): {json.dumps(violations, indent=2)}"

    def test_no_dangerously_broad_keywords_without_scope(self):
        """
        Keywords like 'validation', 'update', 'change' are dangerously broad.
        Any rule with these keywords MUST have a tools scope or be enforcement=future.
        """
        dangerous_keywords = {
            "validation", "update", "change", "edit", "modify",
            "token", "force", "delete", "remove"
        }

        index = load_rules_index(force_reload=True)

        violations = []

        for rule in index.get("active_rules", []):
            # Only check actively enforced rules
            if rule.get("enforcement") not in ["PreToolUse", "skill_runner"]:
                continue

            keywords = set(k.lower() for k in rule.get("trigger_keywords", []))
            dangerous_found = keywords.intersection(dangerous_keywords)

            if dangerous_found and "tools" not in rule:
                violations.append({
                    "id": rule.get("id"),
                    "name": rule.get("name"),
                    "dangerous_keywords": list(dangerous_found)
                })

        assert len(violations) == 0, \
            f"Rules with dangerous keywords but no tools scope: {json.dumps(violations, indent=2)}"


class TestCheckRulesLayerAPI:
    """Test the main entry point API."""

    def test_check_rules_layer_returns_tuple(self):
        """check_rules_layer should return (allowed, message, matched_rules)."""
        allowed, message, matched_rules = check_rules_layer(
            "some_tool",
            {"arg": "value"},
            enforce=True
        )

        assert isinstance(allowed, bool)
        assert isinstance(message, str)
        assert isinstance(matched_rules, list)

    def test_check_rules_layer_non_destructive_tool_allowed(self):
        """Non-destructive tools with trigger keywords should be allowed."""
        allowed, message, matched_rules = check_rules_layer(
            "duro_store_fact",
            {"claim": "I need to delete this old data and remove the cache"},
            enforce=True
        )

        # duro_store_fact should be allowed even with 'delete' and 'remove' in args
        assert allowed, f"duro_store_fact should be allowed but got: {message}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
