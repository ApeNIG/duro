"""
Tests for code_scaffold skill.

Tests cover:
- Template listing and retrieval
- Variable validation
- Path validation
- Template rendering
- Project generation
- Post-generation validation
- Error handling
- Run function
"""

import pytest
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Add skills to path
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "code"))

from code_scaffold import (
    run,
    ProjectType,
    License,
    TemplateVariable,
    TemplateFile,
    ProjectTemplate,
    ScaffoldResult,
    TemplateEngine,
    get_template,
    list_templates,
    scaffold_project,
    validate_variable,
    validate_variables,
    validate_project_name,
    validate_output_path,
    validate_generated_project,
    BUILT_IN_TEMPLATES,
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
        assert SKILL_META["name"] == "code_scaffold"

    def test_has_composes(self):
        assert "composes" in SKILL_META
        assert "meta/adversarial_planning.py" in SKILL_META["composes"]


class TestTemplateEngine:
    """Test template engine."""

    def test_simple_variable(self):
        engine = TemplateEngine({"name": "myproject"})
        result = engine.render("Hello {{name}}")
        assert result == "Hello myproject"

    def test_multiple_variables(self):
        engine = TemplateEngine({"name": "myproject", "author": "John"})
        result = engine.render("{{name}} by {{author}}")
        assert result == "myproject by John"

    def test_underscore_filter(self):
        engine = TemplateEngine({"name": "my-project"})
        result = engine.render("{{name | underscore}}")
        assert result == "my_project"

    def test_hyphen_filter(self):
        engine = TemplateEngine({"name": "my_project"})
        result = engine.render("{{name | hyphen}}")
        assert result == "my-project"

    def test_upper_filter(self):
        engine = TemplateEngine({"name": "myproject"})
        result = engine.render("{{name | upper}}")
        assert result == "MYPROJECT"

    def test_lower_filter(self):
        engine = TemplateEngine({"name": "MyProject"})
        result = engine.render("{{name | lower}}")
        assert result == "myproject"

    def test_unknown_variable_unchanged(self):
        engine = TemplateEngine({"name": "test"})
        result = engine.render("Hello {{unknown}}")
        assert result == "Hello {{unknown}}"

    def test_render_path(self):
        engine = TemplateEngine({"name": "myproject"})
        result = engine.render_path("src/{{name}}/main.py")
        assert result == "src/myproject/main.py"


class TestVariableValidation:
    """Test variable validation."""

    def test_required_variable_missing(self):
        var = TemplateVariable("name", "Name", required=True)
        valid, error = validate_variable(var, "")
        assert valid is False
        assert "missing" in error.lower()

    def test_required_variable_present(self):
        var = TemplateVariable("name", "Name", required=True)
        valid, error = validate_variable(var, "myproject")
        assert valid is True

    def test_pattern_match(self):
        var = TemplateVariable("name", "Name", pattern=r"^[a-z]+$")
        valid, error = validate_variable(var, "myproject")
        assert valid is True

    def test_pattern_mismatch(self):
        var = TemplateVariable("name", "Name", pattern=r"^[a-z]+$")
        valid, error = validate_variable(var, "MyProject")
        assert valid is False
        assert "pattern" in error.lower()

    def test_choices_valid(self):
        var = TemplateVariable("license", "License", choices=["MIT", "Apache"])
        valid, error = validate_variable(var, "MIT")
        assert valid is True

    def test_choices_invalid(self):
        var = TemplateVariable("license", "License", choices=["MIT", "Apache"])
        valid, error = validate_variable(var, "GPL")
        assert valid is False
        assert "must be one of" in error.lower()

    def test_optional_variable_empty(self):
        var = TemplateVariable("optional", "Optional", required=False)
        valid, error = validate_variable(var, "")
        assert valid is True


class TestProjectNameValidation:
    """Test project name validation."""

    def test_valid_name(self):
        valid, error = validate_project_name("my-project")
        assert valid is True

    def test_empty_name(self):
        valid, error = validate_project_name("")
        assert valid is False
        assert "required" in error.lower()

    def test_name_too_long(self):
        valid, error = validate_project_name("a" * 101)
        assert valid is False
        assert "too long" in error.lower()

    def test_name_starts_with_number(self):
        valid, error = validate_project_name("123project")
        assert valid is False

    def test_name_with_spaces(self):
        valid, error = validate_project_name("my project")
        assert valid is False


class TestOutputPathValidation:
    """Test output path validation."""

    def test_valid_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "new_project"
            valid, error = validate_output_path(path, False)
            assert valid is True

    def test_path_exists_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            valid, error = validate_output_path(path, False)
            assert valid is False
            assert "already exists" in error.lower()

    def test_path_exists_with_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            valid, error = validate_output_path(path, True)
            assert valid is True

    def test_parent_not_exists(self):
        path = Path("/nonexistent/path/project")
        valid, error = validate_output_path(path, False)
        assert valid is False
        assert "parent" in error.lower()


class TestTemplateRetrieval:
    """Test template listing and retrieval."""

    def test_list_templates(self):
        templates = list_templates()
        assert len(templates) >= 4
        names = [t["name"] for t in templates]
        assert "python-package" in names
        assert "react-app" in names
        assert "express-api" in names
        assert "cli-tool" in names

    def test_get_python_template(self):
        template = get_template("python-package")
        assert template is not None
        assert template.name == "python-package"
        assert template.project_type == ProjectType.PYTHON_PACKAGE

    def test_get_react_template(self):
        template = get_template("react-app")
        assert template is not None
        assert template.project_type == ProjectType.REACT_APP

    def test_get_express_template(self):
        template = get_template("express-api")
        assert template is not None
        assert template.project_type == ProjectType.EXPRESS_API

    def test_get_cli_template(self):
        template = get_template("cli-tool")
        assert template is not None
        assert template.project_type == ProjectType.CLI_TOOL

    def test_get_unknown_template(self):
        template = get_template("nonexistent")
        assert template is None


class TestScaffoldResult:
    """Test ScaffoldResult dataclass."""

    def test_success_result(self):
        result = ScaffoldResult(
            success=True,
            project_path="/path/to/project",
            files_created=["main.py", "test.py"]
        )
        assert result.success is True
        assert len(result.files_created) == 2

    def test_to_dict(self):
        result = ScaffoldResult(
            success=True,
            project_path="/path",
            files_created=["a.py"],
            directories_created=["src"]
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["project_path"] == "/path"
        assert "a.py" in d["files_created"]


class TestScaffoldGeneration:
    """Test project scaffold generation."""

    def test_python_package_scaffold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_package"

            result = scaffold_project(
                template_name="python-package",
                output_path=str(output_path),
                variables={
                    "name": "test_package",
                    "description": "A test package",
                    "author": "Test Author",
                    "author_email": "test@example.com",
                }
            )

            assert result.success is True
            assert output_path.exists()
            assert (output_path / "pyproject.toml").exists()
            assert (output_path / "src" / "test_package" / "__init__.py").exists()
            assert (output_path / "tests" / "test_main.py").exists()

    def test_react_app_scaffold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test-app"

            result = scaffold_project(
                template_name="react-app",
                output_path=str(output_path),
                variables={
                    "name": "test-app",
                    "description": "A test app",
                    "author": "Test Author",
                }
            )

            assert result.success is True
            assert (output_path / "package.json").exists()
            assert (output_path / "src" / "App.tsx").exists()
            assert (output_path / "tsconfig.json").exists()

    def test_express_api_scaffold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test-api"

            result = scaffold_project(
                template_name="express-api",
                output_path=str(output_path),
                variables={
                    "name": "test-api",
                    "description": "A test API",
                    "author": "Test Author",
                }
            )

            assert result.success is True
            assert (output_path / "package.json").exists()
            assert (output_path / "src" / "index.ts").exists()
            assert (output_path / "src" / "routes" / "health.ts").exists()

    def test_cli_tool_scaffold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test-cli"

            result = scaffold_project(
                template_name="cli-tool",
                output_path=str(output_path),
                variables={
                    "name": "test-cli",
                    "description": "A test CLI",
                    "author": "Test Author",
                    "author_email": "test@example.com",
                }
            )

            assert result.success is True
            assert (output_path / "pyproject.toml").exists()
            assert (output_path / "src" / "test_cli" / "cli.py").exists()

    def test_unknown_template_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scaffold_project(
                template_name="unknown-template",
                output_path=str(Path(tmpdir) / "project"),
                variables={}
            )

            assert result.success is False
            assert "unknown template" in result.error.lower()

    def test_validation_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scaffold_project(
                template_name="python-package",
                output_path=str(Path(tmpdir) / "project"),
                variables={
                    "name": "InvalidName",  # Doesn't match pattern
                    "description": "Test",
                    "author": "Test",
                    "author_email": "invalid-email",  # Doesn't match pattern
                }
            )

            assert result.success is False
            assert "validation" in result.error.lower()

    def test_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "existing"
            output_path.mkdir()
            (output_path / "file.txt").write_text("existing")

            result = scaffold_project(
                template_name="python-package",
                output_path=str(output_path),
                variables={
                    "name": "test_package",
                    "description": "Test",
                    "author": "Test",
                    "author_email": "test@example.com",
                },
                config={"allow_overwrite": False}
            )

            assert result.success is False
            assert "already exists" in result.error.lower()

    def test_overwrite_allowed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "existing"
            output_path.mkdir()
            (output_path / "file.txt").write_text("existing")

            result = scaffold_project(
                template_name="python-package",
                output_path=str(output_path),
                variables={
                    "name": "test_package",
                    "description": "Test",
                    "author": "Test",
                    "author_email": "test@example.com",
                },
                config={"allow_overwrite": True}
            )

            assert result.success is True
            # Old file should be gone
            assert not (output_path / "file.txt").exists()

    def test_progress_callback(self):
        progress_updates = []

        def callback(update):
            progress_updates.append(update)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = scaffold_project(
                template_name="python-package",
                output_path=str(Path(tmpdir) / "project"),
                variables={
                    "name": "test_package",
                    "description": "Test",
                    "author": "Test",
                    "author_email": "test@example.com",
                },
                progress_callback=callback
            )

            assert result.success is True
            assert len(progress_updates) > 0
            assert all("step" in u for u in progress_updates)


class TestPostGenerationValidation:
    """Test post-generation validation."""

    def test_python_syntax_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "project"

            result = scaffold_project(
                template_name="python-package",
                output_path=str(output_path),
                variables={
                    "name": "test_package",
                    "description": "Test",
                    "author": "Test",
                    "author_email": "test@example.com",
                }
            )

            assert result.success is True
            assert result.validation_passed is True

    def test_json_syntax_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "project"

            result = scaffold_project(
                template_name="react-app",
                output_path=str(output_path),
                variables={
                    "name": "test-app",
                    "description": "Test",
                    "author": "Test",
                }
            )

            assert result.success is True
            # Verify JSON is valid
            package_json = output_path / "package.json"
            content = package_json.read_text()
            parsed = json.loads(content)
            assert parsed["name"] == "test-app"


class TestRunFunction:
    """Test the main run() function."""

    def test_missing_template(self):
        result = run(
            {"output_path": "/tmp/project", "variables": {}},
            {},
            {}
        )
        assert result["success"] is False
        assert "template" in result["error"].lower()

    def test_missing_output_path(self):
        result = run(
            {"template": "python-package", "variables": {}},
            {},
            {}
        )
        assert result["success"] is False
        assert "output_path" in result["error"].lower()

    def test_invalid_variables_type(self):
        result = run(
            {
                "template": "python-package",
                "output_path": "/tmp/project",
                "variables": "not-a-dict"
            },
            {},
            {}
        )
        assert result["success"] is False
        assert "dictionary" in result["error"].lower()

    def test_successful_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run(
                {
                    "template": "python-package",
                    "output_path": str(Path(tmpdir) / "project"),
                    "variables": {
                        "name": "test_package",
                        "description": "Test",
                        "author": "Test",
                        "author_email": "test@example.com",
                    }
                },
                {},
                {}
            )

            assert result["success"] is True
            assert result["project_path"] is not None

    def test_run_with_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "project"
            output_path.mkdir()

            result = run(
                {
                    "template": "python-package",
                    "output_path": str(output_path),
                    "variables": {
                        "name": "test_package",
                        "description": "Test",
                        "author": "Test",
                        "author_email": "test@example.com",
                    },
                    "allow_overwrite": True
                },
                {},
                {}
            )

            assert result["success"] is True


class TestTemplateContent:
    """Test that template content is correctly rendered."""

    def test_python_package_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "mypackage"

            scaffold_project(
                template_name="python-package",
                output_path=str(output_path),
                variables={
                    "name": "mypackage",
                    "description": "My test package",
                    "author": "John Doe",
                    "author_email": "john@example.com",
                    "license": "MIT",
                }
            )

            # Check pyproject.toml content
            pyproject = (output_path / "pyproject.toml").read_text()
            assert 'name = "mypackage"' in pyproject
            assert 'description = "My test package"' in pyproject
            assert "John Doe" in pyproject

            # Check __init__.py content
            init_py = (output_path / "src" / "mypackage" / "__init__.py").read_text()
            assert "My test package" in init_py

    def test_cli_tool_underscore_conversion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "my-cli"

            result = scaffold_project(
                template_name="cli-tool",
                output_path=str(output_path),
                variables={
                    "name": "my-cli",
                    "description": "My CLI tool",
                    "author": "John",
                    "author_email": "john@example.com",
                }
            )

            assert result.success is True
            # Package name should use underscores
            assert (output_path / "src" / "my_cli" / "cli.py").exists()

            # Check import in test file uses underscore
            test_content = (output_path / "tests" / "test_cli.py").read_text()
            assert "from my_cli.cli import main" in test_content


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_variables_with_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # python_version has default, should work
            result = scaffold_project(
                template_name="python-package",
                output_path=str(Path(tmpdir) / "project"),
                variables={
                    "name": "test_pkg",
                    "description": "Test",
                    "author": "Test",
                    "author_email": "test@example.com",
                    # license and python_version have defaults
                }
            )

            assert result.success is True

    def test_special_characters_in_description(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scaffold_project(
                template_name="python-package",
                output_path=str(Path(tmpdir) / "project"),
                variables={
                    "name": "test_pkg",
                    "description": "A package with 'quotes' and \"double quotes\"",
                    "author": "Test",
                    "author_email": "test@example.com",
                }
            )

            assert result.success is True

    def test_cleanup_on_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Force a failure by using invalid parent path
            result = scaffold_project(
                template_name="python-package",
                output_path="/nonexistent/path/project",
                variables={
                    "name": "test_pkg",
                    "description": "Test",
                    "author": "Test",
                    "author_email": "test@example.com",
                }
            )

            assert result.success is False
            # Should not leave temp files

    def test_files_created_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scaffold_project(
                template_name="python-package",
                output_path=str(Path(tmpdir) / "project"),
                variables={
                    "name": "test_pkg",
                    "description": "Test",
                    "author": "Test",
                    "author_email": "test@example.com",
                }
            )

            assert result.success is True
            assert len(result.files_created) > 0
            assert "pyproject.toml" in result.files_created
            assert any("__init__.py" in f for f in result.files_created)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
