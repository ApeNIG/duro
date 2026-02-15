"""
Tests for test_generate skill.

Tests cover:
- Code analysis (AST extraction)
- Parameter parsing
- Test generation for functions
- Test generation for classes
- Framework support (pytest, unittest)
- Edge case generation
- Type check generation
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

from test_generate import (
    run,
    TestFramework,
    ParameterType,
    Parameter,
    FunctionInfo,
    ClassInfo,
    ModuleInfo,
    GeneratedTest,
    TestGenerationResult,
    CodeAnalyzer,
    TestGenerator,
    analyze_code,
    get_sample_values,
    get_edge_case_values,
    generate_tests,
    generate_tests_for_file,
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
        assert SKILL_META["name"] == "test_generate"

    def test_has_composes(self):
        assert "composes" in SKILL_META
        assert "verification/test_coverage_verifier.py" in SKILL_META["composes"]


class TestParameter:
    """Test Parameter dataclass."""

    def test_string_type(self):
        param = Parameter("name", "str")
        assert param.param_type == ParameterType.STRING

    def test_int_type(self):
        param = Parameter("count", "int")
        assert param.param_type == ParameterType.INTEGER

    def test_float_type(self):
        param = Parameter("value", "float")
        assert param.param_type == ParameterType.FLOAT

    def test_bool_type(self):
        param = Parameter("flag", "bool")
        assert param.param_type == ParameterType.BOOLEAN

    def test_list_type(self):
        param = Parameter("items", "List[str]")
        assert param.param_type == ParameterType.LIST

    def test_dict_type(self):
        param = Parameter("data", "Dict[str, int]")
        assert param.param_type == ParameterType.DICT

    def test_optional_type(self):
        param = Parameter("maybe", "Optional[str]")
        assert param.param_type == ParameterType.OPTIONAL

    def test_no_type_hint(self):
        param = Parameter("unknown")
        assert param.param_type == ParameterType.ANY

    def test_custom_type(self):
        param = Parameter("obj", "MyClass")
        assert param.param_type == ParameterType.CUSTOM


class TestSampleValues:
    """Test sample value generation."""

    def test_string_values(self):
        param = Parameter("name", "str")
        values = get_sample_values(param)
        assert len(values) > 0
        assert '"test_string"' in values

    def test_int_values(self):
        param = Parameter("count", "int")
        values = get_sample_values(param)
        assert "0" in values
        assert "1" in values
        assert "-1" in values

    def test_bool_values(self):
        param = Parameter("flag", "bool")
        values = get_sample_values(param)
        assert "True" in values
        assert "False" in values

    def test_list_values(self):
        param = Parameter("items", "list")
        values = get_sample_values(param)
        assert "[]" in values


class TestEdgeCaseValues:
    """Test edge case value generation."""

    def test_string_edge_cases(self):
        param = Parameter("name", "str")
        cases = get_edge_case_values(param)
        assert len(cases) > 0
        # Check for empty string case
        assert any('""' in case[0] for case in cases)

    def test_int_edge_cases(self):
        param = Parameter("count", "int")
        cases = get_edge_case_values(param)
        assert any("0" in case[0] for case in cases)
        assert any("-1" in case[0] for case in cases)

    def test_float_edge_cases(self):
        param = Parameter("value", "float")
        cases = get_edge_case_values(param)
        assert any("inf" in case[0].lower() for case in cases)


class TestCodeAnalyzer:
    """Test AST code analysis."""

    def test_analyze_simple_function(self):
        code = '''
def greet(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}"
'''
        info = analyze_code(code)
        assert len(info.functions) == 1
        func = info.functions[0]
        assert func.name == "greet"
        assert len(func.parameters) == 1
        assert func.parameters[0].name == "name"
        assert func.parameters[0].type_hint == "str"
        assert func.return_type == "str"

    def test_analyze_function_with_defaults(self):
        code = '''
def greet(name: str, formal: bool = False) -> str:
    return name
'''
        info = analyze_code(code)
        func = info.functions[0]
        assert len(func.parameters) == 2
        assert func.parameters[1].default == "False"
        assert func.parameters[1].is_optional is True

    def test_analyze_async_function(self):
        code = '''
async def fetch(url: str) -> str:
    return url
'''
        info = analyze_code(code)
        func = info.functions[0]
        assert func.is_async is True

    def test_analyze_class(self):
        code = '''
class Calculator:
    """A calculator."""

    def __init__(self, initial: int = 0):
        self.value = initial

    def add(self, x: int) -> int:
        return self.value + x
'''
        info = analyze_code(code)
        assert len(info.classes) == 1
        cls = info.classes[0]
        assert cls.name == "Calculator"
        assert cls.has_init is True
        assert len(cls.methods) == 2

    def test_analyze_staticmethod(self):
        code = '''
class Utils:
    @staticmethod
    def helper(x: int) -> int:
        return x * 2
'''
        info = analyze_code(code)
        method = info.classes[0].methods[0]
        assert method.is_staticmethod is True

    def test_analyze_classmethod(self):
        code = '''
class Factory:
    @classmethod
    def create(cls, name: str) -> "Factory":
        return cls()
'''
        info = analyze_code(code)
        method = info.classes[0].methods[0]
        assert method.is_classmethod is True

    def test_skip_private_functions(self):
        code = '''
def public():
    pass

def _private():
    pass
'''
        info = analyze_code(code)
        assert len(info.functions) == 1
        assert info.functions[0].name == "public"

    def test_keep_init(self):
        code = '''
class MyClass:
    def __init__(self):
        pass
'''
        info = analyze_code(code)
        assert len(info.classes[0].methods) == 1
        assert info.classes[0].methods[0].name == "__init__"

    def test_analyze_imports(self):
        code = '''
import os
from pathlib import Path
'''
        info = analyze_code(code)
        assert "os" in info.imports
        assert "pathlib.Path" in info.imports

    def test_analyze_module_docstring(self):
        code = '''"""This is the module docstring."""

def func():
    pass
'''
        info = analyze_code(code)
        assert info.module_docstring == "This is the module docstring."


class TestTestGenerator:
    """Test test code generation."""

    def test_generate_basic_function_test(self):
        code = '''
def add(a: int, b: int) -> int:
    return a + b
'''
        result = generate_tests(code, "mymodule")
        assert result.success is True
        assert "def test_add" in result.test_file_content
        assert "from mymodule import" in result.test_file_content

    def test_generate_class_tests(self):
        code = '''
class Calculator:
    def __init__(self, initial: int = 0):
        self.value = initial

    def add(self, x: int) -> int:
        return self.value + x
'''
        result = generate_tests(code, "calc")
        assert result.success is True
        assert "class TestCalculator" in result.test_file_content
        assert "def test_add" in result.test_file_content

    def test_generate_pytest_fixture(self):
        code = '''
class MyClass:
    def __init__(self, value: int):
        self.value = value

    def get(self) -> int:
        return self.value
'''
        result = generate_tests(code, "mymodule")
        assert result.success is True
        assert "@pytest.fixture" in result.test_file_content
        assert "def instance" in result.test_file_content

    def test_generate_unittest_style(self):
        code = '''
def greet(name: str) -> str:
    return name
'''
        result = generate_tests(code, "mymodule", framework=TestFramework.UNITTEST)
        assert result.success is True
        assert "import unittest" in result.test_file_content
        assert "self.assertIsNotNone" in result.test_file_content or "def test_greet" in result.test_file_content

    def test_generate_async_test(self):
        code = '''
async def fetch(url: str) -> str:
    return url
'''
        result = generate_tests(code, "mymodule")
        assert result.success is True
        assert "async def test_fetch" in result.test_file_content

    def test_generate_parameterized_tests(self):
        code = '''
def process(value: str) -> str:
    return value
'''
        result = generate_tests(code, "mymodule", config={"include_edge_cases": True})
        assert result.success is True
        assert "@pytest.mark.parametrize" in result.test_file_content

    def test_generate_type_check_tests(self):
        code = '''
def get_count() -> int:
    return 42
'''
        result = generate_tests(code, "mymodule", config={"include_type_checks": True})
        assert result.success is True
        assert "returns_correct_type" in result.test_file_content
        assert "isinstance" in result.test_file_content

    def test_no_testable_code(self):
        code = '''
# Just a comment
'''
        result = generate_tests(code, "empty")
        assert result.success is True
        assert "No testable functions" in result.warnings[0]


class TestTestGenerationResultDataclass:
    """Test TestGenerationResult dataclass."""

    def test_to_dict(self):
        from test_generate import TestGenerationResult as TGResult
        result = TGResult(
            success=True,
            test_file_content="test code",
            tests_generated=[
                GeneratedTest("test_foo", "code", "foo", "basic")
            ]
        )
        d = result.to_dict()
        assert d["success"] is True
        assert len(d["tests_generated"]) == 1


class TestGenerateTestsForFile:
    """Test file-based test generation."""

    def test_file_not_found(self):
        result = generate_tests_for_file("/nonexistent/file.py")
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_non_python_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not python")
            path = f.name

        result = generate_tests_for_file(path)
        assert result.success is False
        assert "python file" in result.error.lower()

        Path(path).unlink()

    def test_successful_file_generation(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
            f.write('''
def hello(name: str) -> str:
    return f"Hello, {name}"
''')
            source_path = f.name

        result = generate_tests_for_file(source_path)
        assert result.success is True
        assert "test_hello" in result.test_file_content

        Path(source_path).unlink()

    def test_write_output_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "module.py"
            source_path.write_text('''
def foo() -> int:
    return 42
''')
            output_path = Path(tmpdir) / "test_module.py"

            result = generate_tests_for_file(
                str(source_path),
                output_path=str(output_path)
            )

            assert result.success is True
            assert output_path.exists()
            content = output_path.read_text()
            assert "test_foo" in content


class TestRunFunction:
    """Test the main run() function."""

    def test_missing_source(self):
        result = run({}, {}, {})
        assert result["success"] is False
        assert "source_path or source_code" in result["error"].lower()

    def test_missing_module_name(self):
        result = run({"source_code": "def foo(): pass"}, {}, {})
        assert result["success"] is False
        assert "module_name" in result["error"].lower()

    def test_invalid_framework(self):
        result = run({
            "source_code": "def foo(): pass",
            "module_name": "test",
            "framework": "invalid"
        }, {}, {})
        assert result["success"] is False
        assert "invalid framework" in result["error"].lower()

    def test_successful_run_with_source_code(self):
        result = run({
            "source_code": '''
def add(a: int, b: int) -> int:
    return a + b
''',
            "module_name": "math_utils"
        }, {}, {})

        assert result["success"] is True
        assert "test_add" in result["test_file_content"]

    def test_run_with_source_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "module.py"
            source_path.write_text('''
def greet(name: str) -> str:
    return name
''')

            result = run({
                "source_path": str(source_path)
            }, {}, {})

            assert result["success"] is True
            assert "test_greet" in result["test_file_content"]

    def test_run_with_unittest(self):
        result = run({
            "source_code": "def foo(): pass",
            "module_name": "test",
            "framework": "unittest"
        }, {}, {})

        assert result["success"] is True
        assert "import unittest" in result["test_file_content"]

    def test_run_with_options(self):
        result = run({
            "source_code": '''
def process(value: str) -> str:
    return value
''',
            "module_name": "proc",
            "include_edge_cases": True,
            "include_type_checks": True,
            "include_docstrings": True
        }, {}, {})

        assert result["success"] is True
        assert '"""' in result["test_file_content"]  # Docstrings


