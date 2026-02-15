"""
Tests for code_review_verifier skill.

Tests cover:
- Complexity detection
- Nesting depth detection
- Security issue detection
- Naming convention checks
- File length checks
- Edge cases (empty files, syntax errors)
"""

import pytest
import sys
from pathlib import Path

# Add skills to path
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "verification"))

from code_review_verifier import (
    run,
    analyze_python_file,
    Finding,
    Severity,
    Category,
    DEFAULT_CONFIG,
    SKILL_META,
)


class TestSkillMetadata:
    """Test skill metadata is properly defined."""

    def test_has_required_fields(self):
        assert "name" in SKILL_META
        assert "description" in SKILL_META
        assert "tier" in SKILL_META
        assert "version" in SKILL_META

    def test_name_matches(self):
        assert SKILL_META["name"] == "code_review_verifier"


class TestComplexityDetection:
    """Test cyclomatic complexity detection."""

    def test_simple_function_passes(self):
        code = '''
def simple():
    return 42
'''
        findings = analyze_python_file("test.py", code, DEFAULT_CONFIG)
        complexity_findings = [f for f in findings if f.rule_id == "high_complexity"]
        assert len(complexity_findings) == 0

    def test_complex_function_detected(self):
        code = '''
def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                return 1
            else:
                return 2
        elif y < 0:
            return 3
        else:
            return 4
    elif x < 0:
        for i in range(10):
            if i % 2 == 0:
                continue
        return 5
    else:
        try:
            return 6
        except:
            return 7
'''
        config = {**DEFAULT_CONFIG, "max_function_complexity": 5}
        findings = analyze_python_file("test.py", code, config)
        complexity_findings = [f for f in findings if f.rule_id == "high_complexity"]
        assert len(complexity_findings) == 1
        assert complexity_findings[0].severity == Severity.WARN


class TestNestingDepth:
    """Test nesting depth detection."""

    def test_shallow_nesting_passes(self):
        code = '''
def shallow():
    if True:
        if True:
            return 1
'''
        findings = analyze_python_file("test.py", code, DEFAULT_CONFIG)
        nesting_findings = [f for f in findings if f.rule_id == "deep_nesting"]
        assert len(nesting_findings) == 0

    def test_deep_nesting_detected(self):
        code = '''
def deep():
    if True:
        if True:
            if True:
                if True:
                    if True:
                        return 1
'''
        config = {**DEFAULT_CONFIG, "max_nesting_depth": 4}
        findings = analyze_python_file("test.py", code, config)
        nesting_findings = [f for f in findings if f.rule_id == "deep_nesting"]
        assert len(nesting_findings) == 1


class TestSecurityDetection:
    """Test security issue detection."""

    def test_eval_detected(self):
        code = '''
def dangerous():
    user_input = "print('hello')"
    eval(user_input)
'''
        config = {**DEFAULT_CONFIG, "banned_functions": ["eval"]}
        findings = analyze_python_file("test.py", code, config)
        security_findings = [f for f in findings if f.category == Category.SECURITY]
        assert len(security_findings) >= 1
        assert any("eval" in f.message for f in security_findings)

    def test_exec_detected(self):
        code = '''
def also_dangerous():
    exec("import os")
'''
        config = {**DEFAULT_CONFIG, "banned_functions": ["exec"]}
        findings = analyze_python_file("test.py", code, config)
        security_findings = [f for f in findings if f.category == Category.SECURITY]
        assert len(security_findings) >= 1

    def test_shell_injection_detected(self):
        code = '''
import subprocess
def run_command(cmd):
    subprocess.call(cmd, shell=True)
'''
        findings = analyze_python_file("test.py", code, DEFAULT_CONFIG)
        security_findings = [f for f in findings if "shell" in f.rule_id]
        assert len(security_findings) >= 1


class TestNamingConventions:
    """Test naming convention checks."""

    def test_snake_case_function_passes(self):
        code = '''
def my_function():
    pass

def another_function_name():
    pass
'''
        config = {**DEFAULT_CONFIG, "naming_convention": "snake_case"}
        findings = analyze_python_file("test.py", code, config)
        naming_findings = [f for f in findings if f.rule_id == "naming_convention"]
        # Filter out docstring warnings
        naming_findings = [f for f in naming_findings if "naming" in f.message.lower()]
        assert len(naming_findings) == 0

    def test_camel_case_function_detected(self):
        code = '''
def myFunction():
    pass
'''
        config = {**DEFAULT_CONFIG, "naming_convention": "snake_case"}
        findings = analyze_python_file("test.py", code, config)
        naming_findings = [f for f in findings if f.rule_id == "naming_convention"]
        assert len(naming_findings) >= 1

    def test_class_requires_pascal_case(self):
        code = '''
class my_class:
    pass
'''
        findings = analyze_python_file("test.py", code, DEFAULT_CONFIG)
        naming_findings = [f for f in findings if "Class" in f.message]
        assert len(naming_findings) >= 1


