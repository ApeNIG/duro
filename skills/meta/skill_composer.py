"""
Skill: skill_composer
Description: Chain skills into sequential workflows
Version: 1.0.0
Tier: meta

MVP scope (per user requirements):
- Sequential pipeline only (no parallel, no rollback)
- Check skills exist before running
- Run steps in order
- Stop/continue mode on failure
- Attach outputs + timings

Design principles:
- Workflows are data-only (JSON/YAML), not executable code
- No Python eval, no JS eval, no arbitrary transforms
- Context passing uses simple JSONPath-like selectors
- Each step produces output that can be referenced by later steps

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function

Usage via orchestrator:
    duro_run_skill(skill_name="skill_composer", args={
        "workflow": {
            "name": "full_verification",
            "steps": [
                {"skill": "design_to_code_verifier", "args": {...}},
                {"skill": "code_quality_verifier", "args": {...}}
            ]
        }
    })
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

# Import from skill_runner
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))
try:
    from skill_runner import generate_run_id, get_timestamp
except ImportError:
    import uuid
    from datetime import datetime
    def generate_run_id():
        return f"run_{uuid.uuid4().hex[:8]}"
    def get_timestamp():
        return datetime.utcnow().isoformat() + "Z"


# Skill metadata
SKILL_META = {
    "name": "skill_composer",
    "description": "Chain skills into sequential workflows",
    "tier": "meta",
    "version": "1.0.0",
    "author": "duro",
    "triggers": ["compose skills", "run workflow", "chain skills", "pipeline"],
}

# Required capabilities
REQUIRES = ["skill_registry", "skill_runner"]


class FailureMode(Enum):
    """How to handle step failures."""
    STOP = "stop"       # Stop pipeline on first failure
    CONTINUE = "continue"  # Continue with remaining steps


class StepStatus(Enum):
    """Status of a workflow step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_name: str
    skill_name: str
    status: StepStatus
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


@dataclass
class WorkflowResult:
    """Result of executing a complete workflow."""
    workflow_name: str
    run_id: str
    success: bool
    steps: List[StepResult] = field(default_factory=list)
    total_duration_ms: float = 0
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowStep:
    """Definition of a single workflow step."""
    name: str
    skill: str
    args: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[str] = None  # Simple condition: "prev.success" or None
    on_failure: FailureMode = FailureMode.STOP


@dataclass
class Workflow:
    """Definition of a complete workflow."""
    name: str
    steps: List[WorkflowStep]
    description: str = ""
    on_failure: FailureMode = FailureMode.STOP


def parse_workflow(workflow_dict: Dict[str, Any]) -> Workflow:
    """Parse a workflow definition from dict."""
    steps = []
    for i, step_dict in enumerate(workflow_dict.get("steps", [])):
        step = WorkflowStep(
            name=step_dict.get("name", f"step_{i+1}"),
            skill=step_dict["skill"],
            args=step_dict.get("args", {}),
            condition=step_dict.get("condition"),
            on_failure=FailureMode(step_dict.get("on_failure", "stop"))
        )
        steps.append(step)

    return Workflow(
        name=workflow_dict.get("name", "unnamed_workflow"),
        description=workflow_dict.get("description", ""),
        steps=steps,
        on_failure=FailureMode(workflow_dict.get("on_failure", "stop"))
    )


