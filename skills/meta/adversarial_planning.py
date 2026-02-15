"""
Skill: adversarial_planning
Description: 3-phase planning with built-in critique for robust plans
Version: 1.0.0
Tier: core

Implements the Architect → Critic → Integrator pattern:
1. ARCHITECT: Draft comprehensive implementation plan
2. CRITIC: Challenge the plan with adversarial questions
3. INTEGRATOR: Merge plan with feedback, add mitigations

This pattern produces more robust plans by explicitly surfacing:
- Missing requirements
- Edge cases
- Security concerns
- Alternative approaches
- Risks and mitigations

Origin: Extracted from SuperAGI planify_context pattern.

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
- Individual phase functions for flexible use

Usage:
    # Full 3-phase planning
    result = run({
        "task": "Add user authentication",
        "context": {"repo": "path/to/repo", "constraints": [...]}
    }, tools, context)

    # Or use phases individually
    plan = architect_phase(task, context)
    critiques = critic_phase(plan)
    final = integrator_phase(plan, critiques)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime


# Skill metadata
SKILL_META = {
    "name": "adversarial_planning",
    "description": "3-phase planning with built-in critique (Architect/Critic/Integrator)",
    "tier": "core",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Extracted from SuperAGI planify pattern",
    "triggers": ["plan", "design", "architect", "implement", "build", "create"],
}

# Required capabilities
REQUIRES = ["read_file", "glob_files"]


class CritiqueCategory(Enum):
    """Categories of critique questions."""
    REQUIREMENTS = "requirements"
    EDGE_CASES = "edge_cases"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    ALTERNATIVES = "alternatives"
    DEPENDENCIES = "dependencies"
    TESTING = "testing"


class RiskLevel(Enum):
    """Risk severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Assumption:
    """An assumption that needs validation."""
    statement: str
    validation_method: str
    validated: bool = False
    result: Optional[str] = None


@dataclass
class ImplementationStep:
    """A single implementation step."""
    order: int
    description: str
    file_paths: List[str] = field(default_factory=list)
    dependencies: List[int] = field(default_factory=list)  # Step numbers this depends on
    estimated_complexity: str = "medium"  # low, medium, high


@dataclass
class AcceptanceCriterion:
    """A criterion for accepting the implementation."""
    description: str
    verification_method: str
    met: bool = False


@dataclass
class ArchitectPlan:
    """Output of the Architect phase."""
    task_summary: str
    assumptions: List[Assumption]
    data_model_changes: List[str]
    api_endpoints: List[Dict[str, str]]
    ui_components: List[Dict[str, str]]
    implementation_steps: List[ImplementationStep]
    acceptance_criteria: List[AcceptanceCriterion]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Critique:
    """A single critique point."""
    category: CritiqueCategory
    question: str
    concern: str
    severity: RiskLevel
    suggested_mitigation: Optional[str] = None


@dataclass
class CriticReport:
    """Output of the Critic phase."""
    critiques: List[Critique]
    missing_requirements: List[str]
    unhandled_edge_cases: List[str]
    security_concerns: List[str]
    alternative_approaches: List[Dict[str, str]]
    overall_assessment: str  # "proceed", "revise", "reconsider"


@dataclass
class Risk:
    """A risk identified during planning."""
    description: str
    likelihood: RiskLevel
    impact: RiskLevel
    mitigation: str
    owner: str = "developer"


@dataclass
class ValidationStep:
    """A step to validate the implementation."""
    description: str
    command: Optional[str] = None
    expected_outcome: str = ""


@dataclass
class IntegratedPlan:
    """Final output of the Integrator phase."""
    original_plan: ArchitectPlan
    addressed_critiques: List[Dict[str, str]]  # critique -> resolution
    risks: List[Risk]
    final_task_list: List[ImplementationStep]
    validation_steps: List[ValidationStep]
    go_no_go: str  # "go", "go_with_caution", "no_go"
    rationale: str


