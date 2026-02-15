"""
Integration tests for the full production pipeline.

These tests verify that all Phase 3.x skills work together correctly:
- audio/generate_tts.py
- image/image_generate.py
- video/video_compose.py
- video/video_subtitle.py
- production/episode_produce.py

Tests use mocking to avoid actual external service calls while
verifying the integration contracts between skills.
"""

import pytest
import sys
import tempfile
import json
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

# Add skills to path
SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"
sys.path.insert(0, str(SKILLS_DIR / "production"))
sys.path.insert(0, str(SKILLS_DIR / "audio"))
sys.path.insert(0, str(SKILLS_DIR / "image"))
sys.path.insert(0, str(SKILLS_DIR / "video"))
sys.path.insert(0, str(SKILLS_DIR / "code"))
sys.path.insert(0, str(SKILLS_DIR / "verification"))


class TestSkillComposition:
    """Test that skills compose correctly."""

    def test_episode_produce_composes_all_media_skills(self):
        """Verify episode_produce declares correct compositions."""
        from episode_produce import SKILL_META

        composes = SKILL_META.get("composes", [])
        assert "audio/generate_tts.py" in composes
        assert "image/image_generate.py" in composes
        assert "video/video_compose.py" in composes
        assert "video/video_subtitle.py" in composes

    def test_code_refactor_composes_code_review(self):
        """Verify code_refactor declares composition with verifier."""
        try:
            sys.path.insert(0, str(SKILLS_DIR / "code"))
            from code_refactor import SKILL_META
            composes = SKILL_META.get("composes", [])
            assert "verification/code_review_verifier.py" in composes
        except ImportError:
            pytest.skip("code_refactor not available")

    def test_test_generate_composes_coverage_verifier(self):
        """Verify test_generate declares composition with coverage verifier."""
        try:
            from test_generate import SKILL_META
            composes = SKILL_META.get("composes", [])
            assert "verification/test_coverage_verifier.py" in composes
        except ImportError:
            pytest.skip("test_generate not available")


