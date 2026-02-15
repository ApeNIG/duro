"""
Tests for code_refactor skill.

Tests cover:
- Rename operations (variable, function, class)
- Import operations (remove unused, sort)
- Code transformations (f-strings, dead code removal)
- Extract function
- Verification before/after
- Diff generation
- Error handling
- Run function
"""

import pytest
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Add skills to path
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "code"))

from code_refactor import (
    run,
    RefactorType,
    RefactorOperation,
    CodeLocation,
    RefactorChange,
    RefactorResult,
    VerificationResult,
    NameCollector,
    rename_in_code,
    remove_unused_imports,
    sort_imports,
    convert_to_fstring,
    extract_function,
    remove_dead_code,
    verify_code,
    generate_diff,
    refactor,
    refactor_file,
    SKILL_META,
    DEFAULT_CONFIG,
)


class TestSkillMetadata:
    """Test skill metadata is properly defined."""

    def test_has_required_fields(self):
        assert "name" in SKILL_META
        assert "description" in SKILL_META
        assert "tier" in SKILL_META
        assert "version" in SKILL_META

    def test_name_matches(self):
        assert SKILL_META["name"] == "code_refactor"

    def test_has_composes(self):
        assert "composes" in SKILL_META
        assert "verification/code_review_verifier.py" in SKILL_META["composes"]


class TestRenameInCode:
    """Test rename operations."""

    def test_rename_variable(self):
        code = '''
x = 10
y = x + 5
print(x)
'''
        result, changes = rename_in_code(code, "x", "value")
        assert "value = 10" in result
        assert "y = value + 5" in result
        assert "print(value)" in result
        assert len(changes) == 3

    def test_rename_function(self):
        code = '''
def foo():
    return 42

result = foo()
'''
        result, changes = rename_in_code(code, "foo", "get_value")
        assert "def get_value():" in result
        assert "result = get_value()" in result

    def test_rename_preserves_similar_names(self):
        code = '''
x = 1
x_value = 2
my_x = 3
'''
        result, changes = rename_in_code(code, "x", "y")
        assert "y = 1" in result
        assert "x_value = 2" in result  # Not renamed
        assert "my_x = 3" in result  # Not renamed

    def test_rename_with_scope(self):
        code = '''
x = 1

def foo():
    x = 2
    return x

y = x
'''
        result, changes = rename_in_code(code, "x", "local_x", scope="foo")
        assert "local_x = 2" in result
        assert "return local_x" in result
        # Outside scope should not be renamed
        assert "y = x" in result or "x = 1" in result

    def test_no_matches(self):
        code = "y = 10"
        result, changes = rename_in_code(code, "x", "z")
        assert result == code
        assert len(changes) == 0


class TestRemoveUnusedImports:
    """Test unused import removal."""

    def test_remove_unused(self):
        code = '''
import os
import sys
import json

print(os.getcwd())
'''
        result, changes = remove_unused_imports(code)
        assert "import os" in result
        assert "import sys" not in result
        assert "import json" not in result

    def test_keep_all_used(self):
        code = '''
import os
import sys

print(os.getcwd())
sys.exit()
'''
        result, changes = remove_unused_imports(code)
        assert "import os" in result
        assert "import sys" in result

    def test_no_imports(self):
        code = '''
x = 10
print(x)
'''
        result, changes = remove_unused_imports(code)
        assert result == code

    def test_syntax_error_handling(self):
        code = "def broken(:"
        result, changes = remove_unused_imports(code)
        assert result == code
        assert len(changes) == 0


class TestSortImports:
    """Test import sorting."""

    def test_sort_stdlib_first(self):
        code = '''
from pathlib import Path
import json
import os
import sys
'''
        result, changes = sort_imports(code)
        lines = [l.strip() for l in result.split('\n') if l.strip()]
        # All imports should be sorted
        assert "import json" in result
        assert "import os" in result

    def test_separate_groups(self):
        code = '''
import requests
import os
from . import local
'''
        result, changes = sort_imports(code)
        # Should have groups separated by blank lines
        assert result.count('\n\n') >= 1 or len(changes) == 0

    def test_no_imports(self):
        code = "x = 10"
        result, changes = sort_imports(code)
        assert result == code


class TestConvertToFstring:
    """Test f-string conversion."""

    def test_convert_format(self):
        code = '''
name = "World"
msg = "Hello, {}".format(name)
'''
        result, changes = convert_to_fstring(code)
        assert 'f"Hello, {name}"' in result

    def test_convert_positional(self):
        code = '''
msg = "Hello, {0} and {1}".format("Alice", "Bob")
'''
        result, changes = convert_to_fstring(code)
        # Should convert to f-string with variables
        assert 'f"' in result

    def test_no_format_calls(self):
        code = '''
msg = f"Already an f-string"
'''
        result, changes = convert_to_fstring(code)
        assert result == code


