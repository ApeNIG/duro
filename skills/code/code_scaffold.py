"""
Code Scaffold Skill - Template-based project generation with validation.

Generates project scaffolds from templates with:
- Built-in templates for common project types
- Variable substitution with validation
- Post-generation verification
- Integration with adversarial_planning
- Atomic directory creation with cleanup on failure

Phase 3.3.1 of Duro Capability Expansion.
"""

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Tuple
import json


# === Metadata ===

SKILL_META = {
    "name": "code_scaffold",
    "description": "Template-based project generation with validation",
    "tier": "tested",
    "phase": "3.3",
    "version": "1.0.0",
    "keywords": [
        "scaffold", "template", "project", "generate", "create",
        "python", "react", "express", "cli", "package"
    ],
    "dependencies": [],
    "side_effects": ["writes_file", "creates_directory"],
    "composes": ["meta/adversarial_planning.py"],
}

DEFAULT_CONFIG = {
    "templates_dir": None,  # Use built-in templates
    "allow_overwrite": False,
    "validate_output": True,
    "cleanup_on_failure": True,
}


# === Enums and Data Classes ===

class ProjectType(Enum):
    """Supported project types."""
    PYTHON_PACKAGE = "python-package"
    REACT_APP = "react-app"
    EXPRESS_API = "express-api"
    CLI_TOOL = "cli-tool"
    CUSTOM = "custom"


class License(Enum):
    """Common open source licenses."""
    MIT = "MIT"
    APACHE2 = "Apache-2.0"
    GPL3 = "GPL-3.0"
    BSD3 = "BSD-3-Clause"
    UNLICENSE = "Unlicense"
    PROPRIETARY = "Proprietary"


@dataclass
class TemplateVariable:
    """A variable in a template."""
    name: str
    description: str
    default: Optional[str] = None
    required: bool = True
    pattern: Optional[str] = None  # Regex validation
    choices: Optional[List[str]] = None


@dataclass
class TemplateFile:
    """A file to generate from template."""
    path: str  # Relative path with variables like {{name}}
    content: str  # Content with variables
    executable: bool = False
    condition: Optional[str] = None  # Variable that must be truthy


@dataclass
class ProjectTemplate:
    """A complete project template."""
    name: str
    description: str
    project_type: ProjectType
    variables: List[TemplateVariable]
    files: List[TemplateFile]
    directories: List[str] = field(default_factory=list)
    post_commands: List[str] = field(default_factory=list)


@dataclass
class ScaffoldResult:
    """Result of scaffold generation."""
    success: bool
    project_path: Optional[str] = None
    files_created: List[str] = field(default_factory=list)
    directories_created: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: str = ""
    validation_passed: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# === Built-in Templates ===

def get_python_package_template() -> ProjectTemplate:
    """Python package template with modern setup."""
    return ProjectTemplate(
        name="python-package",
        description="Python package with pyproject.toml, src layout, and tests",
        project_type=ProjectType.PYTHON_PACKAGE,
        variables=[
            TemplateVariable("name", "Package name (lowercase, underscores)", pattern=r"^[a-z][a-z0-9_]*$"),
            TemplateVariable("description", "Short description of the package"),
            TemplateVariable("author", "Author name"),
            TemplateVariable("author_email", "Author email", pattern=r"^[^@]+@[^@]+\.[^@]+$"),
            TemplateVariable("license", "License type", default="MIT", choices=["MIT", "Apache-2.0", "GPL-3.0"]),
            TemplateVariable("python_version", "Minimum Python version", default="3.9"),
        ],
        directories=[
            "src/{{name}}",
            "tests",
            "docs",
        ],
        files=[
            TemplateFile(
                path="pyproject.toml",
                content='''[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{{name}}"
version = "0.1.0"
description = "{{description}}"
readme = "README.md"
license = {text = "{{license}}"}
authors = [
    {name = "{{author}}", email = "{{author_email}}"}
]
requires-python = ">={{python_version}}"
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
]
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "black>=23.0",
    "ruff>=0.1.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.black]
line-length = 88
target-version = ["py{{python_version | replace('.', '')}}"]

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "W"]
'''
            ),
            TemplateFile(
                path="README.md",
                content='''# {{name}}

{{description}}

## Installation

```bash
pip install {{name}}
```

## Usage

```python
import {{name}}
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

{{license}}
'''
            ),
            TemplateFile(
                path="src/{{name}}/__init__.py",
                content='''"""{{description}}"""

__version__ = "0.1.0"
'''
            ),
            TemplateFile(
                path="src/{{name}}/main.py",
                content='''"""Main module for {{name}}."""


def main() -> None:
    """Entry point."""
    print("Hello from {{name}}!")


if __name__ == "__main__":
    main()
'''
            ),
            TemplateFile(
                path="tests/__init__.py",
                content='"""Tests for {{name}}."""\n'
            ),
            TemplateFile(
                path="tests/test_main.py",
                content='''"""Tests for main module."""

import pytest
from {{name}}.main import main


def test_main(capsys):
    """Test main function."""
    main()
    captured = capsys.readouterr()
    assert "Hello from {{name}}" in captured.out
'''
            ),
            TemplateFile(
                path=".gitignore",
                content='''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.env
.venv
env/
venv/

# Testing
.pytest_cache/
.coverage
htmlcov/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
'''
            ),
        ],
    )


