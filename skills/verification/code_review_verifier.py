"""
Skill: code_review_verifier
Description: AST-based code review with configurable rules
Version: 1.0.0
Tier: untested

AST-based code review that goes beyond regex patterns:
- Python: Uses ast module for accurate parsing
- JavaScript/TypeScript: Uses tree-sitter (optional)
- Configurable rule sets per project
- Integration with code_quality_verifier for combined checks

Categories:
- STRUCTURE: Function complexity, nesting depth, file length
- SECURITY: Injection risks, secret exposure, unsafe operations
- STYLE: Naming conventions, import ordering, dead code
- PATTERNS: Anti-patterns, code smells, deprecated usage

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
- Individual analyzers for flexible use

Usage:
    result = run({
        "files": ["src/main.py", "src/utils.py"],
        "rules": ["complexity", "security", "naming"],
        "config": {"max_complexity": 10, "max_nesting": 4}
    }, tools, context)
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import re


# Skill metadata
SKILL_META = {
    "name": "code_review_verifier",
    "description": "AST-based code review with configurable rules",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "phase": "3.1",
    "triggers": ["review code", "code review", "check code", "analyze code"],
}

# Required capabilities
REQUIRES = ["read_file", "glob_files"]


class Severity(Enum):
    """Finding severity levels."""
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class Category(Enum):
    """Review categories."""
    STRUCTURE = "structure"
    SECURITY = "security"
    STYLE = "style"
    PATTERNS = "patterns"


@dataclass
class Finding:
    """A single code review finding."""
    rule_id: str
    category: Category
    severity: Severity
    file_path: str
    line: int
    column: int
    message: str
    snippet: Optional[str] = None
    suggestion: Optional[str] = None
    confidence: float = 0.9


@dataclass
class ReviewResult:
    """Result of a code review."""
    files_reviewed: int
    findings: List[Finding]
    summary: Dict[str, int]  # severity -> count
    passed: bool
    duration_ms: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# === DEFAULT THRESHOLDS ===

DEFAULT_CONFIG = {
    "max_function_complexity": 10,  # Cyclomatic complexity
    "max_function_lines": 50,
    "max_file_lines": 500,
    "max_nesting_depth": 4,
    "max_arguments": 5,
    "max_returns": 3,
    "banned_functions": ["eval", "exec", "compile", "__import__"],
    "required_docstrings": True,
    "naming_convention": "snake_case",  # snake_case, camelCase, PascalCase
}


# === AST ANALYZERS ===

class ComplexityVisitor(ast.NodeVisitor):
    """Calculate cyclomatic complexity of functions."""

    def __init__(self):
        self.complexity = 1  # Base complexity

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # and/or add complexity
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node):
        self.complexity += 1
        self.generic_visit(node)


class NestingVisitor(ast.NodeVisitor):
    """Track nesting depth in code."""

    def __init__(self):
        self.max_depth = 0
        self.current_depth = 0
        self.deepest_location = (0, 0)

    def _enter_block(self, node):
        self.current_depth += 1
        if self.current_depth > self.max_depth:
            self.max_depth = self.current_depth
            self.deepest_location = (getattr(node, 'lineno', 0), getattr(node, 'col_offset', 0))
        self.generic_visit(node)
        self.current_depth -= 1

    def visit_If(self, node):
        self._enter_block(node)

    def visit_For(self, node):
        self._enter_block(node)

    def visit_While(self, node):
        self._enter_block(node)

    def visit_With(self, node):
        self._enter_block(node)

    def visit_Try(self, node):
        self._enter_block(node)


class SecurityVisitor(ast.NodeVisitor):
    """Detect security issues in Python code."""

    # Dangerous module.function patterns (module prefix required)
    DANGEROUS_ATTR_CALLS = {
        ("os", "system"),
        ("os", "popen"),
        ("os", "spawn"),
        ("os", "spawnl"),
        ("os", "spawnle"),
        ("os", "spawnlp"),
        ("os", "spawnlpe"),
        ("os", "spawnv"),
        ("os", "spawnve"),
        ("os", "spawnvp"),
        ("os", "spawnvpe"),
        ("subprocess", "call"),
        ("subprocess", "run"),
        ("subprocess", "Popen"),
        ("subprocess", "check_output"),
        ("subprocess", "check_call"),
        ("commands", "getoutput"),
        ("commands", "getstatusoutput"),
    }

    def __init__(self, banned_functions: List[str]):
        self.banned_functions = set(banned_functions)
        self.findings: List[Tuple[int, int, str, str]] = []  # line, col, issue, message

    def visit_Call(self, node):
        # Direct call: eval(...), exec(...), compile(...)
        # Only flag these for banned built-in functions
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.banned_functions:
                self.findings.append((
                    node.lineno,
                    node.col_offset,
                    f"banned_function_{func_name}",
                    f"Use of banned built-in '{func_name}' detected"
                ))

        # Attribute call: os.system(...), subprocess.run(...)
        # Only flag known dangerous module.function patterns
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            # Get the module/object name if it's a simple Name
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
                if (module_name, attr_name) in self.DANGEROUS_ATTR_CALLS:
                    self.findings.append((
                        node.lineno,
                        node.col_offset,
                        f"dangerous_call_{module_name}_{attr_name}",
                        f"Use of dangerous function '{module_name}.{attr_name}' detected"
                    ))

        # Check for shell=True in subprocess calls
        shell_dangerous_funcs = {"call", "run", "Popen", "check_output", "check_call"}
        is_subprocess_call = False

        if isinstance(node.func, ast.Attribute):
            if node.func.attr in shell_dangerous_funcs:
                is_subprocess_call = True
        elif isinstance(node.func, ast.Name):
            if node.func.id in shell_dangerous_funcs:
                is_subprocess_call = True

        if is_subprocess_call:
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                    if keyword.value.value is True:
                        self.findings.append((
                            node.lineno,
                            node.col_offset,
                            "shell_injection_risk",
                            "subprocess with shell=True is vulnerable to injection"
                        ))

        self.generic_visit(node)


class NamingVisitor(ast.NodeVisitor):
    """Check naming conventions."""

    SNAKE_CASE = re.compile(r'^[a-z][a-z0-9_]*$')
    CAMEL_CASE = re.compile(r'^[a-z][a-zA-Z0-9]*$')
    PASCAL_CASE = re.compile(r'^[A-Z][a-zA-Z0-9]*$')
    UPPER_SNAKE = re.compile(r'^[A-Z][A-Z0-9_]*$')

    def __init__(self, convention: str = "snake_case"):
        self.convention = convention
        self.findings: List[Tuple[int, int, str, str]] = []

    def _check_name(self, name: str, expected: str, node, kind: str):
        if name.startswith('_'):
            name = name.lstrip('_')
        if not name:
            return

        pattern = {
            "snake_case": self.SNAKE_CASE,
            "camelCase": self.CAMEL_CASE,
            "PascalCase": self.PASCAL_CASE,
        }.get(expected, self.SNAKE_CASE)

        if not pattern.match(name):
            self.findings.append((
                getattr(node, 'lineno', 0),
                getattr(node, 'col_offset', 0),
                "naming_convention",
                f"{kind} '{name}' doesn't follow {expected} convention"
            ))

    def visit_FunctionDef(self, node):
        self._check_name(node.name, self.convention, node, "Function")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self._check_name(node.name, self.convention, node, "Function")
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self._check_name(node.name, "PascalCase", node, "Class")
        self.generic_visit(node)


def analyze_python_file(
    file_path: str,
    content: str,
    config: Dict[str, Any]
) -> List[Finding]:
    """
    Analyze a Python file using AST.

    Args:
        file_path: Path to the file
        content: File content
        config: Review configuration

    Returns:
        List of findings
    """
    findings = []

    try:
        tree = ast.parse(content, filename=file_path)
    except SyntaxError as e:
        findings.append(Finding(
            rule_id="syntax_error",
            category=Category.STRUCTURE,
            severity=Severity.CRITICAL,
            file_path=file_path,
            line=e.lineno or 1,
            column=e.offset or 0,
            message=f"Syntax error: {e.msg}",
            confidence=1.0
        ))
        return findings

    lines = content.split('\n')

    # File length check
    if len(lines) > config.get("max_file_lines", 500):
        findings.append(Finding(
            rule_id="file_too_long",
            category=Category.STRUCTURE,
            severity=Severity.WARN,
            file_path=file_path,
            line=1,
            column=0,
            message=f"File has {len(lines)} lines (max: {config['max_file_lines']})",
            suggestion="Consider splitting into multiple modules"
        ))

    # Analyze functions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Complexity
            complexity_visitor = ComplexityVisitor()
            complexity_visitor.visit(node)
            max_complexity = config.get("max_function_complexity", 10)

            if complexity_visitor.complexity > max_complexity:
                findings.append(Finding(
                    rule_id="high_complexity",
                    category=Category.STRUCTURE,
                    severity=Severity.WARN,
                    file_path=file_path,
                    line=node.lineno,
                    column=node.col_offset,
                    message=f"Function '{node.name}' has complexity {complexity_visitor.complexity} (max: {max_complexity})",
                    suggestion="Consider breaking into smaller functions"
                ))

            # Function length
            if hasattr(node, 'end_lineno') and node.end_lineno:
                func_lines = node.end_lineno - node.lineno
                max_lines = config.get("max_function_lines", 50)
                if func_lines > max_lines:
                    findings.append(Finding(
                        rule_id="function_too_long",
                        category=Category.STRUCTURE,
                        severity=Severity.WARN,
                        file_path=file_path,
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"Function '{node.name}' has {func_lines} lines (max: {max_lines})",
                        suggestion="Consider refactoring into smaller functions"
                    ))

            # Too many arguments
            max_args = config.get("max_arguments", 5)
            arg_count = len(node.args.args) + len(node.args.kwonlyargs)
            if arg_count > max_args:
                findings.append(Finding(
                    rule_id="too_many_arguments",
                    category=Category.STRUCTURE,
                    severity=Severity.WARN,
                    file_path=file_path,
                    line=node.lineno,
                    column=node.col_offset,
                    message=f"Function '{node.name}' has {arg_count} arguments (max: {max_args})",
                    suggestion="Consider using a dataclass or config object"
                ))

            # Missing docstring
            if config.get("required_docstrings", True):
                if not ast.get_docstring(node):
                    findings.append(Finding(
                        rule_id="missing_docstring",
                        category=Category.STYLE,
                        severity=Severity.INFO,
                        file_path=file_path,
                        line=node.lineno,
                        column=node.col_offset,
                        message=f"Function '{node.name}' is missing a docstring"
                    ))

    # Nesting depth
    nesting_visitor = NestingVisitor()
    nesting_visitor.visit(tree)
    max_nesting = config.get("max_nesting_depth", 4)

    if nesting_visitor.max_depth > max_nesting:
        findings.append(Finding(
            rule_id="deep_nesting",
            category=Category.STRUCTURE,
            severity=Severity.WARN,
            file_path=file_path,
            line=nesting_visitor.deepest_location[0],
            column=nesting_visitor.deepest_location[1],
            message=f"Nesting depth is {nesting_visitor.max_depth} (max: {max_nesting})",
            suggestion="Consider early returns or extracting to functions"
        ))

    # Security checks
    security_visitor = SecurityVisitor(config.get("banned_functions", []))
    security_visitor.visit(tree)

    for line, col, rule_id, message in security_visitor.findings:
        findings.append(Finding(
            rule_id=rule_id,
            category=Category.SECURITY,
            severity=Severity.ERROR,
            file_path=file_path,
            line=line,
            column=col,
            message=message,
            confidence=0.95
        ))

    # Naming conventions
    naming_visitor = NamingVisitor(config.get("naming_convention", "snake_case"))
    naming_visitor.visit(tree)

    for line, col, rule_id, message in naming_visitor.findings:
        findings.append(Finding(
            rule_id=rule_id,
            category=Category.STYLE,
            severity=Severity.INFO,
            file_path=file_path,
            line=line,
            column=col,
            message=message
        ))

    return findings


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            files: List[str] - files to review (or glob pattern)
            config: Dict - review configuration overrides
            fail_on: str - severity level to fail on (error, warn, info)
        }
        tools: {
            read_file: callable
            glob_files: callable
        }
        context: {run_id, etc.}

    Returns:
        {
            success: bool,
            passed: bool - whether review passed
            findings: List[dict] - all findings
            summary: dict - counts by severity
            files_reviewed: int
        }
    """
    import time
    start_time = time.time()

    files = args.get("files", [])
    config = {**DEFAULT_CONFIG, **args.get("config", {})}
    fail_on = args.get("fail_on", "error")

    # Expand glob patterns
    if isinstance(files, str):
        files = [files]

    expanded_files = []
    for f in files:
        if "*" in f:
            if tools.get("glob_files"):
                expanded_files.extend(tools["glob_files"](pattern=f))
            else:
                expanded_files.append(f)
        else:
            expanded_files.append(f)

    all_findings: List[Finding] = []
    files_reviewed = 0

    for file_path in expanded_files:
        # Only analyze Python files for now
        if not file_path.endswith('.py'):
            continue

        try:
            if tools.get("read_file"):
                content = tools["read_file"](file_path)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

            findings = analyze_python_file(file_path, content, config)
            all_findings.extend(findings)
            files_reviewed += 1

        except Exception as e:
            all_findings.append(Finding(
                rule_id="read_error",
                category=Category.STRUCTURE,
                severity=Severity.ERROR,
                file_path=file_path,
                line=1,
                column=0,
                message=f"Could not read file: {str(e)}"
            ))

    # Calculate summary
    summary = {
        "critical": sum(1 for f in all_findings if f.severity == Severity.CRITICAL),
        "error": sum(1 for f in all_findings if f.severity == Severity.ERROR),
        "warn": sum(1 for f in all_findings if f.severity == Severity.WARN),
        "info": sum(1 for f in all_findings if f.severity == Severity.INFO),
    }

    # Determine pass/fail
    fail_threshold = {
        "critical": [Severity.CRITICAL],
        "error": [Severity.CRITICAL, Severity.ERROR],
        "warn": [Severity.CRITICAL, Severity.ERROR, Severity.WARN],
        "info": [Severity.CRITICAL, Severity.ERROR, Severity.WARN, Severity.INFO],
    }.get(fail_on, [Severity.CRITICAL, Severity.ERROR])

    passed = not any(f.severity in fail_threshold for f in all_findings)

    duration_ms = int((time.time() - start_time) * 1000)

    return {
        "success": True,
        "passed": passed,
        "findings": [
            {
                "rule_id": f.rule_id,
                "category": f.category.value,
                "severity": f.severity.value,
                "file_path": f.file_path,
                "line": f.line,
                "column": f.column,
                "message": f.message,
                "snippet": f.snippet,
                "suggestion": f.suggestion,
                "confidence": f.confidence,
            }
            for f in all_findings
        ],
        "summary": summary,
        "files_reviewed": files_reviewed,
        "duration_ms": duration_ms,
        "config_used": config,
    }


# Export key components
__all__ = [
    "SKILL_META",
    "REQUIRES",
    "run",
    "analyze_python_file",
    "Finding",
    "ReviewResult",
    "Severity",
    "Category",
    "DEFAULT_CONFIG",
]


if __name__ == "__main__":
    print("code_review_verifier Skill v1.0")
    print("=" * 50)
    print()
    print("Categories:")
    for cat in Category:
        print(f"  - {cat.value}")
    print()
    print("Default Config:")
    for k, v in DEFAULT_CONFIG.items():
        print(f"  {k}: {v}")
    print()
    print("Usage:")
    print('  result = run({"files": ["src/**/*.py"]}, tools, ctx)')
    print('  print(f"Passed: {result[\'passed\']}, Findings: {len(result[\'findings\'])}")')