class TestExtractFunction:
    """Test function extraction."""

    def test_extract_lines(self):
        code = '''
def main():
    x = 10
    y = 20
    z = x + y
    print(z)
'''
        result, changes = extract_function(code, 4, 5, "calculate", ["x", "y"])
        assert "def calculate(x, y):" in result
        assert "calculate(x, y)" in result

    def test_invalid_range(self):
        code = "x = 10"
        result, changes = extract_function(code, 10, 20, "foo")
        assert result == code
        assert len(changes) == 0


class TestRemoveDeadCode:
    """Test dead code removal."""

    def test_remove_after_return(self):
        code = '''
def foo():
    return 42
    print("dead")
    x = 10
'''
        result, changes = remove_dead_code(code)
        assert "print" not in result
        assert "x = 10" not in result

    def test_remove_after_raise(self):
        code = '''
def bar():
    raise ValueError()
    cleanup()
'''
        result, changes = remove_dead_code(code)
        assert "cleanup" not in result

    def test_preserve_code_after_if(self):
        code = '''
def baz():
    if True:
        return 1
    return 2
'''
        result, changes = remove_dead_code(code)
        # Both returns should remain (different branches)
        assert "return 1" in result
        assert "return 2" in result

    def test_no_dead_code(self):
        code = '''
def foo():
    x = 10
    return x
'''
        result, changes = remove_dead_code(code)
        assert result == code


class TestVerifyCode:
    """Test code verification."""

    def test_valid_code(self):
        code = '''
def foo():
    return 42
'''
        result = verify_code(code)
        assert result.passed is True

    def test_syntax_error(self):
        code = "def broken(:"
        result = verify_code(code)
        assert result.passed is False
        assert any("Syntax error" in i for i in result.issues)

    def test_long_lines(self):
        code = f'x = "{" " * 200}"'
        result = verify_code(code)
        assert any("too long" in i.lower() for i in result.issues)

    def test_todo_comment(self):
        code = "# TODO: fix this"
        result = verify_code(code)
        assert any("TODO" in i for i in result.issues)


class TestGenerateDiff:
    """Test diff generation."""

    def test_simple_diff(self):
        original = "x = 1\ny = 2"
        modified = "x = 1\nz = 2"
        diff = generate_diff(original, modified)
        assert "-y = 2" in diff
        assert "+z = 2" in diff

    def test_no_changes(self):
        code = "x = 1"
        diff = generate_diff(code, code)
        assert diff == ""


class TestRefactorFunction:
    """Test main refactor function."""

    def test_rename_operation(self):
        code = "x = 10\ny = x + 5"
        op = RefactorOperation(
            type=RefactorType.RENAME_VARIABLE,
            target="x",
            new_value="value"
        )
        result = refactor(code, op)
        assert result.success is True
        assert "value = 10" in result.refactored_code

    def test_no_changes_warning(self):
        code = "y = 10"
        op = RefactorOperation(
            type=RefactorType.RENAME_VARIABLE,
            target="x",
            new_value="z"
        )
        result = refactor(code, op)
        assert result.success is True
        assert "No changes" in str(result.warnings)

    def test_unsupported_operation(self):
        code = "x = 10"
        op = RefactorOperation(
            type=RefactorType.ADD_TYPE_HINTS,  # Not implemented
            target=""
        )
        result = refactor(code, op)
        assert result.success is False
        assert "Unsupported" in result.error

    def test_verification(self):
        code = "x = 10\nprint(x)"
        op = RefactorOperation(
            type=RefactorType.RENAME_VARIABLE,
            target="x",
            new_value="value"
        )
        result = refactor(code, op, config={"verify_before": True, "verify_after": True})
        assert result.verification_before is not None
        assert result.verification_after is not None

    def test_progress_callback(self):
        updates = []

        def callback(update):
            updates.append(update)

        code = "x = 10"
        op = RefactorOperation(
            type=RefactorType.RENAME_VARIABLE,
            target="x",
            new_value="y"
        )
        refactor(code, op, progress_callback=callback)
        assert len(updates) > 0


class TestRefactorResult:
    """Test RefactorResult dataclass."""

    def test_to_dict(self):
        result = RefactorResult(
            success=True,
            original_code="x = 1",
            refactored_code="y = 1",
            changes=[
                RefactorChange(
                    location=CodeLocation(1, 0),
                    original="x",
                    replacement="y",
                    description="Renamed"
                )
            ]
        )
        d = result.to_dict()
        assert d["success"] is True
        assert len(d["changes"]) == 1