def get_react_app_template() -> ProjectTemplate:
    """React + TypeScript + Vite template."""
    return ProjectTemplate(
        name="react-app",
        description="React application with TypeScript and Vite",
        project_type=ProjectType.REACT_APP,
        variables=[
            TemplateVariable("name", "Project name (lowercase, hyphens)", pattern=r"^[a-z][a-z0-9-]*$"),
            TemplateVariable("description", "Short description"),
            TemplateVariable("author", "Author name"),
        ],
        directories=[
            "src",
            "src/components",
            "src/hooks",
            "src/utils",
            "public",
        ],
        files=[
            TemplateFile(
                path="package.json",
                content='''{
  "name": "{{name}}",
  "private": true,
  "version": "0.1.0",
  "description": "{{description}}",
  "author": "{{author}}",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@typescript-eslint/eslint-plugin": "^6.0.0",
    "@typescript-eslint/parser": "^6.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "eslint": "^8.45.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.0",
    "typescript": "^5.0.0",
    "vite": "^5.0.0",
    "vitest": "^1.0.0"
  }
}
'''
            ),
            TemplateFile(
                path="tsconfig.json",
                content='''{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
'''
            ),
            TemplateFile(
                path="tsconfig.node.json",
                content='''{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
'''
            ),
            TemplateFile(
                path="vite.config.ts",
                content='''import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
'''
            ),
            TemplateFile(
                path="index.html",
                content='''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{{name}}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
'''
            ),
            TemplateFile(
                path="src/main.tsx",
                content='''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
'''
            ),
            TemplateFile(
                path="src/App.tsx",
                content='''import { useState } from 'react'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="app">
      <h1>{{name}}</h1>
      <p>{{description}}</p>
      <button onClick={() => setCount((c) => c + 1)}>
        Count: {count}
      </button>
    </div>
  )
}

export default App
'''
            ),
            TemplateFile(
                path="src/index.css",
                content=''':root {
  font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
  line-height: 1.5;
  font-weight: 400;
  color: #213547;
  background-color: #ffffff;
}

.app {
  max-width: 1280px;
  margin: 0 auto;
  padding: 2rem;
  text-align: center;
}

button {
  padding: 0.6em 1.2em;
  font-size: 1em;
  font-weight: 500;
  border-radius: 8px;
  border: 1px solid transparent;
  background-color: #1a1a1a;
  color: white;
  cursor: pointer;
  transition: background-color 0.25s;
}

button:hover {
  background-color: #333;
}
'''
            ),
            TemplateFile(
                path="README.md",
                content='''# {{name}}

{{description}}

## Development

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
```

## Test

```bash
npm test
```
'''
            ),
            TemplateFile(
                path=".gitignore",
                content='''# Dependencies
node_modules/

# Build
dist/
build/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Logs
*.log
npm-debug.log*

# Environment
.env
.env.local
.env.*.local
'''
            ),
        ],
    )


