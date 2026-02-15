"""
Tests for skill_runner.py

Run with: python -m pytest tests/test_skill_runner.py -v
"""

import pytest
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from skill_runner import (
    SkillRunner, SkillResult, Finding, CheckResult,
    RuleSpec, RuleEngine, PathValidator, SuppressionManager,
    Severity, validate_args
)


class TestPathValidator:
    """Test path security validation."""

    def test_blocks_path_traversal(self):
        validator = PathValidator()
        assert not validator.is_safe("../../../etc/passwd")
        assert not validator.is_safe("C:/Users/sibag/../../../etc/passwd")

    def test_allows_safe_paths(self):
        validator = PathValidator()
        assert validator.is_safe("C:/Users/sibag/Desktop/BUILD/msj/src/app.tsx")
        assert validator.is_safe("C:/Users/sibag/.agent/skills/test.py")

    def test_blocks_outside_roots(self):
        validator = PathValidator()
        assert not validator.is_safe("/etc/passwd")
        assert not validator.is_safe("C:/Windows/System32/config")


class TestValidateArgs:
    """Test argument schema validation."""

    def test_detects_missing_required(self):
        schema = {"required": ["file_path", "rules"]}
        args = {"file_path": "test.tsx"}
        errors = validate_args(args, schema)
        assert "Missing required argument: rules" in errors

    def test_checks_types(self):
        schema = {
            "types": {"count": "int", "name": "str"}
        }
        args = {"count": "not an int", "name": 123}
        errors = validate_args(args, schema)
        assert len(errors) == 2

    def test_applies_defaults(self):
        schema = {
            "defaults": {"max_findings": 100}
        }
        args = {}
        validate_args(args, schema)
        assert args["max_findings"] == 100

    def test_passes_valid_args(self):
        schema = {
            "required": ["file_path"],
            "types": {"file_path": "str", "limit": "int"},
            "defaults": {"limit": 50}
        }
        args = {"file_path": "test.tsx"}
        errors = validate_args(args, schema)
        assert len(errors) == 0
        assert args["limit"] == 50


class TestRuleEngine:
    """Test rule execution."""

    def test_finds_pattern_matches(self):
        from tests.mock_mcp import MockMCP

        mcp = MockMCP()
        mcp.add_fixture("test.tsx", '''
const x: any = 5;
const y: string = "hello";
const z: any = {};
''')

        runner = SkillRunner(
            project_root=Path.cwd(),
            allowed_roots=[Path.cwd()]
        )
        engine = RuleEngine(runner)

        rule = RuleSpec(
            id="no_any",
            name="No any type",
            pattern=r":\s*any\b",
            message="Avoid using 'any' type",
            severity=Severity.WARN
        )

        # Run rule against fixture
        content = mcp.fixtures["test.tsx"]
        result = engine.run_rule(rule, Path("test.tsx"), content)

        assert len(result.findings) == 2  # Line 2 and 4
        assert result.findings[0].line == 2
        assert result.findings[1].line == 4

    def test_respects_timeout(self):
        runner = SkillRunner(project_root=Path.cwd(), allowed_roots=[Path.cwd()])
        engine = RuleEngine(runner)

        # Catastrophic backtracking pattern
        rule = RuleSpec(
            id="slow_rule",
            name="Slow rule",
            pattern=r"(a+)+$",  # This will be slow on "aaaaaaaaaaaaaaaaaaaaaaaaaaaaab"
            message="Slow",
            timeout_ms=100  # Very short timeout
        )

        content = "a" * 30 + "b"  # Triggers backtracking
        result = engine.run_rule(rule, Path("test.txt"), content)

        # Should complete (either timeout or finish) without hanging
        assert result is not None


class TestSkillResult:
    """Test result formatting."""

    def test_to_devkit_json(self):
        result = SkillResult(
            success=True,
            summary="Check passed",
            run_id="run_abc123",
            timestamp="2026-02-15T06:00:00Z",
            repo="msj",
            checks=[
                CheckResult(name="lint", success=True, duration_ms=150)
            ],
            findings=[]
        )

        json_str = result.to_devkit_json()
        assert "run_abc123" in json_str
        assert '"success": true' in json_str


class TestFinding:
    """Test finding creation and serialization."""

    def test_to_dict(self):
        finding = Finding(
            id="any_001",
            type="quality_violation",
            severity=Severity.ERROR,
            confidence=0.9,
            file="src/app.tsx",
            line=10,
            message="Found 'any' type",
            rule_id="no_any"
        )

        d = finding.to_dict()
        assert d["severity"] == "error"
        assert d["confidence"] == 0.9
        assert d["rule_id"] == "no_any"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