# Default critique questions by category
DEFAULT_CRITIQUE_QUESTIONS = {
    CritiqueCategory.REQUIREMENTS: [
        "What requirements might be missing from this plan?",
        "Are there implicit requirements not captured?",
        "Does this meet all stated acceptance criteria?",
    ],
    CritiqueCategory.EDGE_CASES: [
        "What happens with empty/null inputs?",
        "How does this handle concurrent access?",
        "What if the operation is interrupted midway?",
        "How does this behave at scale (10x, 100x)?",
    ],
    CritiqueCategory.SECURITY: [
        "Are there injection vulnerabilities (SQL, XSS, command)?",
        "Is authentication/authorization properly handled?",
        "Are secrets properly managed?",
        "Is input validation sufficient?",
    ],
    CritiqueCategory.PERFORMANCE: [
        "Are there N+1 query problems?",
        "Is caching considered where appropriate?",
        "Are there potential memory leaks?",
        "How does this affect page load / API response time?",
    ],
    CritiqueCategory.MAINTAINABILITY: [
        "Is the code structure clear and consistent?",
        "Are there magic numbers or hardcoded values?",
        "Is error handling comprehensive?",
        "Will this be easy to debug?",
    ],
    CritiqueCategory.ALTERNATIVES: [
        "Is there a simpler approach?",
        "Could an existing library solve this?",
        "What are the trade-offs of this approach vs alternatives?",
    ],
    CritiqueCategory.DEPENDENCIES: [
        "Are new dependencies justified?",
        "Are dependencies well-maintained and secure?",
        "What happens if a dependency becomes unavailable?",
    ],
    CritiqueCategory.TESTING: [
        "Is this testable?",
        "What test coverage is needed?",
        "Are there integration test considerations?",
    ],
}


# Project type presets for weighted critique focus
PROJECT_CRITIQUE_WEIGHTS = {
    "api": {
        CritiqueCategory.SECURITY: 2.0,
        CritiqueCategory.PERFORMANCE: 1.5,
        CritiqueCategory.EDGE_CASES: 1.5,
    },
    "ui": {
        CritiqueCategory.EDGE_CASES: 1.5,
        CritiqueCategory.MAINTAINABILITY: 1.5,
        CritiqueCategory.ALTERNATIVES: 1.2,
    },
    "data_pipeline": {
        CritiqueCategory.EDGE_CASES: 2.0,
        CritiqueCategory.PERFORMANCE: 2.0,
        CritiqueCategory.TESTING: 1.5,
    },
    "infrastructure": {
        CritiqueCategory.SECURITY: 2.0,
        CritiqueCategory.DEPENDENCIES: 1.5,
        CritiqueCategory.EDGE_CASES: 1.5,
    },
    "default": {
        cat: 1.0 for cat in CritiqueCategory
    },
}


def architect_phase(
    task: str,
    context: Dict[str, Any],
    repo_structure: Optional[List[str]] = None
) -> ArchitectPlan:
    """
    Phase 1: Draft a comprehensive implementation plan.

    Args:
        task: Description of what needs to be implemented
        context: Additional context (constraints, existing code, etc.)
        repo_structure: Optional list of relevant file paths

    Returns:
        ArchitectPlan with all planning details
    """
    # This is a template/framework - actual implementation would use LLM
    # to generate the plan based on task and context

    return ArchitectPlan(
        task_summary=task,
        assumptions=[],
        data_model_changes=[],
        api_endpoints=[],
        ui_components=[],
        implementation_steps=[],
        acceptance_criteria=[]
    )


def critic_phase(
    plan: ArchitectPlan,
    project_type: str = "default",
    custom_questions: Optional[Dict[CritiqueCategory, List[str]]] = None
) -> CriticReport:
    """
    Phase 2: Challenge the plan with adversarial questions.

    Args:
        plan: The ArchitectPlan to critique
        project_type: Type of project for weighted critique focus
        custom_questions: Additional critique questions by category

    Returns:
        CriticReport with all concerns and alternatives
    """
    questions = {**DEFAULT_CRITIQUE_QUESTIONS}
    if custom_questions:
        for cat, qs in custom_questions.items():
            questions[cat] = questions.get(cat, []) + qs

    weights = PROJECT_CRITIQUE_WEIGHTS.get(project_type, PROJECT_CRITIQUE_WEIGHTS["default"])

    # This is a template - actual implementation would use LLM
    # to generate critiques based on questions and plan

    return CriticReport(
        critiques=[],
        missing_requirements=[],
        unhandled_edge_cases=[],
        security_concerns=[],
        alternative_approaches=[],
        overall_assessment="proceed"
    )


