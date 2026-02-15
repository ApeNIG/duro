"""
Test Generate Skill - Generate tests from function signatures.

Generates test files from:
- Function signatures with type hints
- Class definitions with methods
- Module-level functions

Features:
- AST-based analysis for accurate extraction
- Multiple test frameworks (pytest, unittest)
- Parameterized test generation
- Mock/fixture suggestions
- Integration with test_coverage_verifier

Phase 3.3.2 of Duro Capability Expansion.
"""

import ast
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Tuple, Union
import textwrap


# === Metadata ===

SKILL_META = {
    "name": "test_generate",
    "description": "Generate tests from function signatures",
    "tier": "tested",
    "phase": "3.3",
    "version": "1.0.0",
    "keywords": [
        "test", "generate", "pytest", "unittest", "coverage",
        "mock", "fixture", "parameterized", "tdd"
    ],
    "dependencies": [],
    "side_effects": ["writes_file"],
    "composes": ["verification/test_coverage_verifier.py"],
}

DEFAULT_CONFIG = {
    "framework": "pytest",
    "include_docstrings": True,
    "include_edge_cases": True,
    "include_type_checks": True,
    "max_params_for_parameterized": 3,
}


# === Enums and Data Classes ===

class TestFramework(Enum):
    """Supported test frameworks."""
    PYTEST = "pytest"
    UNITTEST = "unittest"


class ParameterType(Enum):
    """Types of parameters for test generation."""
    STRING = "str"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    LIST = "list"
    DICT = "dict"
    NONE = "None"
    ANY = "Any"
    OPTIONAL = "Optional"
    CUSTOM = "custom"


@dataclass
class Parameter:
    """Function parameter information."""
    name: str
    type_hint: Optional[str] = None
    default: Optional[str] = None
    is_optional: bool = False

    @property
    def param_type(self) -> ParameterType:
        """Get the parameter type enum."""
        if not self.type_hint:
            return ParameterType.ANY

        hint = self.type_hint.lower()
        if hint == "str":
            return ParameterType.STRING
        elif hint == "int":
            return ParameterType.INTEGER
        elif hint == "float":
            return ParameterType.FLOAT
        elif hint == "bool":
            return ParameterType.BOOLEAN
        elif hint.startswith("list"):
            return ParameterType.LIST
        elif hint.startswith("dict"):
            return ParameterType.DICT
        elif hint == "none":
            return ParameterType.NONE
        elif hint.startswith("optional"):
            return ParameterType.OPTIONAL
        return ParameterType.CUSTOM