def resolve_args(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve argument references from workflow context.

    Supports simple JSONPath-like references:
    - "$prev.output.match_rate" -> previous step's output.match_rate
    - "$steps.step1.output.findings" -> specific step's output
    - "$context.code_dir" -> workflow context variable

    This is DATA-ONLY - no code execution.
    """
    resolved = {}

    for key, value in args.items():
        if isinstance(value, str) and value.startswith("$"):
            # Parse reference
            parts = value[1:].split(".")
            ref_type = parts[0]

            try:
                if ref_type == "prev" and "prev" in context:
                    obj = context["prev"]
                    for part in parts[1:]:
                        if isinstance(obj, dict):
                            obj = obj.get(part)
                        else:
                            obj = None
                            break
                    resolved[key] = obj

                elif ref_type == "steps" and "steps" in context:
                    step_name = parts[1]
                    obj = context["steps"].get(step_name, {})
                    for part in parts[2:]:
                        if isinstance(obj, dict):
                            obj = obj.get(part)
                        else:
                            obj = None
                            break
                    resolved[key] = obj

                elif ref_type == "context":
                    obj = context
                    for part in parts[1:]:
                        if isinstance(obj, dict):
                            obj = obj.get(part)
                        else:
                            obj = None
                            break
                    resolved[key] = obj

                else:
                    resolved[key] = value  # Unresolved reference, keep as-is

            except Exception:
                resolved[key] = value  # On error, keep original

        elif isinstance(value, dict):
            # Recurse into nested dicts
            resolved[key] = resolve_args(value, context)
        else:
            resolved[key] = value

    return resolved


def evaluate_condition(condition: str, context: Dict[str, Any]) -> bool:
    """
    Evaluate a simple condition string.

    Only supports:
    - "prev.success" -> previous step succeeded
    - "prev.failed" -> previous step failed
    - "always" -> always run

    This is DATA-ONLY - no code execution.
    """
    if not condition or condition == "always":
        return True

    if condition == "prev.success":
        return context.get("prev", {}).get("success", False)

    if condition == "prev.failed":
        return not context.get("prev", {}).get("success", True)

    # Unknown condition = run
    return True


def run_workflow(
    workflow: Workflow,
    skill_runner: Callable,
    tools: Dict[str, Any],
    initial_context: Dict[str, Any] = None
) -> WorkflowResult:
    """
    Execute a workflow sequentially.

    Args:
        workflow: The workflow to execute
        skill_runner: Function to run a skill: (skill_name, args, tools, context) -> result
        tools: MCP tools dict
        initial_context: Initial context variables

    Returns:
        WorkflowResult with all step results
    """
    run_id = generate_run_id()
    started_at = get_timestamp()
    start_time = time.time()

    result = WorkflowResult(
        workflow_name=workflow.name,
        run_id=run_id,
        success=True,
        started_at=started_at,
        context=initial_context or {}
    )

    # Workflow context for variable resolution
    wf_context = {
        "context": initial_context or {},
        "steps": {},
        "prev": None
    }

    for step in workflow.steps:
        step_started = get_timestamp()
        step_start = time.time()

        # Check condition
        if step.condition and not evaluate_condition(step.condition, wf_context):
            step_result = StepResult(
                step_name=step.name,
                skill_name=step.skill,
                status=StepStatus.SKIPPED,
                started_at=step_started,
                ended_at=get_timestamp()
            )
            result.steps.append(step_result)
            continue

        # Resolve args with context
        resolved_args = resolve_args(step.args, wf_context)

        try:
            # Run the skill
            skill_output = skill_runner(
                step.skill,
                resolved_args,
                tools,
                {"run_id": f"{run_id}_{step.name}"}
            )

            step_success = skill_output.get("success", True)
            step_result = StepResult(
                step_name=step.name,
                skill_name=step.skill,
                status=StepStatus.SUCCESS if step_success else StepStatus.FAILED,
                output=skill_output,
                duration_ms=(time.time() - step_start) * 1000,
                started_at=step_started,
                ended_at=get_timestamp()
            )

            if not step_success:
                step_result.error = skill_output.get("error", "Step failed")

        except Exception as e:
            step_result = StepResult(
                step_name=step.name,
                skill_name=step.skill,
                status=StepStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - step_start) * 1000,
                started_at=step_started,
                ended_at=get_timestamp()
            )

        result.steps.append(step_result)

        # Update context
        wf_context["steps"][step.name] = {
            "success": step_result.status == StepStatus.SUCCESS,
            "output": step_result.output,
            "error": step_result.error
        }
        wf_context["prev"] = wf_context["steps"][step.name]

        # Handle failure
        if step_result.status == StepStatus.FAILED:
            result.success = False
            if step.on_failure == FailureMode.STOP or workflow.on_failure == FailureMode.STOP:
                # Mark remaining steps as skipped
                remaining_idx = workflow.steps.index(step) + 1
                for remaining in workflow.steps[remaining_idx:]:
                    result.steps.append(StepResult(
                        step_name=remaining.name,
                        skill_name=remaining.skill,
                        status=StepStatus.SKIPPED
                    ))
                break

    result.total_duration_ms = (time.time() - start_time) * 1000
    result.ended_at = get_timestamp()

    return result


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            workflow: dict - workflow definition
            initial_context: dict (optional) - initial context variables
        }
        tools: {
            skill_registry: dict - available skills
            skill_runner: callable - function to run skills
        }
        context: {run_id, constraints}

    Returns:
        {success, workflow_name, steps, total_duration_ms, errors}
    """
    workflow_dict = args.get("workflow")
    initial_context = args.get("initial_context", {})

    if not workflow_dict:
        return {"success": False, "error": "workflow is required"}

    # Parse workflow
    try:
        workflow = parse_workflow(workflow_dict)
    except Exception as e:
        return {"success": False, "error": f"Invalid workflow: {str(e)}"}

    # Check skills exist
    skill_registry = tools.get("skill_registry", {})
    for step in workflow.steps:
        if step.skill not in skill_registry:
            return {
                "success": False,
                "error": f"Unknown skill: {step.skill}",
                "available_skills": list(skill_registry.keys())
            }

    # Get skill runner
    skill_runner_func = tools.get("skill_runner")
    if not skill_runner_func:
        return {"success": False, "error": "skill_runner function not provided"}

    # Execute workflow
    result = run_workflow(
        workflow,
        skill_runner_func,
        tools,
        initial_context
    )

    return _format_result(result)


def _format_result(result: WorkflowResult) -> Dict[str, Any]:
    """Format result for return."""
    return {
        "success": result.success,
        "workflow_name": result.workflow_name,
        "run_id": result.run_id,
        "total_duration_ms": result.total_duration_ms,
        "started_at": result.started_at,
        "ended_at": result.ended_at,
        "steps": [
            {
                "name": s.step_name,
                "skill": s.skill_name,
                "status": s.status.value,
                "duration_ms": s.duration_ms,
                "output_summary": _summarize_output(s.output) if s.output else None,
                "error": s.error
            }
            for s in result.steps
        ],
        "step_count": len(result.steps),
        "success_count": len([s for s in result.steps if s.status == StepStatus.SUCCESS]),
        "failed_count": len([s for s in result.steps if s.status == StepStatus.FAILED]),
        "skipped_count": len([s for s in result.steps if s.status == StepStatus.SKIPPED]),
    }


def _summarize_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """Create a summary of step output (avoid huge outputs in result)."""
    if not output:
        return {}

    summary = {
        "success": output.get("success"),
    }

    # Include key metrics without full data
    for key in ["match_rate", "tokens_checked", "total_findings", "files_checked", "drifts_count"]:
        if key in output:
            summary[key] = output[key]

    return summary


# === EXAMPLE WORKFLOWS ===

FULL_VERIFICATION_WORKFLOW = {
    "name": "full_verification",
    "description": "Run design verification and code quality checks",
    "steps": [
        {
            "name": "design_check",
            "skill": "design_to_code_verifier",
            "args": {
                "pen_file": "$context.pen_file",
                "code_dir": "$context.code_dir",
                "output_format": "devkit"
            }
        },
        {
            "name": "quality_check",
            "skill": "code_quality_verifier",
            "args": {
                "code_dir": "$context.code_dir",
                "output_format": "devkit"
            }
        }
    ],
    "on_failure": "continue"  # Run both checks even if first fails
}

CI_BLOCKING_WORKFLOW = {
    "name": "ci_blocking",
    "description": "Blocking checks for CI pipeline",
    "steps": [
        {
            "name": "security_check",
            "skill": "code_quality_verifier",
            "args": {
                "code_dir": "$context.code_dir",
                "rules": ["sec_no_eval", "sec_no_dangerous_html", "sec_no_inner_html", "sec_no_hardcoded_secrets"]
            }
        },
        {
            "name": "type_safety_check",
            "skill": "code_quality_verifier",
            "args": {
                "code_dir": "$context.code_dir",
                "rules": ["ts_no_as_any", "ts_no_as_unknown_as"]
            },
            "condition": "prev.success"  # Only if security passed
        }
    ],
    "on_failure": "stop"
}


# CLI for testing
if __name__ == "__main__":
    print("skill_composer Skill v1.0")
    print("=" * 40)
    print("\nFeatures:")
    print("  - Sequential pipeline execution")
    print("  - Stop/continue failure modes")
    print("  - Simple context variable resolution")
    print("  - Step timing and output tracking")

    print("\n\nExample workflow: full_verification")
    print(json.dumps(FULL_VERIFICATION_WORKFLOW, indent=2))

    print("\n\nExample workflow: ci_blocking")
    print(json.dumps(CI_BLOCKING_WORKFLOW, indent=2))