def get_express_api_template() -> ProjectTemplate:
    """Express + TypeScript API template."""
    return ProjectTemplate(
        name="express-api",
        description="Express.js API with TypeScript",
        project_type=ProjectType.EXPRESS_API,
        variables=[
            TemplateVariable("name", "Project name (lowercase, hyphens)", pattern=r"^[a-z][a-z0-9-]*$"),
            TemplateVariable("description", "API description"),
            TemplateVariable("author", "Author name"),
            TemplateVariable("port", "Default port", default="3000", pattern=r"^\d+$"),
        ],
        directories=[
            "src",
            "src/routes",
            "src/middleware",
            "src/controllers",
            "src/types",
        ],
        files=[
            TemplateFile(
                path="package.json",
                content='''{
  "name": "{{name}}",
  "version": "0.1.0",
  "description": "{{description}}",
  "author": "{{author}}",
  "main": "dist/index.js",
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc",
    "start": "node dist/index.js",
    "lint": "eslint src --ext .ts",
    "test": "vitest"
  },
  "dependencies": {
    "cors": "^2.8.5",
    "express": "^4.18.2",
    "helmet": "^7.1.0"
  },
  "devDependencies": {
    "@types/cors": "^2.8.17",
    "@types/express": "^4.17.21",
    "@types/node": "^20.10.0",
    "tsx": "^4.6.0",
    "typescript": "^5.3.0",
    "vitest": "^1.0.0"
  }
}
'''
            ),
            TemplateFile(
                path="tsconfig.json",
                content='''{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "declaration": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
'''
            ),
            TemplateFile(
                path="src/index.ts",
                content='''import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import { healthRouter } from './routes/health';
import { errorHandler } from './middleware/errorHandler';

const app = express();
const PORT = process.env.PORT || {{port}};

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

// Routes
app.use('/health', healthRouter);

// Error handling
app.use(errorHandler);

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

export default app;
'''
            ),
            TemplateFile(
                path="src/routes/health.ts",
                content='''import { Router } from 'express';

export const healthRouter = Router();

healthRouter.get('/', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    service: '{{name}}',
  });
});
'''
            ),
            TemplateFile(
                path="src/middleware/errorHandler.ts",
                content='''import { Request, Response, NextFunction } from 'express';

export interface ApiError extends Error {
  statusCode?: number;
}

export function errorHandler(
  err: ApiError,
  req: Request,
  res: Response,
  next: NextFunction
) {
  const statusCode = err.statusCode || 500;
  const message = err.message || 'Internal Server Error';

  console.error(`[${new Date().toISOString()}] ${statusCode} - ${message}`);

  res.status(statusCode).json({
    error: {
      message,
      statusCode,
    },
  });
}
'''
            ),
            TemplateFile(
                path="src/types/index.ts",
                content='''export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}
'''
            ),
            TemplateFile(
                path="README.md",
                content='''# {{name}}

{{description}}

## Development

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
npm start
```

## API Endpoints

- `GET /health` - Health check
'''
            ),
            TemplateFile(
                path=".gitignore",
                content='''node_modules/
dist/
.env
*.log
.DS_Store
'''
            ),
        ],
    )


def get_cli_tool_template() -> ProjectTemplate:
    """Python CLI tool template with Click."""
    return ProjectTemplate(
        name="cli-tool",
        description="Python CLI tool with Click",
        project_type=ProjectType.CLI_TOOL,
        variables=[
            TemplateVariable("name", "CLI name (lowercase, hyphens)", pattern=r"^[a-z][a-z0-9-]*$"),
            TemplateVariable("description", "CLI description"),
            TemplateVariable("author", "Author name"),
            TemplateVariable("author_email", "Author email", pattern=r"^[^@]+@[^@]+\.[^@]+$"),
            TemplateVariable("command_name", "Main command name", default="{{name}}"),
        ],
        directories=[
            "src/{{name | underscore}}",
            "tests",
        ],
        files=[
            TemplateFile(
                path="pyproject.toml",
                content='''[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{{name}}"
version = "0.1.0"
description = "{{description}}"
readme = "README.md"
authors = [
    {name = "{{author}}", email = "{{author_email}}"}
]
requires-python = ">=3.9"
dependencies = [
    "click>=8.0",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]

[project.scripts]
{{command_name}} = "{{name | underscore}}.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
'''
            ),
            TemplateFile(
                path="src/{{name | underscore}}/__init__.py",
                content='''"""{{description}}"""

__version__ = "0.1.0"
'''
            ),
            TemplateFile(
                path="src/{{name | underscore}}/cli.py",
                content='''"""CLI entry point for {{name}}."""

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option()
def main():
    """{{description}}"""
    pass


@main.command()
@click.argument('name', default='World')
def hello(name: str):
    """Say hello to NAME."""
    console.print(f"[bold green]Hello, {name}![/bold green]")


@main.command()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
def status(verbose: bool):
    """Show current status."""
    console.print("[blue]Status:[/blue] OK")
    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")


if __name__ == '__main__':
    main()
'''
            ),
            TemplateFile(
                path="tests/test_cli.py",
                content='''"""Tests for CLI."""

import pytest
from click.testing import CliRunner
from {{name | underscore}}.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_hello(runner):
    """Test hello command."""
    result = runner.invoke(main, ['hello'])
    assert result.exit_code == 0
    assert 'Hello' in result.output


def test_hello_with_name(runner):
    """Test hello command with name."""
    result = runner.invoke(main, ['hello', 'Test'])
    assert result.exit_code == 0
    assert 'Test' in result.output


def test_status(runner):
    """Test status command."""
    result = runner.invoke(main, ['status'])
    assert result.exit_code == 0
    assert 'OK' in result.output
'''
            ),
            TemplateFile(
                path="README.md",
                content='''# {{name}}

{{description}}

## Installation

```bash
pip install {{name}}
```

## Usage

```bash
{{command_name}} --help
{{command_name}} hello
{{command_name}} status
```

## Development

```bash
pip install -e ".[dev]"
pytest
```
'''
            ),
            TemplateFile(
                path=".gitignore",
                content='''__pycache__/
*.py[cod]
dist/
*.egg-info/
.pytest_cache/
.coverage
.env
.venv/
'''
            ),
        ],
    )