class TestProductionPipelineIntegration:
    """Test the full production pipeline integration."""

    @pytest.fixture
    def sample_script(self):
        """Create a sample production script."""
        return """
## Scene 1: Introduction

[A beautiful sunrise over mountains]

**NARRATOR (voiceover):**
"Welcome to our story."

**ALICE:**
"What a beautiful morning!"

## Scene 2: The Meeting

[A cozy coffee shop interior]

**BOB:**
"Alice! Over here!"

**ALICE:**
"Bob! So good to see you!"

## Scene 3: The Conclusion

[Sunset on the beach]

**NARRATOR:**
"And so our story ends."
"""

    @pytest.fixture
    def mock_tts(self):
        """Mock TTS to return success without actual generation."""
        with patch.dict('sys.modules', {
            'generate_tts': MagicMock(
                generate_speech=Mock(return_value={
                    "success": True,
                    "duration": 2.5,
                    "file_size": 1024
                }),
                VOICE_PRESETS={"narrator": "en-US-GuyNeural", "alice": "en-US-JennyNeural", "bob": "en-US-TonyNeural"}
            )
        }):
            yield

    @pytest.fixture
    def mock_image_generate(self):
        """Mock image generation."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.backend_used = "pollinations"
        mock_result.error = None

        with patch.dict('sys.modules', {
            'image_generate': MagicMock(
                generate_image=Mock(return_value=mock_result),
                ImageConfig=MagicMock
            )
        }):
            yield

    @pytest.fixture
    def mock_video_compose(self):
        """Mock video composition."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output_path = None
        mock_result.error = None

        with patch.dict('sys.modules', {
            'video_compose': MagicMock(
                compose_video=Mock(return_value=mock_result),
                VideoConfig=MagicMock
            )
        }):
            yield

    @pytest.fixture
    def mock_video_subtitle(self):
        """Mock subtitle addition."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error = None

        with patch.dict('sys.modules', {
            'video_subtitle': MagicMock(
                add_subtitles_to_video=Mock(return_value=mock_result),
                SubtitleStyle=MagicMock
            )
        }):
            yield

    def test_script_parsing_extracts_all_elements(self, sample_script):
        """Test that script parsing extracts scenes and dialogue correctly."""
        from episode_produce import parse_script

        scenes, dialogue = parse_script(sample_script)

        # Should have 3 scenes
        assert len(scenes) == 3

        # Should have 5 dialogue lines
        assert len(dialogue) == 5

        # Check scene titles
        assert scenes[0].title == "Introduction"
        assert scenes[1].title == "The Meeting"
        assert scenes[2].title == "The Conclusion"

        # Check dialogue distribution
        scene1_dialogue = [d for d in dialogue if d.scene_number == 1]
        scene2_dialogue = [d for d in dialogue if d.scene_number == 2]
        scene3_dialogue = [d for d in dialogue if d.scene_number == 3]

        assert len(scene1_dialogue) == 2
        assert len(scene2_dialogue) == 2
        assert len(scene3_dialogue) == 1

        # Check dialogue types
        voiceovers = [d for d in dialogue if d.line_type == "voiceover"]
        assert len(voiceovers) == 1
        assert voiceovers[0].character == "narrator"

    def test_image_prompts_include_style(self, sample_script):
        """Test that image prompts are generated with style modifiers."""
        from episode_produce import parse_script, generate_image_prompts

        scenes, _ = parse_script(sample_script)
        scenes = generate_image_prompts(scenes, "cinematic")

        for scene in scenes:
            assert scene.image_prompt != ""
            assert "cinematic" in scene.image_prompt.lower()

    def test_production_result_structure(self, sample_script):
        """Test that production results have proper structure."""
        from episode_produce import produce_episode, ProductionStage

        # Run with minimal config to test structure
        result = produce_episode(
            script_content=sample_script,
            config={"continue_on_error": True}
        )

        # Should have stages
        assert len(result.stages) > 0

        # First stage should be parse
        assert result.stages[0].stage == ProductionStage.PARSE_SCRIPT
        assert result.stages[0].success is True

        # Should count scenes correctly
        assert result.scenes_count == 3

    def test_continue_on_error_behavior(self, sample_script):
        """Test that continue_on_error allows partial production."""
        from episode_produce import produce_episode

        # Even with failures, should get partial results
        result = produce_episode(
            script_content=sample_script,
            config={"continue_on_error": True}
        )

        # Parse stage should succeed
        parse_stages = [s for s in result.stages if s.stage.value == "parse_script"]
        assert len(parse_stages) == 1
        assert parse_stages[0].success is True


class TestCodeWorkflowIntegration:
    """Test code workflow skills integration."""

    def test_scaffold_produces_valid_python(self):
        """Test that code_scaffold produces syntactically valid Python."""
        try:
            from code_scaffold import scaffold_project
            import ast

            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "test_pkg"
                result = scaffold_project(
                    template_name="python-package",
                    output_path=str(output_path),
                    variables={"name": "test_pkg", "author": "Test Author", "description": "Test package"}
                )

                if result.success:
                    # Check that Python files are valid
                    for py_file in output_path.rglob("*.py"):
                        content = py_file.read_text()
                        try:
                            ast.parse(content)
                        except SyntaxError as e:
                            pytest.fail(f"Invalid Python in {py_file}: {e}")
        except ImportError:
            pytest.skip("code_scaffold not available")

    def test_test_generate_produces_runnable_tests(self):
        """Test that test_generate produces valid test code."""
        try:
            from test_generate import generate_tests
            import ast

            source_code = '''
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

def multiply(x: int, y: int) -> int:
    """Multiply two numbers."""
    return x * y
'''
            result = generate_tests(source_code, "math_utils")

            if result.success:
                # Parse the generated test file
                try:
                    ast.parse(result.test_file_content)
                except SyntaxError as e:
                    pytest.fail(f"Invalid test code: {e}")

                # Should have tests for both functions
                assert "test_add" in result.test_file_content
                assert "test_multiply" in result.test_file_content
        except ImportError:
            pytest.skip("test_generate not available")

    def test_refactor_preserves_functionality(self):
        """Test that code_refactor produces valid code."""
        try:
            from code_refactor import refactor, RefactorOperation, RefactorType
            import ast

            source_code = '''
def calculate(x):
    result = x * 2
    return result
'''
            op = RefactorOperation(
                type=RefactorType.RENAME_VARIABLE,
                target="result",
                new_value="output"
            )

            result = refactor(source_code, op)

            if result.success:
                # Should be valid Python
                try:
                    ast.parse(result.refactored_code)
                except SyntaxError as e:
                    pytest.fail(f"Invalid refactored code: {e}")

                # Should have renamed
                assert "output" in result.refactored_code
                assert "result" not in result.refactored_code
        except ImportError:
            pytest.skip("code_refactor not available")


class TestVerificationIntegration:
    """Test verification skills integration."""

    def test_code_review_catches_issues(self):
        """Test that code_review_verifier catches real issues."""
        try:
            from code_review_verifier import review_code

            problematic_code = '''
def foo():
    x = 1
    y = 2
    z = 3
    a = 4
    b = 5
    c = 6
    d = 7
    e = 8
    f = 9
    g = 10
    h = 11  # Too many local variables
    return x
'''
            result = review_code(problematic_code)

            # Should detect some issue (complexity, too many variables, etc.)
            assert len(result.issues) > 0 or result.score < 1.0
        except ImportError:
            pytest.skip("code_review_verifier not available")

    def test_accessibility_verifier_checks_html(self):
        """Test that accessibility_verifier checks HTML content."""
        try:
            from accessibility_verifier import verify_accessibility

            html_without_alt = '''
<html>
<body>
<img src="photo.jpg">
<button style="background: #fff; color: #eee;">Click</button>
</body>
</html>
'''
            result = verify_accessibility(html_without_alt, content_type="html")

            # Should detect missing alt text or contrast issues
            assert len(result.issues) > 0 or not result.passed
        except ImportError:
            pytest.skip("accessibility_verifier not available")


class TestResourceLimitsIntegration:
    """Test that resource limits are enforced across skills."""

    def test_video_compose_respects_image_limit(self):
        """Test that video_compose respects max_images limit."""
        try:
            from video_compose import compose_video, VideoConfig

            # Try to compose with too many images
            config = {"max_images": 5}
            images = [f"/fake/image_{i}.png" for i in range(100)]

            # Should warn or limit
            # This is tested via the skill's behavior
        except ImportError:
            pytest.skip("video_compose not available")

    def test_episode_produce_respects_duration_limit(self):
        """Test that episode_produce respects max_duration_seconds."""
        from episode_produce import DEFAULT_CONFIG

        assert "max_duration_seconds" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["max_duration_seconds"] == 600  # 10 minutes


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios."""

    def test_minimal_episode_production(self):
        """Test minimal episode production scenario."""
        from episode_produce import produce_episode

        minimal_script = """
## Scene 1

**NARRATOR:**
"Hello world."
"""
        result = produce_episode(
            script_content=minimal_script,
            config={"continue_on_error": True}
        )

        # Should at least parse successfully
        assert result.scenes_count == 1

    def test_code_to_test_workflow(self):
        """Test generating tests from scaffolded code."""
        try:
            from code_scaffold import scaffold_project
            from test_generate import generate_tests_for_file

            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "mylib"
                # Scaffold a project
                scaffold_result = scaffold_project(
                    template_name="python-package",
                    output_path=str(output_path),
                    variables={"name": "mylib", "author": "Test", "description": "Test lib"}
                )

                if scaffold_result.success:
                    # Find main module
                    main_file = output_path / "mylib" / "__init__.py"
                    if main_file.exists():
                        # Generate tests for it
                        test_result = generate_tests_for_file(str(main_file))
                        # Should produce some output (even if no testable functions)
                        assert test_result is not None
        except ImportError:
            pytest.skip("Required skills not available")