class TestSyntaxError:
    """Test syntax error handling."""

    def test_invalid_syntax(self):
        result = generate_tests("def broken(:", "module")
        assert result.success is False
        assert "syntax error" in result.error.lower()


class TestProgressCallback:
    """Test progress callback."""

    def test_callback_called(self):
        updates = []

        def callback(update):
            updates.append(update)

        generate_tests(
            "def foo(): pass",
            "module",
            progress_callback=callback
        )

        assert len(updates) > 0
        assert all("step" in u for u in updates)


class TestComplexScenarios:
    """Test complex code scenarios."""

    def test_multiple_functions(self):
        code = '''
def add(a: int, b: int) -> int:
    return a + b

def subtract(a: int, b: int) -> int:
    return a - b

def multiply(a: int, b: int) -> int:
    return a * b
'''
        result = generate_tests(code, "math_ops")
        assert result.success is True
        assert "test_add" in result.test_file_content
        assert "test_subtract" in result.test_file_content
        assert "test_multiply" in result.test_file_content
        assert len(result.tests_generated) >= 3

    def test_class_with_multiple_methods(self):
        code = '''
class Service:
    def __init__(self, name: str):
        self.name = name

    def start(self) -> bool:
        return True

    def stop(self) -> bool:
        return True

    def status(self) -> str:
        return "running"
'''
        result = generate_tests(code, "service")
        assert result.success is True
        assert "TestService" in result.test_file_content
        assert "test_start" in result.test_file_content
        assert "test_stop" in result.test_file_content
        assert "test_status" in result.test_file_content

    def test_mixed_functions_and_classes(self):
        code = '''
def helper(x: int) -> int:
    return x * 2

class Worker:
    def work(self) -> str:
        return "done"
'''
        result = generate_tests(code, "mixed")
        assert result.success is True
        assert "test_helper" in result.test_file_content
        assert "TestWorker" in result.test_file_content

    def test_optional_parameters(self):
        code = '''
def greet(name: str, formal: bool = False, title: str = "") -> str:
    return name
'''
        result = generate_tests(code, "greet")
        assert result.success is True
        # Basic test should only use required params
        assert "test_greet" in result.test_file_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
