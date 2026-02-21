"""
Duro Orchestrator - Workflow selector and run logger.

The orchestrator is a thin routing layer that:
1. Normalizes intent
2. Checks rules
3. **Checks autonomy** (NEW in Phase 4)
4. Selects an action plan
5. Executes (or dry-runs)
6. Writes a run log linking everything together

One new concept: a "run" - the auditable trace of an orchestrated action.
"""

import json
import random
import re
import string
import time
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from time_utils import utc_now, utc_now_iso
from pathlib import Path
from typing import Any, Optional

# Autonomy Ladder (governance) - Phase 4
AGENT_LIB_PATH = str(Path.home() / ".agent" / "lib")
if AGENT_LIB_PATH not in sys.path:
    sys.path.insert(0, AGENT_LIB_PATH)

AUTONOMY_AVAILABLE = False
AUTONOMY_IMPORT_ERROR = None
try:
    from autonomy_ladder import (
        check_action, record_outcome, classify_action_domain, classify_action_risk,
        get_reputation_store, run_maturation, ActionRisk, AutonomyLevel
    )
    AUTONOMY_AVAILABLE = True
except ImportError as e:
    AUTONOMY_IMPORT_ERROR = str(e)
    pass  # Autonomy enforcement disabled

# Version info for run logs
SERVER_BUILD = "1.2.0"  # Phase 3: proactive recall
SCHEMA_VERSION = "1.1"

# Stop conditions
MAX_TOOL_CALLS = 10
MAX_RETRIES = 3
MAX_SECONDS = 60
SKILL_TIMEOUT_SECONDS = 60

# External tool mapping: capability -> (server, tool_name)
# This is a tiny mapping, not a full registry
EXTERNAL_TOOL_MAP = {
    "search": ("superagi", "web_search"),
    "read": ("superagi", "read_webpage"),
}


@dataclass
class RuleDecision:
    """A decision made based on a rule."""
    rule_id: str
    severity: str  # hard, soft
    decision: str  # ALLOW, CONSTRAIN, DENY
    notes: str = ""


@dataclass
class Plan:
    """The selected action plan."""
    selected: str  # skill or tool name
    type: str  # "skill" or "tool"
    reason: str
    constraints: dict = field(default_factory=dict)


@dataclass
class ToolCall:
    """A single tool call during execution."""
    name: str
    ok: bool
    ms: int
    error: Optional[str] = None


@dataclass
class RunLog:
    """Complete run log structure."""
    run_id: str
    started_at: str
    finished_at: Optional[str]
    intent: str
    intent_normalized: str
    args: dict
    dry_run: bool
    sensitivity: str

    rules_checked: bool
    rules_applicable: list
    rules_decisions: list

    # Autonomy (Phase 4)
    autonomy_checked: bool = False
    autonomy_domain: Optional[str] = None
    autonomy_risk: Optional[str] = None
    autonomy_allowed: bool = True
    autonomy_level: Optional[int] = None
    autonomy_score: Optional[float] = None
    autonomy_downgraded: bool = False

    plan_selected: Optional[str] = None
    plan_type: Optional[str] = None
    plan_reason: Optional[str] = None
    plan_constraints: dict = field(default_factory=dict)

    tool_calls: list = field(default_factory=list)
    outcome: str = "pending"  # pending, success, failed, denied, dry_run, autonomy_blocked
    error: Optional[str] = None
    duration_ms: int = 0

    artifacts_created: list = field(default_factory=list)
    artifact_paths: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    # Governance audit breadcrumb: append-only log of autonomy blocks
    autonomy_block_events: list = field(default_factory=list)

    server_build: str = SERVER_BUILD
    schema_version: str = SCHEMA_VERSION


def generate_run_id() -> str:
    """Generate unique run ID."""
    now = utc_now()
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"run_{date_part}_{time_part}_{random_part}"


def normalize_intent(intent: str) -> str:
    """
    Normalize intent string to a canonical form.
    Returns one of: store_fact, store_decision, delete_artifact, unknown
    """
    intent_lower = intent.lower().strip()

    # store_fact patterns
    if any(p in intent_lower for p in ["store fact", "save fact", "record fact", "add fact"]):
        return "store_fact"
    if any(p in intent_lower for p in ["remember", "note that", "note:"]):
        return "store_fact"  # Low-confidence note

    # store_decision patterns
    if any(p in intent_lower for p in ["store decision", "record decision", "decided", "chose"]):
        return "store_decision"

    # delete_artifact patterns
    if any(p in intent_lower for p in ["delete artifact", "remove artifact", "delete fact", "delete decision"]):
        return "delete_artifact"

    return "unknown"