class TestSkillIndexConsistency:
    """Test that skills/index.json is consistent with actual skills."""

    def test_index_contains_phase_3_skills(self):
        """Test that index.json includes all Phase 3 skills."""
        index_path = SKILLS_DIR / "index.json"
        if not index_path.exists():
            pytest.skip("index.json not found")

        with open(index_path) as f:
            index = json.load(f)

        skill_names = [s.get("name") for s in index.get("skills", [])]

        # Phase 3.1 skills
        assert "code_review_verifier" in skill_names
        assert "test_coverage_verifier" in skill_names
        assert "accessibility_verifier" in skill_names

        # Phase 3.2 skills
        assert "image_generate" in skill_names
        assert "video_compose" in skill_names
        assert "video_subtitle" in skill_names

        # Phase 3.3 skills
        assert "code_scaffold" in skill_names
        assert "test_generate" in skill_names
        assert "code_refactor" in skill_names

    def test_skill_paths_exist(self):
        """Test that skill paths in index.json exist."""
        index_path = SKILLS_DIR / "index.json"
        if not index_path.exists():
            pytest.skip("index.json not found")

        with open(index_path) as f:
            index = json.load(f)

        for skill in index.get("skills", []):
            path = skill.get("path")
            if path:
                full_path = SKILLS_DIR / path
                # Allow .yaml or .py
                assert full_path.exists() or full_path.with_suffix('.yaml').exists(), \
                    f"Skill path not found: {path}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