def integrator_phase(
    plan: ArchitectPlan,
    critique: CriticReport
) -> IntegratedPlan:
    """
    Phase 3: Merge plan with critique feedback.

    Args:
        plan: Original ArchitectPlan
        critique: CriticReport with concerns

    Returns:
        IntegratedPlan with mitigations and final task list
    """
    # Address each critique
    addressed = []
    risks = []

    for c in critique.critiques:
        addressed.append({
            "critique": c.question,
            "resolution": c.suggested_mitigation or "To be addressed during implementation"
        })

        if c.severity in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            risks.append(Risk(
                description=c.concern,
                likelihood=c.severity,
                impact=c.severity,
                mitigation=c.suggested_mitigation or "TBD"
            ))

    # Determine go/no-go
    critical_count = sum(1 for c in critique.critiques if c.severity == RiskLevel.CRITICAL)
    high_count = sum(1 for c in critique.critiques if c.severity == RiskLevel.HIGH)

    if critical_count > 0:
        go_no_go = "no_go"
        rationale = f"{critical_count} critical issues must be resolved first"
    elif high_count > 2:
        go_no_go = "go_with_caution"
        rationale = f"{high_count} high-severity issues require attention"
    else:
        go_no_go = "go"
        rationale = "Plan is sound with acceptable risk level"

    return IntegratedPlan(
        original_plan=plan,
        addressed_critiques=addressed,
        risks=risks,
        final_task_list=plan.implementation_steps,
        validation_steps=[],
        go_no_go=go_no_go,
        rationale=rationale
    )