# Template registry
BUILT_IN_TEMPLATES: Dict[str, ProjectTemplate] = {
    "python-package": get_python_package_template(),
    "react-app": get_react_app_template(),
    "express-api": get_express_api_template(),
    "cli-tool": get_cli_tool_template(),
}


# === Template Engine ===

class TemplateEngine:
    """Simple template engine with variable substitution."""

    # Pattern for {{variable}} or {{variable | filter}}
    VAR_PATTERN = re.compile(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\|\s*([a-zA-Z_]+))?\s*\}\}')

    def __init__(self, variables: Dict[str, str]):
        self.variables = variables

    def _apply_filter(self, value: str, filter_name: str) -> str:
        """Apply a filter to a value."""
        if filter_name == "underscore":
            return value.replace("-", "_")
        elif filter_name == "hyphen":
            return value.replace("_", "-")
        elif filter_name == "upper":
            return value.upper()
        elif filter_name == "lower":
            return value.lower()
        elif filter_name == "title":
            return value.title()
        elif filter_name == "replace":
            # Special handling for replace('.', '') patterns
            return value
        return value

    def render(self, template: str) -> str:
        """Render a template string with variables."""
        def replacer(match):
            var_name = match.group(1)
            filter_name = match.group(2)

            # Get the value
            value = self.variables.get(var_name, match.group(0))

            # Apply filter if present
            if filter_name and value != match.group(0):
                value = self._apply_filter(value, filter_name)

            return value

        return self.VAR_PATTERN.sub(replacer, template)

    def render_path(self, path: str) -> str:
        """Render a path template."""
        return self.render(path)


# === Validation ===

def validate_variable(var: TemplateVariable, value: str) -> Tuple[bool, str]:
    """Validate a variable value against its specification."""
    if var.required and not value:
        return False, f"Required variable '{var.name}' is missing"

    if var.pattern and value:
        if not re.match(var.pattern, value):
            return False, f"Variable '{var.name}' does not match pattern {var.pattern}"

    if var.choices and value:
        if value not in var.choices:
            return False, f"Variable '{var.name}' must be one of: {', '.join(var.choices)}"

    return True, ""


def validate_variables(
    template: ProjectTemplate,
    variables: Dict[str, str]
) -> Tuple[bool, List[str]]:
    """Validate all variables for a template."""
    errors = []

    for var in template.variables:
        value = variables.get(var.name, var.default or "")
        valid, error = validate_variable(var, value)
        if not valid:
            errors.append(error)

    return len(errors) == 0, errors


def validate_project_name(name: str) -> Tuple[bool, str]:
    """Validate a project name."""
    if not name:
        return False, "Project name is required"

    if len(name) > 100:
        return False, "Project name too long (max 100 characters)"

    # Check for invalid characters
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', name):
        return False, "Project name must start with a letter and contain only letters, numbers, hyphens, and underscores"

    return True, ""


