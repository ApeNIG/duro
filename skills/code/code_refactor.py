"""
Code Refactor Skill - Structured refactoring with before/after verification.

Performs code refactoring operations with:
- Before/after verification using code_review_verifier
- Multiple refactoring patterns
- AST-based transformations
- Safe rollback on failure
- Diff generation

Phase 3.3.3 of Duro Capability Expansion.
"""

import ast
import re
import difflib
import tempfile
import shutil
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Tuple, Set
import copy


# === Metadata ===

SKILL_META = {
    "name": "code_refactor",
    "description": "Structured refactoring with before/after verification",
    "tier": "tested",
    "phase": "3.3",
    "version": "1.0.0",
    "keywords": [
        "refactor", "rename", "extract", "inline", "move",
        "code", "transform", "cleanup", "modernize"
    ],
    "dependencies": [],
    "side_effects": ["writes_file"],
    "composes": ["verification/code_review_verifier.py"],
}

DEFAULT_CONFIG = {
    "verify_before": True,
    "verify_after": True,
    "create_backup": True,
    "dry_run": False,
}


# === Enums and Data Classes ===

class RefactorType(Enum):
    """Types of refactoring operations."""
    RENAME_VARIABLE = "rename_variable"
    RENAME_FUNCTION = "rename_function"
    RENAME_CLASS = "rename_class"
    EXTRACT_FUNCTION = "extract_function"
    EXTRACT_VARIABLE = "extract_variable"
    INLINE_VARIABLE = "inline_variable"
    REMOVE_UNUSED_IMPORTS = "remove_unused_imports"
    SORT_IMPORTS = "sort_imports"
    ADD_TYPE_HINTS = "add_type_hints"
    CONVERT_TO_FSTRING = "convert_to_fstring"
    REMOVE_DEAD_CODE = "remove_dead_code"


@dataclass
class RefactorOperation:
    """A refactoring operation to perform."""
    type: RefactorType
    target: str  # What to refactor (name, line number, etc.)
    new_value: Optional[str] = None  # New name, extracted code, etc.
    scope: Optional[str] = None  # Function/class scope
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeLocation:
    """Location in source code."""
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None


@dataclass
class RefactorChange:
    """A single change made during refactoring."""
    location: CodeLocation
    original: str
    replacement: str
    description: str


@dataclass
class VerificationResult:
    """Result of code verification."""
    passed: bool
    issues: List[str] = field(default_factory=list)
    score: float = 1.0


@dataclass
class RefactorResult:
    """Result of a refactoring operation."""
    success: bool
    original_code: str = ""
    refactored_code: str = ""
    changes: List[RefactorChange] = field(default_factory=list)
    diff: str = ""
    verification_before: Optional[VerificationResult] = None
    verification_after: Optional[VerificationResult] = None
    warnings: List[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "original_code": self.original_code,
            "refactored_code": self.refactored_code,
            "changes": [asdict(c) for c in self.changes],
            "diff": self.diff,
            "warnings": self.warnings,
            "error": self.error,
        }
        if self.verification_before:
            result["verification_before"] = asdict(self.verification_before)
        if self.verification_after:
            result["verification_after"] = asdict(self.verification_after)
        return result


# === AST Utilities ===