@dataclass
class FunctionInfo:
    """Extracted function information."""
    name: str
    parameters: List[Parameter]
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    is_method: bool = False
    is_async: bool = False
    is_classmethod: bool = False
    is_staticmethod: bool = False
    is_property: bool = False
    class_name: Optional[str] = None
    decorators: List[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """Extracted class information."""
    name: str
    methods: List[FunctionInfo]
    docstring: Optional[str] = None
    bases: List[str] = field(default_factory=list)
    has_init: bool = False


@dataclass
class ModuleInfo:
    """Extracted module information."""
    functions: List[FunctionInfo]
    classes: List[ClassInfo]
    imports: List[str]
    module_docstring: Optional[str] = None


@dataclass
class GeneratedTest:
    """A generated test case."""
    name: str
    code: str
    target_function: str
    test_type: str  # "basic", "edge_case", "type_check", "parameterized"


@dataclass
class TestGenerationResult:
    """Result of test generation."""
    success: bool
    test_file_content: str = ""
    tests_generated: List[GeneratedTest] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: str = ""
    coverage_hints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["tests_generated"] = [asdict(t) for t in self.tests_generated]
        return result


# === AST Extraction ===

class CodeAnalyzer(ast.NodeVisitor):
    """Extract function and class information from Python code."""

    def __init__(self):
        self.module_info = ModuleInfo(
            functions=[],
            classes=[],
            imports=[],
            module_docstring=None
        )
        self._current_class: Optional[str] = None

    def visit_Module(self, node: ast.Module) -> None:
        """Visit module node."""
        # Get module docstring
        if (node.body and isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Constant) and
            isinstance(node.body[0].value.value, str)):
            self.module_info.module_docstring = node.body[0].value.value

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statement."""
        for alias in node.names:
            self.module_info.imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from import statement."""
        module = node.module or ""
        for alias in node.names:
            self.module_info.imports.append(f"{module}.{alias.name}")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        self._process_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self._process_function(node, is_async=True)

    def _process_function(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], is_async: bool) -> None:
        """Process a function definition."""
        # Skip private/magic methods except __init__
        if node.name.startswith("_") and node.name != "__init__":
            return

        # Get decorators
        decorators = []
        is_classmethod = False
        is_staticmethod = False
        is_property = False

        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorators.append(decorator.id)
                if decorator.id == "classmethod":
                    is_classmethod = True
                elif decorator.id == "staticmethod":
                    is_staticmethod = True
                elif decorator.id == "property":
                    is_property = True

        # Get parameters
        parameters = []
        args = node.args

        # Regular arguments
        defaults_offset = len(args.args) - len(args.defaults)
        for i, arg in enumerate(args.args):
            # Skip self/cls
            if arg.arg in ("self", "cls"):
                continue

            param = Parameter(
                name=arg.arg,
                type_hint=self._get_annotation(arg.annotation),
                default=None,
                is_optional=False
            )

            # Check for default value
            default_idx = i - defaults_offset
            if default_idx >= 0 and default_idx < len(args.defaults):
                param.default = self._get_default_value(args.defaults[default_idx])
                param.is_optional = True

            parameters.append(param)

        # Get return type
        return_type = self._get_annotation(node.returns)

        # Get docstring
        docstring = ast.get_docstring(node)

        func_info = FunctionInfo(
            name=node.name,
            parameters=parameters,
            return_type=return_type,
            docstring=docstring,
            is_method=self._current_class is not None,
            is_async=is_async,
            is_classmethod=is_classmethod,
            is_staticmethod=is_staticmethod,
            is_property=is_property,
            class_name=self._current_class,
            decorators=decorators
        )

        if self._current_class:
            # Add to current class's methods
            for cls in self.module_info.classes:
                if cls.name == self._current_class:
                    cls.methods.append(func_info)
                    if node.name == "__init__":
                        cls.has_init = True
                    break
        else:
            self.module_info.functions.append(func_info)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        # Skip private classes
        if node.name.startswith("_"):
            return

        # Get bases
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(f"{self._get_attribute_name(base)}")

        # Get docstring
        docstring = ast.get_docstring(node)

        class_info = ClassInfo(
            name=node.name,
            methods=[],
            docstring=docstring,
            bases=bases,
            has_init=False
        )
        self.module_info.classes.append(class_info)

        # Visit methods
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = None

    def _get_annotation(self, node: Optional[ast.expr]) -> Optional[str]:
        """Get string representation of type annotation."""
        if node is None:
            return None

        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Subscript):
            base = self._get_annotation(node.value)
            slice_val = self._get_annotation(node.slice)
            return f"{base}[{slice_val}]"
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_name(node)
        elif isinstance(node, ast.Tuple):
            elements = [self._get_annotation(e) for e in node.elts]
            return ", ".join(e for e in elements if e)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            # Union type with |
            left = self._get_annotation(node.left)
            right = self._get_annotation(node.right)
            return f"{left} | {right}"

        return "Any"

    def _get_attribute_name(self, node: ast.Attribute) -> str:
        """Get full attribute name."""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))

    def _get_default_value(self, node: ast.expr) -> str:
        """Get string representation of default value."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return repr(node.value)
            return str(node.value)
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.List):
            return "[]"
        elif isinstance(node, ast.Dict):
            return "{}"
        elif isinstance(node, ast.Tuple):
            return "()"
        return "..."


def analyze_code(source_code: str) -> ModuleInfo:
    """Analyze Python source code and extract information."""
    tree = ast.parse(source_code)
    analyzer = CodeAnalyzer()
    analyzer.visit(tree)
    return analyzer.module_info


# === Test Value Generation ===

def get_sample_values(param: Parameter) -> List[str]:
    """Get sample test values for a parameter."""
    ptype = param.param_type

    if ptype == ParameterType.STRING:
        return ['"test_string"', '""', '"a" * 1000']
    elif ptype == ParameterType.INTEGER:
        return ["0", "1", "-1", "999"]
    elif ptype == ParameterType.FLOAT:
        return ["0.0", "1.5", "-1.5", "float('inf')"]
    elif ptype == ParameterType.BOOLEAN:
        return ["True", "False"]
    elif ptype == ParameterType.LIST:
        return ["[]", "[1, 2, 3]", '["a", "b"]']
    elif ptype == ParameterType.DICT:
        return ["{}", '{"key": "value"}']
    elif ptype == ParameterType.NONE:
        return ["None"]
    elif ptype == ParameterType.OPTIONAL:
        return ["None", '"value"']
    else:
        return ['"test_value"']


def get_edge_case_values(param: Parameter) -> List[Tuple[str, str]]:
    """Get edge case values with descriptions."""
    ptype = param.param_type
    cases = []

    if ptype == ParameterType.STRING:
        cases = [
            ('""', "empty string"),
            ('"a" * 10000', "very long string"),
            ('" "', "whitespace only"),
            ('"\\n\\t"', "special characters"),
        ]
    elif ptype == ParameterType.INTEGER:
        cases = [
            ("0", "zero"),
            ("-1", "negative"),
            ("2**31", "large number"),
        ]
    elif ptype == ParameterType.FLOAT:
        cases = [
            ("0.0", "zero"),
            ("float('inf')", "infinity"),
            ("float('nan')", "NaN"),
        ]
    elif ptype == ParameterType.LIST:
        cases = [
            ("[]", "empty list"),
            ("[None]", "list with None"),
        ]
    elif ptype == ParameterType.DICT:
        cases = [
            ("{}", "empty dict"),
        ]

    return cases


# === Test Generation ===

class TestGenerator:
    """Generate test code from function information."""

    def __init__(self, framework: TestFramework, config: Dict[str, Any]):
        self.framework = framework
        self.config = config
        self.tests: List[GeneratedTest] = []

    def generate_tests(self, module_info: ModuleInfo, module_name: str) -> str:
        """Generate complete test file."""
        self.tests = []
        lines = []

        # Generate header
        lines.extend(self._generate_header(module_name))

        # Generate imports
        lines.extend(self._generate_imports(module_info, module_name))
        lines.append("")

        # Generate function tests
        for func in module_info.functions:
            if func.name.startswith("_"):
                continue
            lines.extend(self._generate_function_tests(func, module_name))
            lines.append("")

        # Generate class tests
        for cls in module_info.classes:
            lines.extend(self._generate_class_tests(cls, module_name))
            lines.append("")

        return "\n".join(lines)

    def _generate_header(self, module_name: str) -> List[str]:
        """Generate test file header."""
        return [
            f'"""Tests for {module_name}."""',
            "",
        ]

    def _generate_imports(self, module_info: ModuleInfo, module_name: str) -> List[str]:
        """Generate import statements."""
        lines = []

        if self.framework == TestFramework.PYTEST:
            lines.append("import pytest")
        else:
            lines.append("import unittest")

        lines.append("")

        # Import from target module
        imports = []
        for func in module_info.functions:
            if not func.name.startswith("_"):
                imports.append(func.name)
        for cls in module_info.classes:
            imports.append(cls.name)

        if imports:
            lines.append(f"from {module_name} import (")
            for imp in imports:
                lines.append(f"    {imp},")
            lines.append(")")

        return lines

    def _generate_function_tests(self, func: FunctionInfo, module_name: str) -> List[str]:
        """Generate tests for a function."""
        lines = []

        if self.framework == TestFramework.PYTEST:
            lines.extend(self._generate_pytest_function_tests(func))
        else:
            lines.extend(self._generate_unittest_function_tests(func))

        return lines

    def _generate_pytest_function_tests(self, func: FunctionInfo) -> List[str]:
        """Generate pytest-style tests for a function."""
        lines = []
        test_name_base = f"test_{func.name}"

        # Basic test
        basic_test = self._generate_basic_test(func, test_name_base)
        lines.extend(basic_test)
        self.tests.append(GeneratedTest(
            name=f"{test_name_base}",
            code="\n".join(basic_test),
            target_function=func.name,
            test_type="basic"
        ))
        lines.append("")

        # Edge case tests
        if self.config.get("include_edge_cases") and func.parameters:
            edge_tests = self._generate_edge_case_tests(func, test_name_base)
            lines.extend(edge_tests)
            lines.append("")

        # Type check tests
        if self.config.get("include_type_checks") and func.return_type:
            type_test = self._generate_type_check_test(func, test_name_base)
            lines.extend(type_test)
            lines.append("")

        return lines

    def _generate_basic_test(self, func: FunctionInfo, test_name_base: str) -> List[str]:
        """Generate a basic test for a function."""
        lines = []

        # Generate test function
        async_prefix = "async " if func.is_async else ""
        lines.append(f"{async_prefix}def {test_name_base}():")

        # Add docstring
        if self.config.get("include_docstrings"):
            lines.append(f'    """Test {func.name} basic functionality."""')

        # Generate call with sample arguments
        args = []
        for param in func.parameters:
            if param.default is not None:
                continue  # Skip optional params for basic test
            values = get_sample_values(param)
            args.append(f"{param.name}={values[0]}")

        call_args = ", ".join(args)
        await_prefix = "await " if func.is_async else ""

        if func.return_type and func.return_type != "None":
            lines.append(f"    result = {await_prefix}{func.name}({call_args})")
            lines.append("    assert result is not None")
        else:
            lines.append(f"    {await_prefix}{func.name}({call_args})")
            lines.append("    # Function executes without error")

        return lines

    def _generate_edge_case_tests(self, func: FunctionInfo, test_name_base: str) -> List[str]:
        """Generate edge case tests."""
        lines = []

        # Find parameters with edge cases
        for param in func.parameters[:self.config.get("max_params_for_parameterized", 3)]:
            edge_cases = get_edge_case_values(param)
            if not edge_cases:
                continue

            test_name = f"{test_name_base}_{param.name}_edge_cases"

            # Generate parameterized test
            param_values = ", ".join(f'({case[0]})' for case in edge_cases)
            lines.append(f'@pytest.mark.parametrize("{param.name}", [{param_values}])')

            async_prefix = "async " if func.is_async else ""
            lines.append(f"{async_prefix}def {test_name}({param.name}):")
            lines.append(f'    """Test {func.name} with edge case {param.name} values."""')

            # Build call with this parameter
            other_args = []
            for p in func.parameters:
                if p.name == param.name:
                    other_args.append(f"{p.name}={p.name}")
                elif p.default is not None:
                    continue
                else:
                    values = get_sample_values(p)
                    other_args.append(f"{p.name}={values[0]}")

            call_args = ", ".join(other_args)
            await_prefix = "await " if func.is_async else ""

            lines.append("    try:")
            lines.append(f"        {await_prefix}{func.name}({call_args})")
            lines.append("    except (ValueError, TypeError):")
            lines.append("        pass  # Expected for some edge cases")
            lines.append("")

            self.tests.append(GeneratedTest(
                name=test_name,
                code="\n".join(lines[-8:]),
                target_function=func.name,
                test_type="edge_case"
            ))

        return lines

    def _generate_type_check_test(self, func: FunctionInfo, test_name_base: str) -> List[str]:
        """Generate return type check test."""
        lines = []
        test_name = f"{test_name_base}_returns_correct_type"

        async_prefix = "async " if func.is_async else ""
        lines.append(f"{async_prefix}def {test_name}():")
        lines.append(f'    """Test that {func.name} returns correct type."""')

        # Generate call
        args = []
        for param in func.parameters:
            if param.default is not None:
                continue
            values = get_sample_values(param)
            args.append(f"{param.name}={values[0]}")

        call_args = ", ".join(args)
        await_prefix = "await " if func.is_async else ""
        lines.append(f"    result = {await_prefix}{func.name}({call_args})")

        # Type assertion
        return_type = func.return_type
        if return_type:
            # Map type hints to isinstance checks
            type_map = {
                "str": "str",
                "int": "int",
                "float": "(int, float)",
                "bool": "bool",
                "list": "list",
                "dict": "dict",
                "List": "list",
                "Dict": "dict",
            }

            for hint, check in type_map.items():
                if hint in return_type:
                    lines.append(f"    assert isinstance(result, {check})")
                    break
            else:
                lines.append(f"    # Expected return type: {return_type}")

        self.tests.append(GeneratedTest(
            name=test_name,
            code="\n".join(lines),
            target_function=func.name,
            test_type="type_check"
        ))

        return lines

    def _generate_unittest_function_tests(self, func: FunctionInfo) -> List[str]:
        """Generate unittest-style tests for a function."""
        lines = []
        test_name = f"test_{func.name}"

        lines.append(f"    def {test_name}(self):")
        if self.config.get("include_docstrings"):
            lines.append(f'        """Test {func.name}."""')

        # Generate call with sample arguments
        args = []
        for param in func.parameters:
            if param.default is not None:
                continue
            values = get_sample_values(param)
            args.append(f"{param.name}={values[0]}")

        call_args = ", ".join(args)

        if func.return_type and func.return_type != "None":
            lines.append(f"        result = {func.name}({call_args})")
            lines.append("        self.assertIsNotNone(result)")
        else:
            lines.append(f"        {func.name}({call_args})")

        return lines

    def _generate_class_tests(self, cls: ClassInfo, module_name: str) -> List[str]:
        """Generate tests for a class."""
        lines = []

        if self.framework == TestFramework.PYTEST:
            lines.append(f"class Test{cls.name}:")
            lines.append(f'    """Tests for {cls.name}."""')
            lines.append("")

            # Fixture for instance
            if cls.has_init:
                lines.append("    @pytest.fixture")
                lines.append("    def instance(self):")
                lines.append(f'        """Create {cls.name} instance."""')

                # Find __init__ params
                init_method = next((m for m in cls.methods if m.name == "__init__"), None)
                if init_method:
                    args = []
                    for param in init_method.parameters:
                        if param.default is not None:
                            continue
                        values = get_sample_values(param)
                        args.append(f"{param.name}={values[0]}")
                    call_args = ", ".join(args)
                    lines.append(f"        return {cls.name}({call_args})")
                else:
                    lines.append(f"        return {cls.name}()")
                lines.append("")

            # Generate method tests
            for method in cls.methods:
                if method.name.startswith("_") or method.is_property:
                    continue
                method_tests = self._generate_method_tests(method, cls)
                lines.extend(method_tests)
                lines.append("")

        else:
            lines.append(f"class Test{cls.name}(unittest.TestCase):")
            lines.append(f'    """Tests for {cls.name}."""')
            lines.append("")

            # setUp method
            if cls.has_init:
                lines.append("    def setUp(self):")
                lines.append(f'        """Set up test fixtures."""')
                lines.append(f"        self.instance = {cls.name}()")
                lines.append("")

            # Generate method tests
            for method in cls.methods:
                if method.name.startswith("_") or method.is_property:
                    continue
                method_tests = self._generate_unittest_method_tests(method, cls)
                lines.extend(method_tests)
                lines.append("")

        return lines

    def _generate_method_tests(self, method: FunctionInfo, cls: ClassInfo) -> List[str]:
        """Generate pytest tests for a class method."""
        lines = []
        test_name = f"test_{method.name}"

        # Determine if we need the instance fixture
        needs_instance = not method.is_staticmethod and not method.is_classmethod

        if needs_instance and cls.has_init:
            async_prefix = "async " if method.is_async else ""
            lines.append(f"    {async_prefix}def {test_name}(self, instance):")
        else:
            async_prefix = "async " if method.is_async else ""
            lines.append(f"    {async_prefix}def {test_name}(self):")

        if self.config.get("include_docstrings"):
            lines.append(f'        """Test {cls.name}.{method.name}."""')

        # Generate call
        args = []
        for param in method.parameters:
            if param.default is not None:
                continue
            values = get_sample_values(param)
            args.append(f"{param.name}={values[0]}")

        call_args = ", ".join(args)
        await_prefix = "await " if method.is_async else ""

        if method.is_staticmethod:
            call = f"{cls.name}.{method.name}({call_args})"
        elif method.is_classmethod:
            call = f"{cls.name}.{method.name}({call_args})"
        elif needs_instance and cls.has_init:
            call = f"instance.{method.name}({call_args})"
        else:
            call = f"{cls.name}().{method.name}({call_args})"

        if method.return_type and method.return_type != "None":
            lines.append(f"        result = {await_prefix}{call}")
            lines.append("        assert result is not None")
        else:
            lines.append(f"        {await_prefix}{call}")

        self.tests.append(GeneratedTest(
            name=f"Test{cls.name}.{test_name}",
            code="\n".join(lines),
            target_function=f"{cls.name}.{method.name}",
            test_type="basic"
        ))

        return lines

    def _generate_unittest_method_tests(self, method: FunctionInfo, cls: ClassInfo) -> List[str]:
        """Generate unittest tests for a class method."""
        lines = []
        test_name = f"test_{method.name}"

        lines.append(f"    def {test_name}(self):")
        if self.config.get("include_docstrings"):
            lines.append(f'        """Test {cls.name}.{method.name}."""')

        # Generate call
        args = []
        for param in method.parameters:
            if param.default is not None:
                continue
            values = get_sample_values(param)
            args.append(f"{param.name}={values[0]}")

        call_args = ", ".join(args)

        if method.is_staticmethod:
            call = f"{cls.name}.{method.name}({call_args})"
        elif method.is_classmethod:
            call = f"{cls.name}.{method.name}({call_args})"
        else:
            call = f"self.instance.{method.name}({call_args})"

        if method.return_type and method.return_type != "None":
            lines.append(f"        result = {call}")
            lines.append("        self.assertIsNotNone(result)")
        else:
            lines.append(f"        {call}")

        return lines


# === Core Functions ===

def generate_tests(
    source_code: str,
    module_name: str,
    framework: TestFramework = TestFramework.PYTEST,
    config: Dict[str, Any] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> TestGenerationResult:
    """
    Generate tests from source code.

    Args:
        source_code: Python source code to analyze
        module_name: Name of the module being tested
        framework: Test framework to use
        config: Generation configuration
        progress_callback: Optional progress callback

    Returns:
        TestGenerationResult with generated test code
    """
    config = {**DEFAULT_CONFIG, **(config or {})}

    try:
        # Analyze code
        if progress_callback:
            progress_callback({"step": 1, "total": 3, "message": "Analyzing code..."})

        module_info = analyze_code(source_code)

        # Check if there's anything to test
        if not module_info.functions and not module_info.classes:
            return TestGenerationResult(
                success=True,
                test_file_content="# No testable functions or classes found",
                warnings=["No testable functions or classes found in source code"]
            )

        # Generate tests
        if progress_callback:
            progress_callback({"step": 2, "total": 3, "message": "Generating tests..."})

        generator = TestGenerator(framework, config)
        test_content = generator.generate_tests(module_info, module_name)

        # Generate coverage hints
        if progress_callback:
            progress_callback({"step": 3, "total": 3, "message": "Finalizing..."})

        coverage_hints = []
        for func in module_info.functions:
            coverage_hints.append(f"Function '{func.name}': {len(func.parameters)} parameters")
        for cls in module_info.classes:
            coverage_hints.append(f"Class '{cls.name}': {len(cls.methods)} methods")

        return TestGenerationResult(
            success=True,
            test_file_content=test_content,
            tests_generated=generator.tests,
            coverage_hints=coverage_hints
        )

    except SyntaxError as e:
        return TestGenerationResult(
            success=False,
            error=f"Syntax error in source code: {e}"
        )
    except Exception as e:
        return TestGenerationResult(
            success=False,
            error=f"Test generation failed: {e}"
        )


def generate_tests_for_file(
    source_path: str,
    output_path: Optional[str] = None,
    framework: TestFramework = TestFramework.PYTEST,
    config: Dict[str, Any] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> TestGenerationResult:
    """
    Generate tests for a source file.

    Args:
        source_path: Path to source file
        output_path: Optional output path for test file
        framework: Test framework to use
        config: Generation configuration
        progress_callback: Optional progress callback

    Returns:
        TestGenerationResult with generated test code
    """
    source_path = Path(source_path)

    if not source_path.exists():
        return TestGenerationResult(
            success=False,
            error=f"Source file not found: {source_path}"
        )

    if not source_path.suffix == ".py":
        return TestGenerationResult(
            success=False,
            error="Source file must be a Python file (.py)"
        )

    try:
        source_code = source_path.read_text(encoding="utf-8")
    except Exception as e:
        return TestGenerationResult(
            success=False,
            error=f"Failed to read source file: {e}"
        )

    module_name = source_path.stem

    result = generate_tests(
        source_code=source_code,
        module_name=module_name,
        framework=framework,
        config=config,
        progress_callback=progress_callback
    )

    # Write output file if specified
    if result.success and output_path:
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result.test_file_content, encoding="utf-8")
        except Exception as e:
            result.warnings.append(f"Failed to write output file: {e}")

    return result


# === Skill Entry Point ===

def run(args: Dict[str, Any], tools: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for the test_generate skill.

    Args:
        args: Skill arguments
            - source_path: Path to source file (required if no source_code)
            - source_code: Source code string (required if no source_path)
            - module_name: Module name (required if using source_code)
            - output_path: Optional output path for test file
            - framework: Test framework ("pytest" or "unittest")
            - include_edge_cases: Whether to include edge case tests
            - include_type_checks: Whether to include type check tests
        tools: Available tools (unused)
        config: Skill configuration

    Returns:
        Result dict with success status and generated tests
    """
    source_path = args.get("source_path")
    source_code = args.get("source_code")
    module_name = args.get("module_name")
    output_path = args.get("output_path")
    framework_str = args.get("framework", "pytest")

    # Validate inputs
    if not source_path and not source_code:
        return {
            "success": False,
            "error": "Either source_path or source_code is required"
        }

    if source_code and not module_name:
        return {
            "success": False,
            "error": "module_name is required when using source_code"
        }

    # Parse framework
    try:
        framework = TestFramework(framework_str.lower())
    except ValueError:
        return {
            "success": False,
            "error": f"Invalid framework: {framework_str}. Must be 'pytest' or 'unittest'"
        }

    # Build config
    skill_config = {
        **DEFAULT_CONFIG,
        **config,
        "include_edge_cases": args.get("include_edge_cases", True),
        "include_type_checks": args.get("include_type_checks", True),
        "include_docstrings": args.get("include_docstrings", True),
    }

    # Get progress callback
    progress_callback = args.get("_progress_callback")

    # Generate tests
    if source_path:
        result = generate_tests_for_file(
            source_path=source_path,
            output_path=output_path,
            framework=framework,
            config=skill_config,
            progress_callback=progress_callback
        )
    else:
        result = generate_tests(
            source_code=source_code,
            module_name=module_name,
            framework=framework,
            config=skill_config,
            progress_callback=progress_callback
        )

        # Write output if specified
        if result.success and output_path:
            try:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(result.test_file_content, encoding="utf-8")
            except Exception as e:
                result.warnings.append(f"Failed to write output file: {e}")

    return result.to_dict()


# === CLI ===

if __name__ == "__main__":
    import sys

    # Example usage
    sample_code = '''
"""Sample module for testing."""

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

def greet(name: str, formal: bool = False) -> str:
    """Generate a greeting."""
    if formal:
        return f"Good day, {name}"
    return f"Hello, {name}"

class Calculator:
    """A simple calculator."""

    def __init__(self, initial: int = 0):
        self.value = initial

    def add(self, x: int) -> int:
        """Add to the value."""
        self.value += x
        return self.value

    def reset(self) -> None:
        """Reset the value."""
        self.value = 0
'''

    print("Test Generate Skill")
    print("=" * 40)

    result = generate_tests(sample_code, "sample")

    if result.success:
        print(f"\nGenerated {len(result.tests_generated)} tests:\n")
        print(result.test_file_content)
    else:
        print(f"Error: {result.error}")