def detect_sensitivity(args: dict, default: str = "internal") -> str:
    """
    Auto-detect sensitivity based on args content.
    If args contain PII-like patterns, upgrade to internal/sensitive.
    """
    args_str = json.dumps(args).lower()

    # Patterns that suggest sensitive data
    sensitive_patterns = [
        r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',  # email
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # phone
        r'\b\d{3}[-]?\d{2}[-]?\d{4}\b',  # SSN pattern
        r'password', r'secret', r'api[_-]?key', r'token',
        r'credit[_\s]?card', r'ssn', r'social[_\s]?security'
    ]

    for pattern in sensitive_patterns:
        if re.search(pattern, args_str):
            return "sensitive"

    return default


class Orchestrator:
    """
    The workflow selector and executor.
    Routes intents through rules to skills, logs everything.
    """

    def __init__(self, memory_dir: Path, rules_module, skills_module, artifact_store, external_tools=None):
        self.memory_dir = Path(memory_dir)
        self.runs_dir = self.memory_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

        self.rules = rules_module
        self.skills = skills_module
        self.artifacts = artifact_store

        # External tools (from other MCP servers like superagi)
        # Dict of capability_name -> callable
        self.external_tools = external_tools or {}

        # === Autonomy heartbeat: process matured rewards on startup ===
        if AUTONOMY_AVAILABLE:
            try:
                result = run_maturation()
                if result.get("matured_count", 0) > 0:
                    # Log maturation results (visible in server logs)
                    print(f"[Autonomy] Startup maturation: {result['matured_count']} rewards processed")
            except Exception as e:
                print(f"[Autonomy] Maturation error on startup: {e}")

    def _build_tools_dict(self, run_id: str, run: "RunLog" = None) -> dict:
        """
        Build the tools dict that skills receive.
        Skills call tools["search"], tools["store_fact"], etc.
        They never see server names or implementation details.

        Each tool is wrapped with per-tool-call autonomy gating.
        """
        tools = {}

        def _record_block_event(tool_name: str, domain: str, risk: str, reason: str):
            """Record an autonomy block event to the run log (append-only)."""
            if run:
                run.autonomy_block_events.append({
                    "tool_name": tool_name,
                    "domain": domain,
                    "risk": risk,
                    "reason": reason,
                    "timestamp": utc_now_iso()
                })

        def _gate_tool(tool_name: str, tool_func, is_destructive: bool = False):
            """Wrap a tool with per-tool-call autonomy check + token consumption."""
            def gated_wrapper(*args, **kwargs):
                # === Per-tool-call gate ===
                if AUTONOMY_AVAILABLE:
                    # Classify risk FIRST (outside try) - if this fails, fail closed
                    try:
                        risk = classify_action_risk(tool_name, {"is_destructive": is_destructive})
                    except Exception as e:
                        # Can't even classify - fail closed
                        if run:
                            run.notes.append(f"Autonomy: BLOCKED `{tool_name}` - risk classification failed: {e}")
                        _record_block_event(tool_name, "unknown", "unknown", f"risk classification failed: {e}")
                        return {
                            "success": False,
                            "error": f"Autonomy: cannot classify risk for {tool_name}",
                            "blocked_by_autonomy": True,
                            "classification_error": True
                        }

                    is_risky = risk in (ActionRisk.DESTRUCTIVE, ActionRisk.CRITICAL)

                    try:
                        domain = classify_action_domain(tool_name)
                        action_id = f"{tool_name}_{domain}"

                        # Check permission (no token consumption yet)
                        context = {"is_destructive": is_destructive}
                        result = check_action(tool_name, context, action_id=action_id, consume_token=False)

                        if not result.allowed:
                            # Tool blocked - check if it's because we need approval
                            if result.requires_approval:
                                if run:
                                    run.notes.append(f"Autonomy: tool `{tool_name}` requires approval token")
                            else:
                                if run:
                                    run.notes.append(f"Autonomy: blocked `{tool_name}` - {result.reason}")
                            _record_block_event(tool_name, domain, risk.value, result.reason)
                            return {
                                "success": False,
                                "error": f"Autonomy blocked: {result.reason}",
                                "blocked_by_autonomy": True,
                                "required_level": result.required_level.value,
                                "requires_approval": result.requires_approval
                            }

                        # === Token consumption for destructive/critical tools ===
                        # Use structured field, not string matching
                        if is_risky and result.allowed_via_token:
                            from autonomy_ladder import get_autonomy_enforcer
                            enforcer = get_autonomy_enforcer()
                            consumed = enforcer.use_approval(action_id, used_by=run_id)
                            if consumed:
                                if run:
                                    run.notes.append(f"Autonomy: consumed token for `{tool_name}`")
                            else:
                                # Token was valid at check but gone now - race or expiry
                                if run:
                                    run.notes.append(f"Autonomy: token expired for `{tool_name}`")
                                _record_block_event(tool_name, domain, risk.value, "token expired or already used")
                                return {
                                    "success": False,
                                    "error": "Approval token expired or already used",
                                    "blocked_by_autonomy": True,
                                    "token_expired": True
                                }

                    except Exception as e:
                        # === Fail policy: closed for risky, open for safe ===
                        # Use computed risk, not is_destructive flag
                        if is_risky:
                            # Fail CLOSED for destructive/critical - autonomy error = block
                            if run:
                                run.notes.append(f"Autonomy: BLOCKED `{tool_name}` on gate error (fail-closed): {e}")
                            _record_block_event(tool_name, "unknown", risk.value, f"gate error (fail-closed): {e}")
                            return {
                                "success": False,
                                "error": f"Autonomy gate error (fail-closed): {e}",
                                "blocked_by_autonomy": True,
                                "gate_error": True
                            }
                        else:
                            # Fail OPEN for safe tools - log and continue
                            if run:
                                run.notes.append(f"Autonomy: gate error for `{tool_name}` (fail-open): {e}")

                # Execute the actual tool
                return tool_func(*args, **kwargs)
            return gated_wrapper

        # Search capability (from superagi or similar)
        if "search" in self.external_tools:
            tools["search"] = _gate_tool("search", self.external_tools["search"])
        else:
            # Stub that returns empty results
            tools["search"] = lambda q, **kw: {"results": [], "error": "search not configured"}

        # Read webpage capability
        if "read" in self.external_tools:
            tools["read"] = _gate_tool("read_webpage", self.external_tools["read"])
        else:
            tools["read"] = lambda url, **kw: {"content": "", "error": "read not configured"}

        # Internal Duro tools - wrapped to track calls
        def store_fact_wrapper(**kwargs):
            success, artifact_id, path = self.artifacts.store_fact(
                claim=kwargs.get("claim", ""),
                source_urls=kwargs.get("source_urls"),
                snippet=kwargs.get("snippet"),
                confidence=kwargs.get("confidence", 0.5),
                tags=kwargs.get("tags"),
                workflow=kwargs.get("workflow", run_id),
                sensitivity=kwargs.get("sensitivity", "public"),
                evidence_type=kwargs.get("evidence_type", "none"),
                provenance=kwargs.get("provenance", "unknown")
            )
            return {"success": success, "artifact_id": artifact_id, "path": path}

        def store_decision_wrapper(**kwargs):
            success, artifact_id, path = self.artifacts.store_decision(
                decision=kwargs.get("decision", ""),
                rationale=kwargs.get("rationale", ""),
                alternatives=kwargs.get("alternatives"),
                context=kwargs.get("context"),
                reversible=kwargs.get("reversible", True),
                tags=kwargs.get("tags"),
                workflow=kwargs.get("workflow", run_id),
                sensitivity=kwargs.get("sensitivity", "internal")
            )
            return {"success": success, "artifact_id": artifact_id, "path": path}

        def log_wrapper(msg, **kwargs):
            # Simple logging to memory
            return {"logged": True, "message": msg}

        # Gate the internal tools (safe writes, but still gated for L2+)
        tools["store_fact"] = _gate_tool("store_fact", store_fact_wrapper)
        tools["store_decision"] = _gate_tool("store_decision", store_decision_wrapper)
        tools["log"] = log_wrapper  # Logging is not gated

        return tools

    def set_external_tools(self, tools: dict):
        """Set external tool callables (e.g., from superagi MCP)."""
        self.external_tools = tools

    def orchestrate(
        self,
        intent: str,
        args: dict,
        dry_run: bool = False,
        sensitivity: Optional[str] = None
    ) -> dict:
        """
        Main entry point. Route intent through rules to skill, execute, log.

        Returns dict with run_id, outcome, artifacts, etc.
        """
        start_time = time.time()
        run_id = generate_run_id()

        # Normalize
        intent_normalized = normalize_intent(intent)

        # Detect sensitivity
        final_sensitivity = sensitivity or detect_sensitivity(args)

        # Initialize run log
        run = RunLog(
            run_id=run_id,
            started_at=utc_now_iso(),
            finished_at=None,
            intent=intent,
            intent_normalized=intent_normalized,
            args=args,
            dry_run=dry_run,
            sensitivity=final_sensitivity,
            rules_checked=False,
            rules_applicable=[],
            rules_decisions=[],
            plan_selected=None,
            plan_type=None,
            plan_reason=None,
            plan_constraints={},
            tool_calls=[],
            outcome="pending",
            error=None,
            duration_ms=0,
            artifacts_created=[],
            artifact_paths=[],
            notes=[]
        )

        try:
            # Step 0: Proactive recall (Phase 3)
            # Surface relevant memories for context - non-blocking
            run = self._proactive_recall(run, intent, args)

            # Step 1: Check rules
            run = self._apply_rules(run, intent_normalized, args)

            # Check for DENY
            denies = [d for d in run.rules_decisions if d["decision"] == "DENY"]
            if denies:
                run.outcome = "denied"
                run.error = f"Denied by rule: {denies[0]['rule_id']}"
                run.notes.append(f"Rule {denies[0]['rule_id']} blocked execution")
                return self._finalize_run(run, start_time)

            # Step 2: Select plan
            run = self._select_plan(run, intent_normalized, args)

            if run.plan_selected is None:
                run.outcome = "failed"
                run.error = f"No plan available for intent: {intent_normalized}"
                return self._finalize_run(run, start_time)

            # Step 2.5: Check autonomy (Phase 4)
            run = self._check_autonomy(run, intent_normalized, args)

            # Check for autonomy block
            if not run.autonomy_allowed:
                if run.autonomy_downgraded:
                    # Downgraded to propose mode
                    run.outcome = "dry_run"
                    run.notes.append(f"Autonomy downgrade: {run.plan_selected} → propose only")
                    run.notes.append(f"Domain {run.autonomy_domain} score {run.autonomy_score:.2f} insufficient")
                    return self._finalize_run(run, start_time)
                else:
                    run.outcome = "autonomy_blocked"
                    run.error = f"Autonomy blocked: domain {run.autonomy_domain} score {run.autonomy_score:.2f}"
                    return self._finalize_run(run, start_time)

            # Step 3: Execute or dry-run
            if dry_run:
                run.outcome = "dry_run"
                run.notes.append(f"Would execute: {run.plan_selected}")
            else:
                run = self._execute_plan(run, args)

        except Exception as e:
            run.outcome = "failed"
            run.error = str(e)

        return self._finalize_run(run, start_time)

    def _apply_rules(self, run: RunLog, intent: str, args: dict) -> RunLog:
        """Check rules and record decisions."""
        run.rules_checked = True

        # Build task description for rule matching
        task_desc = f"{intent}: {json.dumps(args)[:200]}"

        # Get applicable rules
        applicable = self.rules.check_rules(task_desc)
        run.rules_applicable = [r["rule"]["name"] for r in applicable]

        # Make decisions based on rules
        for match in applicable:
            rule = match["rule"]
            rule_id = rule.get("id", "unknown")
            severity = rule.get("type", "soft")

            # Determine decision based on rule + args
            decision = self._evaluate_rule(rule, intent, args)
            run.rules_decisions.append({
                "rule_id": rule_id,
                "severity": severity,
                "decision": decision["decision"],
                "notes": decision["notes"]
            })

        return run

    def _proactive_recall(self, run: RunLog, intent: str, args: dict) -> RunLog:
        """
        Surface relevant memories for the current task.

        Non-blocking: failures don't stop orchestration.
        Recalled memories are added to run notes for context.
        """
        try:
            from proactive import ProactiveRecall

            # Build context from intent + args
            context = f"{intent}: {json.dumps(args)[:500]}"

            # Create recall instance
            recall = ProactiveRecall(self.artifacts, self.artifacts.index)
            result = recall.recall(
                context=context,
                limit=5,  # Keep it light for orchestration
                include_types=["fact", "decision"],
                force=False  # Let hot path decide
            )

            if result.triggered and result.memories:
                # Add recalled memories as context
                run.notes.append(f"Proactive recall surfaced {len(result.memories)} relevant memories")
                for mem in result.memories[:3]:  # Top 3 only in notes
                    summary = mem.get("summary", "")[:100]
                    run.notes.append(f"  - [{mem['type']}] {summary}")

        except Exception as e:
            # Non-blocking - log but continue
            run.notes.append(f"Proactive recall skipped: {str(e)[:50]}")

        return run

    def _evaluate_rule(self, rule: dict, intent: str, args: dict) -> dict:
        """
        Evaluate a single rule against intent and args.
        Returns {"decision": "ALLOW|CONSTRAIN|DENY", "notes": "..."}
        """
        rule_id = rule.get("id", "")

        # Rule 005: Fact Verification Requirements
        if rule_id == "rule_005" and intent == "store_fact":
            confidence = args.get("confidence", 0.5)
            has_sources = bool(args.get("source_urls"))

            if confidence >= 0.8 and not has_sources:
                return {
                    "decision": "CONSTRAIN",
                    "notes": "High confidence requires sources; routing to verify_and_store_fact"
                }

        # Rule: Stop Conditions (rule about retries/errors)
        if "stop" in rule_id.lower():
            return {"decision": "ALLOW", "notes": "Stop conditions checked at execution time"}

        # Default: allow
        return {"decision": "ALLOW", "notes": "No constraints"}

    def _select_plan(self, run: RunLog, intent: str, args: dict) -> RunLog:
        """Select the skill/tool to execute based on intent and constraints."""

        # Check if any rule constrained us
        constraints = {}
        for dec in run.rules_decisions:
            if dec["decision"] == "CONSTRAIN":
                constraints["rule_constrained"] = True

        # ROUTING TABLE
        if intent == "store_fact":
            confidence = args.get("confidence", 0.5)
            has_sources = bool(args.get("source_urls"))

            if confidence >= 0.8 and not has_sources:
                run.plan_selected = "verify_and_store_fact"
                run.plan_type = "skill"
                run.plan_reason = "High confidence without sources requires verification"
                run.plan_constraints = {"require_sources": True}
            else:
                run.plan_selected = "duro_store_fact"
                run.plan_type = "tool"
                run.plan_reason = "Direct storage (low confidence or sources provided)"
                run.plan_constraints = {}

        elif intent == "store_decision":
            run.plan_selected = "duro_store_decision"
            run.plan_type = "tool"
            run.plan_reason = "Direct decision storage"
            run.plan_constraints = {}

        elif intent == "delete_artifact":
            artifact_id = args.get("artifact_id", "")
            # Check if sensitive
            artifact = self.artifacts.get_artifact(artifact_id) if artifact_id else None
            if artifact and artifact.get("sensitivity") == "sensitive":
                if not args.get("force"):
                    run.plan_constraints = {"requires_force": True}
                    run.notes.append("Sensitive artifact requires force=True")

            run.plan_selected = "duro_delete_artifact"
            run.plan_type = "tool"
            run.plan_reason = "Delete with audit logging"

        else:
            run.plan_selected = None
            run.plan_reason = f"Unknown intent: {intent}"

        return run

    def _check_autonomy(self, run: RunLog, intent: str, args: dict) -> RunLog:
        """
        Check autonomy permissions before execution (Phase 4).

        This is the PRECHECK only - tokens are NOT consumed here.
        Token consumption happens at execution time in _execute_plan.
        """
        if not AUTONOMY_AVAILABLE:
            # Autonomy not available - allow by default
            run.autonomy_checked = False
            run.autonomy_allowed = True
            run.notes.append("Autonomy check skipped (module not available)")
            return run

        run.autonomy_checked = True

        # Map plan to action
        action = run.plan_selected or intent
        context = {
            "is_destructive": "delete" in action.lower(),
            "is_reversible": run.plan_constraints.get("reversible", True),
        }

        # Build action_id for token lookup
        domain = classify_action_domain(action)
        action_id = f"{action}_{domain}"

        # Check permission WITHOUT consuming token (precheck only)
        permission = check_action(action, context, action_id=action_id, consume_token=False)

        run.autonomy_domain = permission.domain
        run.autonomy_risk = permission.action_risk.value
        run.autonomy_allowed = permission.allowed
        run.autonomy_level = permission.current_level.value
        run.autonomy_score = permission.domain_score

        # Track if we'll need to consume a token at execution time
        run.plan_constraints["_autonomy_action_id"] = action_id
        run.plan_constraints["_autonomy_via_token"] = "approval token" in permission.reason

        if not permission.allowed:
            run.autonomy_downgraded = permission.downgrade_to == "propose"
            run.notes.append(f"Autonomy: {permission.reason}")

            if permission.requires_approval:
                run.notes.append(f"Requires approval token: `{action_id}`")
        else:
            run.notes.append(f"Autonomy: allowed at L{permission.current_level.value}")

        return run

    def _execute_plan(self, run: RunLog, args: dict) -> RunLog:
        """Execute the selected plan."""

        # === Consume approval token at execution time (if used) ===
        if AUTONOMY_AVAILABLE and run.plan_constraints.get("_autonomy_via_token"):
            action_id = run.plan_constraints.get("_autonomy_action_id")
            if action_id:
                from autonomy_ladder import get_autonomy_enforcer
                enforcer = get_autonomy_enforcer()
                consumed = enforcer.use_approval(action_id, used_by=run.run_id)
                if consumed:
                    run.notes.append(f"Autonomy: consumed approval token `{action_id}`")
                else:
                    # Token was valid at precheck but gone now - race condition or bug
                    run.notes.append(f"Autonomy: WARNING - token `{action_id}` no longer valid")
                    # Still proceed - we already passed the gate

        if run.plan_type == "skill":
            # Execute via skills module with new interface
            call_start = time.time()
            try:
                # Build tools dict for the skill (with per-tool gating)
                tools = self._build_tools_dict(run.run_id, run=run)

                # Build context
                context = {
                    "run_id": run.run_id,
                    "constraints": run.plan_constraints,
                    "sensitivity": run.sensitivity,
                    "max_sources": 3,
                    "max_pages": 2,
                }

                # Execute with tools interface
                success, result = self.skills.run_skill_with_tools(
                    skill_name=run.plan_selected,
                    args=args,
                    tools=tools,
                    context=context,
                    timeout_seconds=SKILL_TIMEOUT_SECONDS
                )

                call_ms = int((time.time() - call_start) * 1000)

                run.tool_calls.append({
                    "name": run.plan_selected,
                    "ok": success,
                    "ms": call_ms,
                    "error": result.get("error") if not success else None
                })

                if success:
                    run.outcome = "success"
                    # Extract artifact IDs from result
                    if result.get("artifact_id"):
                        run.artifacts_created.append(result["artifact_id"])
                    if result.get("artifacts_created"):
                        run.artifacts_created.extend(result["artifacts_created"])
                else:
                    # Check for timeout - apply degraded fallback
                    if result.get("timeout") and run.intent_normalized == "store_fact":
                        run = self._degraded_fallback_store_fact(run, args, call_ms)
                    else:
                        run.outcome = "failed"
                        run.error = result.get("error", "Unknown skill error")[:500]

            except Exception as e:
                call_ms = int((time.time() - call_start) * 1000)
                run.tool_calls.append({
                    "name": run.plan_selected,
                    "ok": False,
                    "ms": call_ms,
                    "error": str(e)[:200]
                })
                # Try degraded fallback for store_fact
                if run.intent_normalized == "store_fact":
                    run = self._degraded_fallback_store_fact(run, args, call_ms)
                else:
                    run.outcome = "failed"
                    run.error = str(e)

        elif run.plan_type == "tool":
            # Execute via artifact store directly
            call_start = time.time()
            try:
                if run.plan_selected == "duro_store_fact":
                    # Add provenance
                    success, artifact_id, path = self.artifacts.store_fact(
                        claim=args.get("claim", ""),
                        source_urls=args.get("source_urls"),
                        snippet=args.get("snippet"),
                        confidence=args.get("confidence", 0.5),
                        tags=args.get("tags"),
                        workflow="duro_orchestrate",
                        sensitivity=run.sensitivity,
                        evidence_type=args.get("evidence_type", "none"),
                        provenance=args.get("provenance", "unknown")
                    )
                    call_ms = int((time.time() - call_start) * 1000)

                    run.tool_calls.append({
                        "name": "duro_store_fact",
                        "ok": success,
                        "ms": call_ms
                    })

                    if success:
                        run.outcome = "success"
                        run.artifacts_created.append(artifact_id)
                        run.artifact_paths.append(path)
                    else:
                        run.outcome = "failed"
                        run.error = path  # Error message in path slot

                elif run.plan_selected == "duro_store_decision":
                    success, artifact_id, path = self.artifacts.store_decision(
                        decision=args.get("decision", ""),
                        rationale=args.get("rationale", ""),
                        alternatives=args.get("alternatives"),
                        context=args.get("context"),
                        reversible=args.get("reversible", True),
                        tags=args.get("tags"),
                        workflow="duro_orchestrate",
                        sensitivity=run.sensitivity
                    )
                    call_ms = int((time.time() - call_start) * 1000)

                    run.tool_calls.append({
                        "name": "duro_store_decision",
                        "ok": success,
                        "ms": call_ms
                    })

                    if success:
                        run.outcome = "success"
                        run.artifacts_created.append(artifact_id)
                        run.artifact_paths.append(path)
                    else:
                        run.outcome = "failed"
                        run.error = path

                elif run.plan_selected == "duro_delete_artifact":
                    success, message = self.artifacts.delete_artifact(
                        artifact_id=args.get("artifact_id", ""),
                        reason=args.get("reason", "Orchestrated deletion"),
                        force=args.get("force", False)
                    )
                    call_ms = int((time.time() - call_start) * 1000)

                    run.tool_calls.append({
                        "name": "duro_delete_artifact",
                        "ok": success,
                        "ms": call_ms
                    })

                    if success:
                        run.outcome = "success"
                        run.notes.append(message)
                    else:
                        run.outcome = "failed"
                        run.error = message

                else:
                    run.outcome = "failed"
                    run.error = f"Unknown tool: {run.plan_selected}"

            except Exception as e:
                call_ms = int((time.time() - call_start) * 1000)
                run.tool_calls.append({
                    "name": run.plan_selected,
                    "ok": False,
                    "ms": call_ms,
                    "error": str(e)[:200]
                })
                run.outcome = "failed"
                run.error = str(e)

        return run

    def _degraded_fallback_store_fact(self, run: RunLog, args: dict, original_ms: int) -> RunLog:
        """
        Fallback when skill verification fails/timeouts.
        Stores fact as unverified with capped confidence.
        Outcome is 'degraded_success' - not a hard failure.
        """
        run.notes.append("Verification failed/timeout - storing as unverified")

        call_start = time.time()
        try:
            # Cap confidence at 0.5, mark as unverified
            capped_confidence = min(args.get("confidence", 0.5), 0.5)

            # Add needs_verification tag
            tags = list(args.get("tags") or [])
            if "needs_verification" not in tags:
                tags.append("needs_verification")

            success, artifact_id, path = self.artifacts.store_fact(
                claim=args.get("claim", ""),
                source_urls=None,  # No verified sources
                snippet=None,
                confidence=capped_confidence,
                tags=tags,
                workflow=f"{run.run_id}_degraded",
                sensitivity=run.sensitivity,
                evidence_type="none",
                provenance="unknown"
            )

            call_ms = int((time.time() - call_start) * 1000)

            run.tool_calls.append({
                "name": "duro_store_fact_degraded",
                "ok": success,
                "ms": call_ms,
                "note": "Degraded fallback"
            })

            if success:
                run.outcome = "degraded_success"
                run.artifacts_created.append(artifact_id)
                run.artifact_paths.append(path)
                run.notes.append(f"Stored as unverified with confidence={capped_confidence}")
            else:
                run.outcome = "failed"
                run.error = f"Degraded fallback also failed: {path}"

        except Exception as e:
            run.outcome = "failed"
            run.error = f"Degraded fallback exception: {str(e)}"

        return run

    def _finalize_run(self, run: RunLog, start_time: float) -> dict:
        """Finalize and write run log."""
        run.finished_at = utc_now_iso()
        run.duration_ms = int((time.time() - start_time) * 1000)

        # === Automatic outcome recording for autonomy (Phase 4) ===
        if AUTONOMY_AVAILABLE and run.autonomy_checked and run.plan_selected:
            try:
                # Only record outcomes for executed actions (not dry_run, not blocked)
                if run.outcome in ("success", "failed"):
                    # Determine confidence from plan constraints or default
                    confidence = 0.5
                    if run.outcome == "success" and run.artifacts_created:
                        confidence = 0.7  # Higher confidence for successful artifact creation

                    # Get action_id from autonomy precheck for provisional tracking
                    action_id = run.plan_constraints.get("_autonomy_action_id")

                    record_outcome(
                        action=run.plan_selected,
                        success=(run.outcome == "success"),
                        confidence=confidence,
                        was_reverted=False,  # Will be updated later if reverted
                        action_id=action_id,  # For time-window tracking
                        provisional=True  # Successes go through maturation
                    )
                    outcome_type = "provisional success" if run.outcome == "success" else "failure"
                    run.notes.append(f"Autonomy: recorded {outcome_type} for {run.autonomy_domain}")
            except Exception as e:
                run.notes.append(f"Autonomy outcome recording failed: {str(e)[:50]}")

        # === Autonomy heartbeat: check for matured rewards ===
        if AUTONOMY_AVAILABLE:
            try:
                store = get_reputation_store()
                # Only run maturation if there are pending rewards
                pending = [r for r in store.pending_rewards if not r.cancelled and not r.matured]
                if pending:
                    result = run_maturation(store)
                    if result.get("matured_count", 0) > 0:
                        run.notes.append(f"Autonomy: {result['matured_count']} rewards matured")
            except Exception:
                pass  # Don't fail the run for maturation errors

        # Write run log
        run_path = self.runs_dir / f"{run.run_id}.json"
        run_dict = self._run_to_dict(run)

        try:
            with open(run_path, "w", encoding="utf-8") as f:
                json.dump(run_dict, f, indent=2, ensure_ascii=False)
        except Exception as e:
            run.notes.append(f"Failed to write run log: {e}")

        # Return summary
        return {
            "run_id": run.run_id,
            "run_path": str(run_path),
            "intent": run.intent_normalized,
            "plan": run.plan_selected,
            "plan_type": run.plan_type,
            "rules_applied": run.rules_applicable,
            "constraints": run.plan_constraints,
            "outcome": run.outcome,
            "error": run.error,
            "artifacts_created": run.artifacts_created,
            "duration_ms": run.duration_ms,
            "dry_run": run.dry_run
        }

    def _run_to_dict(self, run: RunLog) -> dict:
        """Convert RunLog to nested dict matching spec."""
        return {
            "run_id": run.run_id,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "intent": run.intent,
            "intent_normalized": run.intent_normalized,
            "args": run.args,
            "dry_run": run.dry_run,
            "sensitivity": run.sensitivity,

            "rules": {
                "checked": run.rules_checked,
                "applicable": run.rules_applicable,
                "decisions": run.rules_decisions
            },

            "plan": {
                "selected": run.plan_selected,
                "type": run.plan_type,
                "reason": run.plan_reason,
                "constraints": run.plan_constraints
            },

            "execution": {
                "tool_calls": run.tool_calls,
                "outcome": run.outcome,
                "error": run.error,
                "duration_ms": run.duration_ms,
                "autonomy_block_events": run.autonomy_block_events
            },

            "results": {
                "artifacts_created": run.artifacts_created,
                "artifact_paths": run.artifact_paths,
                "notes": run.notes
            },

            "meta": {
                "server_build": run.server_build,
                "schema_version": run.schema_version
            }
        }

    def get_run(self, run_id: str) -> Optional[dict]:
        """Retrieve a run log by ID."""
        run_path = self.runs_dir / f"{run_id}.json"
        if not run_path.exists():
            return None
        try:
            with open(run_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def list_runs(self, limit: int = 20, outcome: Optional[str] = None) -> list:
        """List recent runs."""
        runs = []
        for run_file in sorted(self.runs_dir.glob("run_*.json"), reverse=True):
            if len(runs) >= limit:
                break
            try:
                with open(run_file, "r", encoding="utf-8") as f:
                    run = json.load(f)
                    if outcome and run.get("execution", {}).get("outcome") != outcome:
                        continue
                    runs.append({
                        "run_id": run.get("run_id"),
                        "intent": run.get("intent_normalized"),
                        "outcome": run.get("execution", {}).get("outcome"),
                        "started_at": run.get("started_at"),
                        "duration_ms": run.get("execution", {}).get("duration_ms")
                    })
            except Exception:
                continue
        return runs