class TestFunctionLength:
    """Test function length detection."""

    def test_short_function_passes(self):
        code = '''
def short():
    x = 1
    y = 2
    return x + y
'''
        findings = analyze_python_file("test.py", code, DEFAULT_CONFIG)
        length_findings = [f for f in findings if f.rule_id == "function_too_long"]
        assert len(length_findings) == 0

    def test_long_function_detected(self):
        # Generate a long function
        lines = ["def long_function():"]
        for i in range(60):
            lines.append(f"    x{i} = {i}")
        lines.append("    return x0")
        code = "\n".join(lines)

        config = {**DEFAULT_CONFIG, "max_function_lines": 50}
        findings = analyze_python_file("test.py", code, config)
        length_findings = [f for f in findings if f.rule_id == "function_too_long"]
        assert len(length_findings) >= 1


class TestTooManyArguments:
    """Test argument count detection."""

    def test_few_arguments_passes(self):
        code = '''
def few_args(a, b, c):
    return a + b + c
'''
        findings = analyze_python_file("test.py", code, DEFAULT_CONFIG)
        arg_findings = [f for f in findings if f.rule_id == "too_many_arguments"]
        assert len(arg_findings) == 0

    def test_many_arguments_detected(self):
        code = '''
def many_args(a, b, c, d, e, f, g, h):
    return a + b + c + d + e + f + g + h
'''
        config = {**DEFAULT_CONFIG, "max_arguments": 5}
        findings = analyze_python_file("test.py", code, config)
        arg_findings = [f for f in findings if f.rule_id == "too_many_arguments"]
        assert len(arg_findings) >= 1


class TestSyntaxErrors:
    """Test handling of syntax errors."""

    def test_syntax_error_reported(self):
        code = '''
def broken(
    return 1
'''
        findings = analyze_python_file("test.py", code, DEFAULT_CONFIG)
        assert len(findings) >= 1
        assert findings[0].rule_id == "syntax_error"
        assert findings[0].severity == Severity.CRITICAL


class TestRunFunction:
    """Test the main run() function."""

    def test_run_returns_expected_structure(self):
        mock_tools = {
            "read_file": lambda p: "def foo(): pass",
            "glob_files": lambda pattern: [],
        }

        result = run(
            {"files": ["test.py"]},
            mock_tools,
            {}
        )

        assert "success" in result
        assert "passed" in result
        assert "findings" in result
        assert "summary" in result
        assert "files_reviewed" in result
        assert "duration_ms" in result

    def test_run_with_glob_pattern(self):
        mock_tools = {
            "read_file": lambda p: "def foo(): pass",
            "glob_files": lambda pattern: ["a.py", "b.py"],
        }

        result = run(
            {"files": ["*.py"]},
            mock_tools,
            {}
        )

        assert result["success"] is True
        assert result["files_reviewed"] == 2

    def test_run_fail_on_error(self):
        mock_tools = {
            "read_file": lambda p: "eval('bad')",
            "glob_files": lambda pattern: [],
        }

        result = run(
            {"files": ["test.py"], "fail_on": "error"},
            mock_tools,
            {}
        )

        # Should fail due to eval being banned
        assert result["success"] is True
        assert result["passed"] is False


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_file(self):
        findings = analyze_python_file("test.py", "", DEFAULT_CONFIG)
        # Should not crash, may have no findings
        assert isinstance(findings, list)

    def test_file_with_only_comments(self):
        code = '''
# This is a comment
# Another comment
'''
        findings = analyze_python_file("test.py", code, DEFAULT_CONFIG)
        assert isinstance(findings, list)

    def test_unicode_content(self):
        code = '''
def greet():
    """Say hello in Japanese."""
    return "こんにちは"
'''
        findings = analyze_python_file("test.py", code, DEFAULT_CONFIG)
        assert isinstance(findings, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