class TestRefactorFile:
    """Test file-based refactoring."""

    def test_file_not_found(self):
        op = RefactorOperation(
            type=RefactorType.RENAME_VARIABLE,
            target="x",
            new_value="y"
        )
        result = refactor_file("/nonexistent/file.py", op)
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_refactor_and_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test.py"
            source.write_text("x = 10\nprint(x)")

            op = RefactorOperation(
                type=RefactorType.RENAME_VARIABLE,
                target="x",
                new_value="value"
            )
            result = refactor_file(str(source), op)

            assert result.success is True
            assert "value = 10" in source.read_text()

    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test.py"
            original = "x = 10"
            source.write_text(original)

            op = RefactorOperation(
                type=RefactorType.RENAME_VARIABLE,
                target="x",
                new_value="y"
            )
            result = refactor_file(
                str(source),
                op,
                config={"dry_run": True}
            )

            assert result.success is True
            assert source.read_text() == original  # Not modified

    def test_output_to_different_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "original.py"
            output = Path(tmpdir) / "refactored.py"
            source.write_text("x = 10")

            op = RefactorOperation(
                type=RefactorType.RENAME_VARIABLE,
                target="x",
                new_value="y"
            )
            result = refactor_file(
                str(source),
                op,
                output_path=str(output)
            )

            assert result.success is True
            assert output.exists()
            assert "y = 10" in output.read_text()


class TestRunFunction:
    """Test the main run() function."""

    def test_missing_source(self):
        result = run({}, {}, {})
        assert result["success"] is False
        assert "source_path or source_code" in result["error"].lower()

    def test_missing_operation(self):
        result = run({"source_code": "x = 1"}, {}, {})
        assert result["success"] is False
        assert "operation" in result["error"].lower()

    def test_invalid_operation(self):
        result = run({
            "source_code": "x = 1",
            "operation": "invalid_op"
        }, {}, {})
        assert result["success"] is False
        assert "invalid operation" in result["error"].lower()

    def test_successful_run(self):
        result = run({
            "source_code": "x = 10\nprint(x)",
            "operation": "rename_variable",
            "target": "x",
            "new_value": "value"
        }, {}, {})

        assert result["success"] is True
        assert "value = 10" in result["refactored_code"]

    def test_run_with_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "test.py"
            source.write_text("x = 10")

            result = run({
                "source_path": str(source),
                "operation": "rename_variable",
                "target": "x",
                "new_value": "y"
            }, {}, {})

            assert result["success"] is True

    def test_run_remove_unused_imports(self):
        result = run({
            "source_code": '''
import os
import sys
print(os.getcwd())
''',
            "operation": "remove_unused_imports"
        }, {}, {})

        assert result["success"] is True
        assert "import sys" not in result["refactored_code"]

    def test_run_convert_to_fstring(self):
        result = run({
            "source_code": '''
msg = "Hello, {}".format("World")
''',
            "operation": "convert_to_fstring"
        }, {}, {})

        assert result["success"] is True
        assert 'f"' in result["refactored_code"]

    def test_run_with_dry_run(self):
        result = run({
            "source_code": "x = 10",
            "operation": "rename_variable",
            "target": "x",
            "new_value": "y",
            "dry_run": True
        }, {}, {})

        assert result["success"] is True
        assert "y = 10" in result["refactored_code"]


class TestComplexScenarios:
    """Test complex refactoring scenarios."""

    def test_multiple_operations_sequence(self):
        code = '''
import os
import sys
import json

def foo():
    x = 10
    message = "Value: {}".format(x)
    return message
    print("dead")
'''
        # Remove unused imports
        op1 = RefactorOperation(type=RefactorType.REMOVE_UNUSED_IMPORTS, target="")
        result1 = refactor(code, op1)

        # Convert to f-string
        op2 = RefactorOperation(type=RefactorType.CONVERT_TO_FSTRING, target="")
        result2 = refactor(result1.refactored_code, op2)

        # Remove dead code
        op3 = RefactorOperation(type=RefactorType.REMOVE_DEAD_CODE, target="")
        result3 = refactor(result2.refactored_code, op3)

        final = result3.refactored_code
        assert "import json" not in final
        assert "import sys" not in final
        assert 'f"Value:' in final or 'f"' in final
        assert "print" not in final.split("return")[-1]

    def test_rename_in_class(self):
        code = '''
class Calculator:
    def __init__(self):
        self.total = 0

    def add(self, value):
        self.total += value

    def get_total(self):
        return self.total
'''
        op = RefactorOperation(
            type=RefactorType.RENAME_VARIABLE,
            target="total",
            new_value="sum"
        )
        result = refactor(code, op)
        assert result.success is True
        assert "self.sum" in result.refactored_code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