def generate_planning_prompt(task: str, context: Dict[str, Any]) -> str:
    """
    Generate a structured prompt for LLM-based planning.

    This prompt guides the LLM through all three phases.
    """
    repo_path = context.get("repo_path", "")
    constraints = context.get("constraints", [])
    existing_patterns = context.get("existing_patterns", [])

    prompt = f"""# Adversarial Planning: {task}

## Context
- Repository: {repo_path}
- Constraints: {', '.join(constraints) if constraints else 'None specified'}
- Existing patterns: {', '.join(existing_patterns) if existing_patterns else 'None identified'}

---

## Phase 1: ARCHITECT

Draft a comprehensive implementation plan including:

1. **Task Summary**: One paragraph describing the goal
2. **Assumptions**: List assumptions that need validation
3. **Data Model Changes**: Any database/schema changes
4. **API Endpoints**: New or modified endpoints (method, path, purpose)
5. **UI Components**: New or modified components
6. **Implementation Steps**: Ordered steps with file paths
7. **Acceptance Criteria**: How to verify completion

---

## Phase 2: CRITIC

Challenge the Architect's plan:

1. **Missing Requirements**: What's not covered?
2. **Edge Cases**: What could break?
3. **Security Concerns**: What vulnerabilities exist?
4. **Performance Issues**: What could be slow?
5. **Alternatives**: Is there a better approach?

Be adversarial. Assume things will go wrong.

---

## Phase 3: INTEGRATOR

Merge the plan with critique feedback:

1. **Address Critiques**: How to resolve each concern
2. **Risk Table**: Likelihood, impact, mitigation for each risk
3. **Final Task List**: Updated implementation steps
4. **Validation Steps**: Commands/checks to verify success
5. **Go/No-Go Decision**: Proceed, revise, or reconsider?

---

Begin with Phase 1 (ARCHITECT):
"""
    return prompt


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            task: str - what to plan
            project_type: str - api/ui/data_pipeline/infrastructure/default
            repo_path: str - path to repository
            constraints: List[str] - any constraints
            custom_critiques: Dict - additional critique questions
        }
        tools: {
            read_file: callable
            glob_files: callable
        }
        context: {run_id, etc.}

    Returns:
        {
            success: bool,
            planning_prompt: str - prompt to use for LLM planning,
            phases: dict - phase definitions,
            critique_questions: dict - questions by category,
            project_weights: dict - critique weights for project type
        }
    """
    task = args.get("task", "")
    if not task:
        return {"success": False, "error": "task is required"}

    project_type = args.get("project_type", "default")
    repo_path = args.get("repo_path", "")
    constraints = args.get("constraints", [])
    custom_critiques = args.get("custom_critiques", {})

    # Build context
    planning_context = {
        "repo_path": repo_path,
        "constraints": constraints,
        "existing_patterns": [],
    }

    # Try to discover repo structure if path provided
    if repo_path and tools.get("glob_files"):
        try:
            files = tools["glob_files"](pattern="**/*.{py,ts,tsx,js,jsx}", path=repo_path)
            planning_context["repo_structure"] = files[:50]  # Limit for context
        except Exception:
            pass

    # Generate the planning prompt
    prompt = generate_planning_prompt(task, planning_context)

    # Get critique questions (with any custom additions)
    questions = {cat.value: qs for cat, qs in DEFAULT_CRITIQUE_QUESTIONS.items()}
    if custom_critiques:
        for cat, qs in custom_critiques.items():
            if cat in questions:
                questions[cat].extend(qs)
            else:
                questions[cat] = qs

    # Get weights for project type
    weights = PROJECT_CRITIQUE_WEIGHTS.get(project_type, PROJECT_CRITIQUE_WEIGHTS["default"])
    weights_dict = {cat.value: w for cat, w in weights.items()}

    return {
        "success": True,
        "planning_prompt": prompt,
        "phases": {
            "1_architect": {
                "name": "Architect",
                "purpose": "Draft comprehensive implementation plan",
                "outputs": ["task_summary", "assumptions", "data_model_changes",
                          "api_endpoints", "ui_components", "implementation_steps",
                          "acceptance_criteria"]
            },
            "2_critic": {
                "name": "Critic",
                "purpose": "Challenge the plan with adversarial questions",
                "outputs": ["missing_requirements", "edge_cases", "security_concerns",
                          "performance_issues", "alternatives", "overall_assessment"]
            },
            "3_integrator": {
                "name": "Integrator",
                "purpose": "Merge plan with critique, add mitigations",
                "outputs": ["addressed_critiques", "risk_table", "final_task_list",
                          "validation_steps", "go_no_go_decision"]
            }
        },
        "critique_questions": questions,
        "project_weights": weights_dict,
        "project_type": project_type
    }


# Export key components for direct use
__all__ = [
    "SKILL_META",
    "REQUIRES",
    "run",
    "architect_phase",
    "critic_phase",
    "integrator_phase",
    "generate_planning_prompt",
    "ArchitectPlan",
    "CriticReport",
    "IntegratedPlan",
    "Critique",
    "Risk",
    "CritiqueCategory",
    "RiskLevel",
    "DEFAULT_CRITIQUE_QUESTIONS",
    "PROJECT_CRITIQUE_WEIGHTS",
]


if __name__ == "__main__":
    print("adversarial_planning Skill v1.0")
    print("=" * 50)
    print("Origin: Extracted from SuperAGI planify pattern")
    print()
    print("Phases:")
    print("  1. ARCHITECT - Draft comprehensive plan")
    print("  2. CRITIC - Challenge with adversarial questions")
    print("  3. INTEGRATOR - Merge and add mitigations")
    print()
    print("Critique Categories:")
    for cat in CritiqueCategory:
        print(f"  - {cat.value}")
    print()
    print("Project Types (weighted critique focus):")
    for pt in PROJECT_CRITIQUE_WEIGHTS:
        print(f"  - {pt}")
    print()
    print("Usage:")
    print("  result = run({'task': 'Add user auth', 'project_type': 'api'}, tools, ctx)")
    print("  print(result['planning_prompt'])")