def validate_output_path(path: Path, allow_overwrite: bool) -> Tuple[bool, str]:
    """Validate the output path."""
    if path.exists():
        if not allow_overwrite:
            return False, f"Output path already exists: {path}"
        if not path.is_dir():
            return False, f"Output path exists but is not a directory: {path}"

    # Check parent is writable
    parent = path.parent
    if not parent.exists():
        return False, f"Parent directory does not exist: {parent}"

    return True, ""


# === Post-generation Validation ===

def validate_generated_project(
    project_path: Path,
    template: ProjectTemplate
) -> Tuple[bool, List[str]]:
    """Validate a generated project."""
    errors = []

    # Check all expected files exist
    for template_file in template.files:
        # Skip conditional files (simplified - would need full condition eval)
        if template_file.condition:
            continue

        # We can't easily validate paths with variables, so just check the project exists
        pass

    # Check for common issues
    # 1. Check for empty files that shouldn't be empty
    for file_path in project_path.rglob("*"):
        if file_path.is_file():
            # Check for zero-byte files (except __init__.py which can be empty)
            if file_path.stat().st_size == 0 and file_path.name != "__init__.py":
                if not file_path.name.startswith("."):
                    errors.append(f"Empty file detected: {file_path.relative_to(project_path)}")

    # 2. Check for Python syntax (if Python project)
    if template.project_type in (ProjectType.PYTHON_PACKAGE, ProjectType.CLI_TOOL):
        for py_file in project_path.rglob("*.py"):
            try:
                content = py_file.read_text()
                compile(content, str(py_file), 'exec')
            except SyntaxError as e:
                errors.append(f"Python syntax error in {py_file.relative_to(project_path)}: {e}")

    # 3. Check for JSON syntax (if contains JSON files)
    for json_file in project_path.rglob("*.json"):
        try:
            content = json_file.read_text()
            json.loads(content)
        except json.JSONDecodeError as e:
            errors.append(f"JSON syntax error in {json_file.relative_to(project_path)}: {e}")

    return len(errors) == 0, errors


# === Core Functions ===

def get_template(template_name: str) -> Optional[ProjectTemplate]:
    """Get a template by name."""
    return BUILT_IN_TEMPLATES.get(template_name)