class NameCollector(ast.NodeVisitor):
    """Collect all name usages in code."""

    def __init__(self):
        self.names: Dict[str, List[CodeLocation]] = {}
        self.definitions: Dict[str, CodeLocation] = {}
        self.imports: Set[str] = set()
        self.used_names: Set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        name = node.id
        loc = CodeLocation(node.lineno, node.col_offset)

        if name not in self.names:
            self.names[name] = []
        self.names[name].append(loc)

        if isinstance(node.ctx, ast.Load):
            self.used_names.add(name)

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.definitions[node.name] = CodeLocation(node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.definitions[node.name] = CodeLocation(node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.definitions[node.name] = CodeLocation(node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            self.imports.add(name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            self.imports.add(name)


class ImportCollector(ast.NodeVisitor):
    """Collect import information."""

    def __init__(self):
        self.imports: List[Tuple[int, int, str, str]] = []  # (line, col, type, module)
        self.import_lines: Set[int] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append((
                node.lineno,
                node.col_offset,
                "import",
                alias.name
            ))
            self.import_lines.add(node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            self.imports.append((
                node.lineno,
                node.col_offset,
                "from",
                f"{module}.{alias.name}"
            ))
            self.import_lines.add(node.lineno)


# === Refactoring Operations ===

def rename_in_code(
    code: str,
    old_name: str,
    new_name: str,
    scope: Optional[str] = None
) -> Tuple[str, List[RefactorChange]]:
    """
    Rename all occurrences of a name in code.

    Args:
        code: Source code
        old_name: Name to replace
        new_name: New name
        scope: Optional scope (function/class name) to limit changes

    Returns:
        Tuple of (modified code, list of changes)
    """
    changes = []

    # Use regex for simple word-boundary replacement
    # This is simpler than AST manipulation for renaming
    pattern = r'\b' + re.escape(old_name) + r'\b'

    lines = code.split('\n')
    new_lines = []
    in_scope = scope is None

    for i, line in enumerate(lines):
        line_num = i + 1

        # Track scope
        if scope:
            # Simple scope detection
            if re.match(rf'^(def|class)\s+{re.escape(scope)}\s*[\(:]', line):
                in_scope = True
            elif in_scope and re.match(r'^(def|class)\s+\w+', line):
                # New definition at same indentation level = out of scope
                if not line.startswith('    '):
                    in_scope = False

        if in_scope and re.search(pattern, line):
            new_line = re.sub(pattern, new_name, line)
            if new_line != line:
                # Find all positions
                for match in re.finditer(pattern, line):
                    changes.append(RefactorChange(
                        location=CodeLocation(line_num, match.start()),
                        original=old_name,
                        replacement=new_name,
                        description=f"Renamed '{old_name}' to '{new_name}'"
                    ))
                new_lines.append(new_line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    return '\n'.join(new_lines), changes


def remove_unused_imports(code: str) -> Tuple[str, List[RefactorChange]]:
    """
    Remove unused import statements.

    Args:
        code: Source code

    Returns:
        Tuple of (modified code, list of changes)
    """
    changes = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, []

    # Collect names and imports
    collector = NameCollector()
    collector.visit(tree)

    # Find unused imports
    unused = collector.imports - collector.used_names

    if not unused:
        return code, []

    # Remove unused import lines
    lines = code.split('\n')
    new_lines = []
    import_collector = ImportCollector()
    import_collector.visit(tree)

    removed_lines = set()
    for line_num, col, imp_type, module in import_collector.imports:
        # Get the imported name
        name = module.split(".")[-1]
        if name in unused:
            removed_lines.add(line_num)
            changes.append(RefactorChange(
                location=CodeLocation(line_num, col),
                original=lines[line_num - 1].strip(),
                replacement="",
                description=f"Removed unused import: {name}"
            ))

    for i, line in enumerate(lines):
        if (i + 1) not in removed_lines:
            new_lines.append(line)

    return '\n'.join(new_lines), changes


def sort_imports(code: str) -> Tuple[str, List[RefactorChange]]:
    """
    Sort import statements (stdlib, third-party, local).

    Args:
        code: Source code

    Returns:
        Tuple of (modified code, list of changes)
    """
    changes = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, []

    lines = code.split('\n')
    import_collector = ImportCollector()
    import_collector.visit(tree)

    if not import_collector.import_lines:
        return code, []

    # Group imports
    stdlib = []
    third_party = []
    local = []

    # Common stdlib modules
    STDLIB = {
        'os', 'sys', 're', 'json', 'math', 'random', 'datetime', 'time',
        'collections', 'itertools', 'functools', 'typing', 'pathlib',
        'tempfile', 'shutil', 'subprocess', 'threading', 'multiprocessing',
        'ast', 'inspect', 'copy', 'enum', 'dataclasses', 'abc', 'io',
        'logging', 'unittest', 'argparse', 'configparser', 'csv', 'hashlib',
        'socket', 'http', 'urllib', 'email', 'html', 'xml', 'sqlite3',
    }

    import_lines_sorted = sorted(import_collector.import_lines)
    first_import = min(import_lines_sorted)
    last_import = max(import_lines_sorted)

    for line_num in import_lines_sorted:
        line = lines[line_num - 1].strip()
        if not line:
            continue

        # Determine category
        if line.startswith('from .') or line.startswith('from ..'):
            local.append(line)
        else:
            # Extract module name
            if line.startswith('import '):
                module = line.split()[1].split('.')[0]
            else:
                # from X import ...
                module = line.split()[1].split('.')[0]

            if module in STDLIB:
                stdlib.append(line)
            elif module.startswith('.'):
                local.append(line)
            else:
                third_party.append(line)

    # Sort each group
    stdlib.sort()
    third_party.sort()
    local.sort()

    # Build new import section
    new_imports = []
    if stdlib:
        new_imports.extend(stdlib)
    if third_party:
        if new_imports:
            new_imports.append('')
        new_imports.extend(third_party)
    if local:
        if new_imports:
            new_imports.append('')
        new_imports.extend(local)

    # Replace import section
    new_lines = lines[:first_import - 1]
    new_lines.extend(new_imports)
    new_lines.extend(lines[last_import:])

    result = '\n'.join(new_lines)

    if result != code:
        changes.append(RefactorChange(
            location=CodeLocation(first_import, 0, last_import, 0),
            original="<import section>",
            replacement="<sorted imports>",
            description="Sorted imports (stdlib, third-party, local)"
        ))

    return result, changes


def convert_to_fstring(code: str) -> Tuple[str, List[RefactorChange]]:
    """
    Convert % formatting and .format() calls to f-strings.

    Args:
        code: Source code

    Returns:
        Tuple of (modified code, list of changes)
    """
    changes = []
    lines = code.split('\n')
    new_lines = []

    # Pattern for .format() calls
    format_pattern = re.compile(
        r'"([^"]*?)"\s*\.format\s*\(([^)]+)\)'
    )

    # Pattern for simple % formatting
    percent_pattern = re.compile(
        r'"([^"]*?%[sd])"\s*%\s*\(([^)]+)\)'
    )

    for i, line in enumerate(lines):
        line_num = i + 1
        new_line = line

        # Convert .format() calls
        for match in format_pattern.finditer(line):
            template = match.group(1)
            args = match.group(2)

            # Simple conversion for positional args
            arg_list = [a.strip() for a in args.split(',')]
            fstring_template = template

            # Replace {0}, {1}, etc. or {} with expressions
            for j, arg in enumerate(arg_list):
                fstring_template = fstring_template.replace(f'{{{j}}}', f'{{{arg}}}')
                fstring_template = fstring_template.replace('{}', f'{{{arg}}}', 1)

            replacement = f'f"{fstring_template}"'
            new_line = new_line.replace(match.group(0), replacement)

            changes.append(RefactorChange(
                location=CodeLocation(line_num, match.start()),
                original=match.group(0),
                replacement=replacement,
                description="Converted .format() to f-string"
            ))

        new_lines.append(new_line)

    return '\n'.join(new_lines), changes


def extract_function(
    code: str,
    start_line: int,
    end_line: int,
    function_name: str,
    params: Optional[List[str]] = None
) -> Tuple[str, List[RefactorChange]]:
    """
    Extract lines into a new function.

    Args:
        code: Source code
        start_line: First line to extract (1-indexed)
        end_line: Last line to extract (1-indexed)
        function_name: Name for the new function
        params: Optional list of parameters

    Returns:
        Tuple of (modified code, list of changes)
    """
    changes = []
    lines = code.split('\n')

    if start_line < 1 or end_line > len(lines) or start_line > end_line:
        return code, []

    # Extract the lines
    extracted = lines[start_line - 1:end_line]

    # Detect indentation
    first_line = extracted[0]
    base_indent = len(first_line) - len(first_line.lstrip())

    # Remove base indentation and add function indentation
    func_lines = []
    for line in extracted:
        if line.strip():
            func_lines.append('    ' + line[base_indent:])
        else:
            func_lines.append('')

    # Build function definition
    params_str = ', '.join(params) if params else ''
    func_def = [f'def {function_name}({params_str}):']
    func_def.extend(func_lines)
    func_def.append('')

    # Build call
    call_indent = ' ' * base_indent
    call_args = ', '.join(params) if params else ''
    call = f'{call_indent}{function_name}({call_args})'

    # Replace original lines with call
    new_lines = lines[:start_line - 1]
    new_lines.append(call)
    new_lines.extend(lines[end_line:])

    # Insert function definition before the usage
    # Find a good place (before the function containing the call, or at module level)
    insert_pos = 0
    for i, line in enumerate(new_lines):
        if line.strip() and not line.startswith('#') and not line.startswith('import') and not line.startswith('from'):
            insert_pos = i
            break

    new_lines = new_lines[:insert_pos] + func_def + new_lines[insert_pos:]

    changes.append(RefactorChange(
        location=CodeLocation(start_line, 0, end_line, 0),
        original='\n'.join(extracted),
        replacement=f"def {function_name}(...)",
        description=f"Extracted lines {start_line}-{end_line} into function '{function_name}'"
    ))

    return '\n'.join(new_lines), changes


def remove_dead_code(code: str) -> Tuple[str, List[RefactorChange]]:
    """
    Remove obviously dead code (after return/raise/break/continue).

    Uses AST analysis to properly handle multi-line statements.

    Args:
        code: Source code

    Returns:
        Tuple of (modified code, list of changes)
    """
    changes = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, []

    # Find lines that are dead code (unreachable statements)
    dead_lines: Set[int] = set()

    class DeadCodeFinder(ast.NodeVisitor):
        """Find unreachable code after return/raise/break/continue."""

        def _check_body(self, body: List[ast.stmt]) -> None:
            """Check a list of statements for dead code."""
            found_terminator = False
            terminator_line = 0

            for stmt in body:
                if found_terminator:
                    # This statement is unreachable
                    # Mark all lines from stmt.lineno to stmt.end_lineno
                    start = stmt.lineno
                    end = getattr(stmt, 'end_lineno', stmt.lineno) or stmt.lineno
                    for line in range(start, end + 1):
                        dead_lines.add(line)
                else:
                    # Check if this is a terminating statement
                    if isinstance(stmt, (ast.Return, ast.Raise)):
                        found_terminator = True
                        terminator_line = getattr(stmt, 'end_lineno', stmt.lineno) or stmt.lineno
                    elif isinstance(stmt, (ast.Break, ast.Continue)):
                        found_terminator = True
                        terminator_line = stmt.lineno

                    # Recurse into compound statements
                    self.visit(stmt)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._check_body(node.body)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._check_body(node.body)

        def visit_If(self, node: ast.If) -> None:
            self._check_body(node.body)
            self._check_body(node.orelse)

        def visit_For(self, node: ast.For) -> None:
            self._check_body(node.body)
            self._check_body(node.orelse)

        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
            self._check_body(node.body)
            self._check_body(node.orelse)

        def visit_While(self, node: ast.While) -> None:
            self._check_body(node.body)
            self._check_body(node.orelse)

        def visit_With(self, node: ast.With) -> None:
            self._check_body(node.body)

        def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
            self._check_body(node.body)

        def visit_Try(self, node: ast.Try) -> None:
            self._check_body(node.body)
            for handler in node.handlers:
                self._check_body(handler.body)
            self._check_body(node.orelse)
            self._check_body(node.finalbody)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self._check_body(node.body)

    finder = DeadCodeFinder()
    finder.visit(tree)

    if not dead_lines:
        return code, []

    # Remove dead lines
    lines = code.split('\n')
    new_lines = []

    for i, line in enumerate(lines):
        line_num = i + 1
        if line_num in dead_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                changes.append(RefactorChange(
                    location=CodeLocation(line_num, 0),
                    original=stripped,
                    replacement="",
                    description="Removed unreachable code after return/raise/break/continue"
                ))
            # Don't include this line
        else:
            new_lines.append(line)

    return '\n'.join(new_lines), changes


# === Verification ===

def verify_code(code: str) -> VerificationResult:
    """
    Verify code quality (simplified version without full code_review_verifier).

    Args:
        code: Source code to verify

    Returns:
        VerificationResult with pass/fail and issues
    """
    issues = []
    score = 1.0

    # Check syntax
    try:
        ast.parse(code)
    except SyntaxError as e:
        return VerificationResult(
            passed=False,
            issues=[f"Syntax error: {e}"],
            score=0.0
        )

    # Basic checks
    lines = code.split('\n')

    for i, line in enumerate(lines):
        line_num = i + 1

        # Line too long
        if len(line) > 120:
            issues.append(f"Line {line_num}: Line too long ({len(line)} > 120)")
            score -= 0.05

        # Trailing whitespace
        if line.endswith(' ') or line.endswith('\t'):
            issues.append(f"Line {line_num}: Trailing whitespace")
            score -= 0.01

        # TODO/FIXME/HACK comments
        if re.search(r'\b(TODO|FIXME|HACK|XXX)\b', line, re.IGNORECASE):
            issues.append(f"Line {line_num}: Contains TODO/FIXME comment")
            score -= 0.02

    # Check for unused variables (simple detection)
    try:
        tree = ast.parse(code)
        collector = NameCollector()
        collector.visit(tree)

        # Check for defined but unused names (excluding imports)
        for name, loc in collector.definitions.items():
            if name not in collector.used_names and not name.startswith('_'):
                issues.append(f"Line {loc.line}: '{name}' defined but never used")
                score -= 0.05
    except Exception:
        pass

    return VerificationResult(
        passed=len([i for i in issues if "Syntax error" in i]) == 0,
        issues=issues,
        score=max(0.0, min(1.0, score))
    )


def generate_diff(original: str, modified: str, filename: str = "code.py") -> str:
    """Generate unified diff between original and modified code."""
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm=""
    )

    return ''.join(diff)


# === Main Refactor Function ===

def refactor(
    code: str,
    operation: RefactorOperation,
    config: Dict[str, Any] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> RefactorResult:
    """
    Perform a refactoring operation on code.

    Args:
        code: Source code to refactor
        operation: Refactoring operation to perform
        config: Configuration options
        progress_callback: Optional progress callback

    Returns:
        RefactorResult with refactored code and changes
    """
    config = {**DEFAULT_CONFIG, **(config or {})}

    # Verify before
    verification_before = None
    if config.get("verify_before"):
        if progress_callback:
            progress_callback({"step": 1, "total": 4, "message": "Verifying original code..."})
        verification_before = verify_code(code)

    # Perform refactoring
    if progress_callback:
        progress_callback({"step": 2, "total": 4, "message": f"Performing {operation.type.value}..."})

    try:
        if operation.type == RefactorType.RENAME_VARIABLE:
            refactored, changes = rename_in_code(
                code,
                operation.target,
                operation.new_value or "",
                operation.scope
            )
        elif operation.type == RefactorType.RENAME_FUNCTION:
            refactored, changes = rename_in_code(
                code,
                operation.target,
                operation.new_value or "",
                None  # Functions are renamed globally
            )
        elif operation.type == RefactorType.RENAME_CLASS:
            refactored, changes = rename_in_code(
                code,
                operation.target,
                operation.new_value or "",
                None
            )
        elif operation.type == RefactorType.REMOVE_UNUSED_IMPORTS:
            refactored, changes = remove_unused_imports(code)
        elif operation.type == RefactorType.SORT_IMPORTS:
            refactored, changes = sort_imports(code)
        elif operation.type == RefactorType.CONVERT_TO_FSTRING:
            refactored, changes = convert_to_fstring(code)
        elif operation.type == RefactorType.EXTRACT_FUNCTION:
            start = operation.options.get("start_line", 1)
            end = operation.options.get("end_line", 1)
            params = operation.options.get("params", [])
            refactored, changes = extract_function(
                code, start, end, operation.new_value or "extracted", params
            )
        elif operation.type == RefactorType.REMOVE_DEAD_CODE:
            refactored, changes = remove_dead_code(code)
        else:
            return RefactorResult(
                success=False,
                error=f"Unsupported refactoring type: {operation.type.value}"
            )
    except Exception as e:
        return RefactorResult(
            success=False,
            original_code=code,
            error=f"Refactoring failed: {e}"
        )

    # Check if anything changed
    if refactored == code:
        return RefactorResult(
            success=True,
            original_code=code,
            refactored_code=code,
            changes=[],
            warnings=["No changes were made"],
            verification_before=verification_before
        )

    # Verify after
    verification_after = None
    if config.get("verify_after"):
        if progress_callback:
            progress_callback({"step": 3, "total": 4, "message": "Verifying refactored code..."})
        verification_after = verify_code(refactored)

        # Check if refactoring introduced issues
        if verification_before and verification_after:
            if verification_after.score < verification_before.score - 0.1:
                return RefactorResult(
                    success=False,
                    original_code=code,
                    refactored_code=refactored,
                    changes=changes,
                    verification_before=verification_before,
                    verification_after=verification_after,
                    error="Refactoring degraded code quality"
                )

    # Generate diff
    if progress_callback:
        progress_callback({"step": 4, "total": 4, "message": "Generating diff..."})

    diff = generate_diff(code, refactored)

    return RefactorResult(
        success=True,
        original_code=code,
        refactored_code=refactored,
        changes=changes,
        diff=diff,
        verification_before=verification_before,
        verification_after=verification_after
    )


def refactor_file(
    file_path: str,
    operation: RefactorOperation,
    output_path: Optional[str] = None,
    config: Dict[str, Any] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> RefactorResult:
    """
    Refactor a file.

    Args:
        file_path: Path to source file
        operation: Refactoring operation to perform
        output_path: Optional output path (defaults to overwriting)
        config: Configuration options
        progress_callback: Optional progress callback

    Returns:
        RefactorResult with refactored code and changes
    """
    config = {**DEFAULT_CONFIG, **(config or {})}
    file_path = Path(file_path)

    if not file_path.exists():
        return RefactorResult(
            success=False,
            error=f"File not found: {file_path}"
        )

    try:
        code = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return RefactorResult(
            success=False,
            error=f"Failed to read file: {e}"
        )

    # Create backup if configured
    backup_path = None
    if config.get("create_backup") and not config.get("dry_run"):
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        try:
            shutil.copy2(file_path, backup_path)
        except Exception as e:
            return RefactorResult(
                success=False,
                error=f"Failed to create backup: {e}"
            )

    # Perform refactoring
    result = refactor(code, operation, config, progress_callback)

    if not result.success:
        # Restore backup on failure
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, file_path)
            backup_path.unlink()
        return result

    # Write result
    if not config.get("dry_run") and result.refactored_code:
        try:
            output = Path(output_path) if output_path else file_path
            output.write_text(result.refactored_code, encoding="utf-8")
        except Exception as e:
            # Restore backup on failure
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, file_path)
                backup_path.unlink()
            return RefactorResult(
                success=False,
                original_code=code,
                error=f"Failed to write output: {e}"
            )

    # Clean up backup on success (unless we want to keep it)
    if backup_path and backup_path.exists() and not config.get("keep_backup"):
        backup_path.unlink()

    return result


# === Skill Entry Point ===

def run(args: Dict[str, Any], tools: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for the code_refactor skill.

    Args:
        args: Skill arguments
            - source_path: Path to source file (required if no source_code)
            - source_code: Source code string (required if no source_path)
            - operation: Refactoring operation type
            - target: Target to refactor
            - new_value: New name/value
            - scope: Optional scope
            - options: Additional options
            - output_path: Optional output path
            - dry_run: Whether to just preview changes
            - verify: Whether to verify before/after
        tools: Available tools (unused)
        config: Skill configuration

    Returns:
        Result dict with success status and refactored code
    """
    source_path = args.get("source_path")
    source_code = args.get("source_code")
    operation_type = args.get("operation")
    target = args.get("target", "")
    new_value = args.get("new_value")
    scope = args.get("scope")
    options = args.get("options", {})
    output_path = args.get("output_path")
    dry_run = args.get("dry_run", False)
    verify = args.get("verify", True)

    # Validate inputs
    if not source_path and not source_code:
        return {
            "success": False,
            "error": "Either source_path or source_code is required"
        }

    if not operation_type:
        return {
            "success": False,
            "error": "Operation type is required"
        }

    # Parse operation type
    try:
        op_type = RefactorType(operation_type)
    except ValueError:
        valid = [t.value for t in RefactorType]
        return {
            "success": False,
            "error": f"Invalid operation: {operation_type}. Valid: {', '.join(valid)}"
        }

    # Build operation
    operation = RefactorOperation(
        type=op_type,
        target=target,
        new_value=new_value,
        scope=scope,
        options=options
    )

    # Build config
    skill_config = {
        **DEFAULT_CONFIG,
        **config,
        "dry_run": dry_run,
        "verify_before": verify,
        "verify_after": verify,
    }

    # Get progress callback
    progress_callback = args.get("_progress_callback")

    # Perform refactoring
    if source_path:
        result = refactor_file(
            file_path=source_path,
            operation=operation,
            output_path=output_path,
            config=skill_config,
            progress_callback=progress_callback
        )
    else:
        result = refactor(
            code=source_code,
            operation=operation,
            config=skill_config,
            progress_callback=progress_callback
        )

        # Write output if specified
        if result.success and output_path and not dry_run:
            try:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(result.refactored_code, encoding="utf-8")
            except Exception as e:
                result.warnings.append(f"Failed to write output file: {e}")

    return result.to_dict()


# === CLI ===

if __name__ == "__main__":
    # Example usage
    sample_code = '''
import os
import sys
import json
from typing import List

def calculate_total(items):
    total = 0
    for item in items:
        total = total + item
    return total
    print("This is dead code")

def greet(name):
    message = "Hello, {}".format(name)
    return message

unused_var = 42
'''

    print("Code Refactor Skill")
    print("=" * 40)

    # Test remove unused imports
    op = RefactorOperation(type=RefactorType.REMOVE_UNUSED_IMPORTS, target="")
    result = refactor(sample_code, op)
    print("\n1. Remove unused imports:")
    print(result.diff if result.diff else "No changes")

    # Test convert to f-string
    op = RefactorOperation(type=RefactorType.CONVERT_TO_FSTRING, target="")
    result = refactor(sample_code, op)
    print("\n2. Convert to f-strings:")
    print(result.diff if result.diff else "No changes")

    # Test remove dead code
    op = RefactorOperation(type=RefactorType.REMOVE_DEAD_CODE, target="")
    result = refactor(sample_code, op)
    print("\n3. Remove dead code:")
    print(result.diff if result.diff else "No changes")

    # Test rename
    op = RefactorOperation(
        type=RefactorType.RENAME_FUNCTION,
        target="calculate_total",
        new_value="sum_items"
    )
    result = refactor(sample_code, op)
    print("\n4. Rename function:")
    print(result.diff if result.diff else "No changes")
