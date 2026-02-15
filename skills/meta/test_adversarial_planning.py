"""
Test: adversarial_planning skill
Run: python test_adversarial_planning.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adversarial_planning import (
    run,
    architect_phase,
    critic_phase,
    integrator_phase,
    generate_planning_prompt,
    CritiqueCategory,
    RiskLevel,
    DEFAULT_CRITIQUE_QUESTIONS,
    PROJECT_CRITIQUE_WEIGHTS,
    ArchitectPlan,
    CriticReport,
    Critique,
)


def test_skill_metadata():
    """Test skill metadata is properly defined."""
    from adversarial_planning import SKILL_META, REQUIRES

    assert SKILL_META["name"] == "adversarial_planning"
    assert SKILL_META["tier"] == "core"
    assert "origin" in SKILL_META
    assert len(REQUIRES) > 0
    print("PASS: test_skill_metadata")


def test_critique_categories():
    """Test all critique categories exist."""
    expected = [
        "requirements", "edge_cases", "security", "performance",
        "maintainability", "alternatives", "dependencies", "testing"
    ]
    actual = [c.value for c in CritiqueCategory]
    assert set(expected) == set(actual), f"Expected {expected}, got {actual}"
    print("PASS: test_critique_categories")


def test_default_questions():
    """Test default critique questions are defined for all categories."""
    for cat in CritiqueCategory:
        assert cat in DEFAULT_CRITIQUE_QUESTIONS, f"Missing questions for {cat}"
        assert len(DEFAULT_CRITIQUE_QUESTIONS[cat]) > 0, f"No questions for {cat}"
    print("PASS: test_default_questions")


def test_project_weights():
    """Test project type weights are defined."""
    expected_types = ["api", "ui", "data_pipeline", "infrastructure", "default"]
    for pt in expected_types:
        assert pt in PROJECT_CRITIQUE_WEIGHTS, f"Missing weights for {pt}"
    print("PASS: test_project_weights")


def test_generate_planning_prompt():
    """Test planning prompt generation."""
    prompt = generate_planning_prompt(
        task="Add user authentication",
        context={
            "repo_path": "/test/repo",
            "constraints": ["Must use OAuth2", "No new dependencies"],
        }
    )

    assert "Add user authentication" in prompt
    assert "Phase 1: ARCHITECT" in prompt
    assert "Phase 2: CRITIC" in prompt
    assert "Phase 3: INTEGRATOR" in prompt
    assert "OAuth2" in prompt
    print("PASS: test_generate_planning_prompt")


def test_run_function():
    """Test main run function."""
    mock_tools = {
        "read_file": lambda x: "",
        "glob_files": lambda **kwargs: [],
    }

    result = run(
        args={
            "task": "Implement search feature",
            "project_type": "api",
        },
        tools=mock_tools,
        context={}
    )

    assert result["success"] is True
    assert "planning_prompt" in result
    assert "phases" in result
    assert len(result["phases"]) == 3
    assert "critique_questions" in result
    assert "project_weights" in result
    assert result["project_type"] == "api"
    print("PASS: test_run_function")


def test_run_requires_task():
    """Test that run fails without task."""
    result = run(args={}, tools={}, context={})
    assert result["success"] is False
    assert "error" in result
    print("PASS: test_run_requires_task")


def test_risk_levels():
    """Test risk levels are properly ordered."""
    levels = list(RiskLevel)
    assert levels[0] == RiskLevel.LOW
    assert levels[-1] == RiskLevel.CRITICAL
    print("PASS: test_risk_levels")


def test_architect_phase():
    """Test architect phase returns proper structure."""
    plan = architect_phase(
        task="Test task",
        context={"repo_path": "/test"}
    )

    assert isinstance(plan, ArchitectPlan)
    assert plan.task_summary == "Test task"
    assert hasattr(plan, "assumptions")
    assert hasattr(plan, "implementation_steps")
    print("PASS: test_architect_phase")


def test_critic_phase():
    """Test critic phase returns proper structure."""
    plan = ArchitectPlan(
        task_summary="Test",
        assumptions=[],
        data_model_changes=[],
        api_endpoints=[],
        ui_components=[],
        implementation_steps=[],
        acceptance_criteria=[]
    )

    report = critic_phase(plan, project_type="api")

    assert isinstance(report, CriticReport)
    assert hasattr(report, "critiques")
    assert hasattr(report, "overall_assessment")
    print("PASS: test_critic_phase")


def test_integrator_phase():
    """Test integrator phase merges properly."""
    plan = ArchitectPlan(
        task_summary="Test",
        assumptions=[],
        data_model_changes=[],
        api_endpoints=[],
        ui_components=[],
        implementation_steps=[],
        acceptance_criteria=[]
    )

    critique = CriticReport(
        critiques=[
            Critique(
                category=CritiqueCategory.SECURITY,
                question="Is auth handled?",
                concern="No auth mentioned",
                severity=RiskLevel.HIGH,
                suggested_mitigation="Add auth middleware"
            )
        ],
        missing_requirements=[],
        unhandled_edge_cases=[],
        security_concerns=["No auth"],
        alternative_approaches=[],
        overall_assessment="revise"
    )

    result = integrator_phase(plan, critique)

    assert result.go_no_go in ["go", "go_with_caution", "no_go"]
    assert len(result.addressed_critiques) == 1
    assert len(result.risks) == 1  # HIGH severity becomes a risk
    print("PASS: test_integrator_phase")


if __name__ == "__main__":
    print("Testing adversarial_planning skill...")
    print("-" * 50)

    try:
        test_skill_metadata()
        test_critique_categories()
        test_default_questions()
        test_project_weights()
        test_generate_planning_prompt()
        test_run_function()
        test_run_requires_task()
        test_risk_levels()
        test_architect_phase()
        test_critic_phase()
        test_integrator_phase()
        print("-" * 50)
        print("ALL TESTS PASSED")
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