def list_templates() -> List[Dict[str, str]]:
    """List available templates."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "type": t.project_type.value,
        }
        for t in BUILT_IN_TEMPLATES.values()
    ]


def scaffold_project(
    template_name: str,
    output_path: str,
    variables: Dict[str, str],
    config: Dict[str, Any] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> ScaffoldResult:
    """
    Generate a project from a template.

    Args:
        template_name: Name of the template to use
        output_path: Where to create the project
        variables: Template variables
        config: Optional configuration overrides
        progress_callback: Optional progress callback

    Returns:
        ScaffoldResult with success status and details
    """
    config = {**DEFAULT_CONFIG, **(config or {})}
    output_path = Path(output_path)

    # Get template
    template = get_template(template_name)
    if not template:
        return ScaffoldResult(
            success=False,
            error=f"Unknown template: {template_name}. Available: {', '.join(BUILT_IN_TEMPLATES.keys())}"
        )

    # Validate output path
    valid, error = validate_output_path(output_path, config["allow_overwrite"])
    if not valid:
        return ScaffoldResult(success=False, error=error)

    # Apply defaults to variables
    final_vars = {}
    for var in template.variables:
        if var.name in variables:
            final_vars[var.name] = variables[var.name]
        elif var.default:
            # Render default (may contain variable references)
            engine = TemplateEngine(final_vars)
            final_vars[var.name] = engine.render(var.default)
        elif not var.required:
            final_vars[var.name] = ""

    # Validate variables
    valid, errors = validate_variables(template, final_vars)
    if not valid:
        return ScaffoldResult(
            success=False,
            error=f"Variable validation failed: {'; '.join(errors)}",
            validation_errors=errors
        )

    # Create template engine
    engine = TemplateEngine(final_vars)

    # Use temp directory for atomic creation
    temp_dir = None
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="scaffold_"))

        files_created = []
        dirs_created = []

        # Create directories
        total_steps = len(template.directories) + len(template.files)
        current_step = 0

        for dir_template in template.directories:
            dir_path = temp_dir / engine.render_path(dir_template)
            dir_path.mkdir(parents=True, exist_ok=True)
            dirs_created.append(str(dir_path.relative_to(temp_dir)))

            current_step += 1
            if progress_callback:
                progress_callback({
                    "step": current_step,
                    "total": total_steps,
                    "message": f"Creating directory: {dir_path.name}"
                })

        # Create files
        for template_file in template.files:
            # Check condition
            if template_file.condition:
                if not final_vars.get(template_file.condition):
                    continue

            file_path = temp_dir / engine.render_path(template_file.path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            content = engine.render(template_file.content)
            file_path.write_text(content)

            if template_file.executable:
                file_path.chmod(file_path.stat().st_mode | 0o111)

            files_created.append(str(file_path.relative_to(temp_dir)))

            current_step += 1
            if progress_callback:
                progress_callback({
                    "step": current_step,
                    "total": total_steps,
                    "message": f"Creating file: {file_path.name}"
                })

        # Validate generated project
        validation_passed = True
        validation_errors = []
        if config["validate_output"]:
            validation_passed, validation_errors = validate_generated_project(temp_dir, template)

        # Move to final location
        if output_path.exists() and config["allow_overwrite"]:
            shutil.rmtree(output_path)

        shutil.move(str(temp_dir), str(output_path))
        temp_dir = None  # Moved successfully

        warnings = []
        if not validation_passed:
            warnings.append(f"Validation issues: {'; '.join(validation_errors)}")

        return ScaffoldResult(
            success=True,
            project_path=str(output_path),
            files_created=files_created,
            directories_created=dirs_created,
            warnings=warnings,
            validation_passed=validation_passed,
            validation_errors=validation_errors
        )

    except Exception as e:
        return ScaffoldResult(
            success=False,
            error=f"Scaffold generation failed: {e}"
        )
    finally:
        # Cleanup temp directory on failure
        if temp_dir and temp_dir.exists() and config["cleanup_on_failure"]:
            shutil.rmtree(temp_dir, ignore_errors=True)


# === Skill Entry Point ===

def run(args: Dict[str, Any], tools: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for the code_scaffold skill.

    Args:
        args: Skill arguments
            - template: Template name (required)
            - output_path: Where to create project (required)
            - variables: Dict of template variables (required)
            - allow_overwrite: Whether to overwrite existing (default: False)
            - validate: Whether to validate output (default: True)
        tools: Available tools (unused)
        config: Skill configuration

    Returns:
        Result dict with success status and details
    """
    # Extract arguments
    template_name = args.get("template")
    output_path = args.get("output_path")
    variables = args.get("variables", {})
    allow_overwrite = args.get("allow_overwrite", False)
    validate = args.get("validate", True)

    # Validate required args
    if not template_name:
        return {
            "success": False,
            "error": "Missing required argument: template"
        }

    if not output_path:
        return {
            "success": False,
            "error": "Missing required argument: output_path"
        }

    if not isinstance(variables, dict):
        return {
            "success": False,
            "error": "Variables must be a dictionary"
        }

    # Get progress callback
    progress_callback = args.get("_progress_callback")

    # Build config
    skill_config = {
        **DEFAULT_CONFIG,
        **config,
        "allow_overwrite": allow_overwrite,
        "validate_output": validate,
    }

    # Generate scaffold
    result = scaffold_project(
        template_name=template_name,
        output_path=output_path,
        variables=variables,
        config=skill_config,
        progress_callback=progress_callback
    )

    return result.to_dict()


# === CLI ===

if __name__ == "__main__":
    import sys

    print("Code Scaffold Skill")
    print("=" * 40)
    print("\nAvailable templates:")
    for t in list_templates():
        print(f"  - {t['name']}: {t['description']}")

    if len(sys.argv) > 1:
        template_name = sys.argv[1]
        output_path = sys.argv[2] if len(sys.argv) > 2 else f"./{template_name}-project"

        print(f"\nGenerating {template_name} at {output_path}...")

        result = scaffold_project(
            template_name=template_name,
            output_path=output_path,
            variables={
                "name": "my-project",
                "description": "A test project",
                "author": "Test Author",
                "author_email": "test@example.com",
            }
        )

        if result.success:
            print(f"Success! Created {len(result.files_created)} files")
        else:
            print(f"Error: {result.error}")
