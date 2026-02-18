"""
Autonomy Ladder + Reputation Score v0
=====================================

The control system that turns "Duro can do things" into
"Duro earns permission to do things."

Autonomy Levels:
- L0 Observe: read/search only
- L1 Propose: can write plans/patch diffs but no execution
- L2 Safe Exec: can run safe commands + edit files (no destructive ops)
- L3 Risk Exec: destructive ops require approval + extra gates
- L4 Trusted Domain: L3 but only for domains where score is high

Reputation Score:
- Computed from append-only validation history
- Per-domain scoring (incident_rca, code_changes, refactors, etc.)
- Feeds autonomy level decisions

Phase 4 - Governance Infrastructure
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Any, Tuple
import json
import os
from pathlib import Path


# === AUTONOMY LEVELS ===

class AutonomyLevel(IntEnum):
    """
    Autonomy levels with hard capability gates.
    Higher levels include all capabilities of lower levels.
    """
    L0_OBSERVE = 0      # Read/search only
    L1_PROPOSE = 1      # Can write plans/diffs, no execution
    L2_SAFE_EXEC = 2    # Safe commands + file edits
    L3_RISK_EXEC = 3    # Destructive ops with approval
    L4_TRUSTED = 4      # Domain-specific trust, minimal gates


# Action risk levels
class ActionRisk(Enum):
    """Risk classification for actions."""
    READ = "read"           # L0+ - reading files, searching
    PLAN = "plan"           # L1+ - writing plans, proposals
    SAFE_WRITE = "safe"     # L2+ - editing files, safe commands
    DESTRUCTIVE = "risk"    # L3+ - delete, overwrite, deploy
    CRITICAL = "critical"   # L4+ with high domain score

    @classmethod
    def from_action(cls, action: str, context: Dict[str, Any] = None) -> "ActionRisk":
        """
        Classify action risk using enum-based matching.

        This is the canonical entry point for action risk classification.
        Uses exact matches first, then pattern matching, then context hints.
        """
        context = context or {}

        # === EXACT MATCH SETS ===
        # Ordered by specificity - check destructive first
        DESTRUCTIVE_ACTIONS = {
            # File operations
            "delete_file", "remove_file", "rm", "unlink",
            # Artifact operations
            "delete_artifact", "duro_delete_artifact",
            # Database
            "drop_table", "drop_database", "truncate", "delete_row",
            # Git destructive
            "git_push", "git_push_force", "git_reset_hard", "force_push",
            # Deploy/Prod
            "deploy", "deploy_prod", "deploy_production",
            # Bash (inherently risky)
            "bash_command", "shell_exec", "run_command",
        }

        SAFE_WRITE_ACTIONS = {
            # File editing
            "edit_file", "write_file", "create_file", "patch_file",
            # Artifact storage
            "store_fact", "store_decision", "store_incident",
            "store_change", "store_checklist", "store_design_ref",
            "save_memory", "save_learning", "log_task", "log_failure",
            # Code generation
            "scaffold", "generate_code", "refactor",
            # Git safe
            "git_commit", "git_add", "git_checkout",
        }

        PLAN_ACTIONS = {
            "plan", "propose", "draft", "estimate", "compare",
            "adversarial_planning", "suggest", "design", "architect",
            "review", "analyze_approach",
        }

        READ_ACTIONS = {
            "read_file", "glob_files", "grep", "search", "query",
            "get_artifact", "list_artifacts", "batch_get",
            "get_screenshot", "read_webpage", "web_search",
            "duro_query_memory", "duro_semantic_search", "duro_get_artifact",
        }

        action_lower = action.lower().strip()

        # Exact match (highest priority)
        if action_lower in DESTRUCTIVE_ACTIONS:
            return cls.DESTRUCTIVE
        if action_lower in SAFE_WRITE_ACTIONS:
            return cls.SAFE_WRITE
        if action_lower in PLAN_ACTIONS:
            return cls.PLAN
        if action_lower in READ_ACTIONS:
            return cls.READ

        # === PATTERN MATCHING (more precise than "in") ===
        # Destructive patterns - action must START with or END with these
        destructive_prefixes = ("delete_", "remove_", "drop_", "destroy_", "force_")
        destructive_suffixes = ("_delete", "_remove", "_drop", "_destroy", "_force")
        if any(action_lower.startswith(p) for p in destructive_prefixes):
            return cls.DESTRUCTIVE
        if any(action_lower.endswith(s) for s in destructive_suffixes):
            return cls.DESTRUCTIVE

        # Safe write patterns
        safe_prefixes = ("edit_", "write_", "update_", "store_", "save_", "create_")
        safe_suffixes = ("_edit", "_write", "_update", "_store", "_save", "_create")
        if any(action_lower.startswith(p) for p in safe_prefixes):
            return cls.SAFE_WRITE
        if any(action_lower.endswith(s) for s in safe_suffixes):
            return cls.SAFE_WRITE

        # Plan patterns
        plan_prefixes = ("plan_", "propose_", "draft_", "design_")
        plan_suffixes = ("_plan", "_proposal", "_draft")
        if any(action_lower.startswith(p) for p in plan_prefixes):
            return cls.PLAN
        if any(action_lower.endswith(s) for s in plan_suffixes):
            return cls.PLAN

        # Read patterns
        read_prefixes = ("read_", "get_", "fetch_", "query_", "list_", "search_")
        read_suffixes = ("_read", "_get", "_fetch", "_query", "_list", "_search")
        if any(action_lower.startswith(p) for p in read_prefixes):
            return cls.READ
        if any(action_lower.endswith(s) for s in read_suffixes):
            return cls.READ

        # === CONTEXT HINTS (override patterns) ===
        if context.get("is_destructive"):
            return cls.DESTRUCTIVE
        if context.get("affects_production") and not context.get("is_reversible", True):
            return cls.CRITICAL
        if context.get("affects_production"):
            return cls.DESTRUCTIVE

        # Default to safe write for unknown (conservative)
        return cls.SAFE_WRITE


# Capability mapping: what each level can do
LEVEL_CAPABILITIES = {
    AutonomyLevel.L0_OBSERVE: {
        ActionRisk.READ,
    },
    AutonomyLevel.L1_PROPOSE: {
        ActionRisk.READ,
        ActionRisk.PLAN,
    },
    AutonomyLevel.L2_SAFE_EXEC: {
        ActionRisk.READ,
        ActionRisk.PLAN,
        ActionRisk.SAFE_WRITE,
    },
    AutonomyLevel.L3_RISK_EXEC: {
        ActionRisk.READ,
        ActionRisk.PLAN,
        ActionRisk.SAFE_WRITE,
        ActionRisk.DESTRUCTIVE,
    },
    AutonomyLevel.L4_TRUSTED: {
        ActionRisk.READ,
        ActionRisk.PLAN,
        ActionRisk.SAFE_WRITE,
        ActionRisk.DESTRUCTIVE,
        ActionRisk.CRITICAL,
    },
}


# === REPUTATION SCORING ===

@dataclass
class DomainScore:
    """Reputation score for a specific domain."""
    domain: str
    score: float = 0.5  # Start neutral
    total_closures: int = 0
    total_reopens: int = 0
    total_reverts: int = 0
    confident_actions: int = 0
    confident_reverts: int = 0
    last_updated: str = ""

    @property
    def reopen_rate(self) -> float:
        """Decisions/incidents reopened ÷ closed."""
        if self.total_closures == 0:
            return 0.0
        return self.total_reopens / self.total_closures

    @property
    def revert_rate(self) -> float:
        """Confident actions later reverted."""
        if self.confident_actions == 0:
            return 0.0
        return self.confident_reverts / self.confident_actions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "score": round(self.score, 3),
            "reopen_rate": round(self.reopen_rate, 3),
            "revert_rate": round(self.revert_rate, 3),
            "total_closures": self.total_closures,
            "total_reopens": self.total_reopens,
            "confident_actions": self.confident_actions,
            "confident_reverts": self.confident_reverts,
            "last_updated": self.last_updated,
        }


# Score adjustment constants (keep it dumb at first)
SCORE_ADJUSTMENTS = {
    "successful_closure": +0.02,    # Clean closure without reopen
    "reopen": -0.08,                # Had to reopen a decision/incident
    "confident_revert": -0.12,      # Confident action later reverted
    "validation_success": +0.01,    # Decision validated as working
    "validation_failure": -0.05,    # Decision validated as failed
}

# Score bounds
SCORE_MIN = 0.0
SCORE_MAX = 1.0

# Domain score thresholds for autonomy
DOMAIN_THRESHOLDS = {
    AutonomyLevel.L4_TRUSTED: 0.75,   # Need high trust for L4
    AutonomyLevel.L3_RISK_EXEC: 0.50, # Medium trust for L3
    AutonomyLevel.L2_SAFE_EXEC: 0.30, # Low bar for safe ops
    AutonomyLevel.L1_PROPOSE: 0.10,   # Very low bar for proposals
    AutonomyLevel.L0_OBSERVE: 0.00,   # Always allowed
}


@dataclass
class PendingReward:
    """A provisional success waiting to mature into a real reward."""
    action_id: str
    domain: str
    confidence: float
    recorded_at: str
    mature_at: str  # ISO datetime when this can become a real reward
    cancelled: bool = False
    matured: bool = False


# Default maturation window (days)
REWARD_MATURATION_DAYS = 7


@dataclass
class ReputationStore:
    """
    Persistent reputation scores per domain.
    Uses existing Duro memory infrastructure.
    """
    scores: Dict[str, DomainScore] = field(default_factory=dict)
    global_score: float = 0.5  # Overall reputation
    store_path: str = ""
    pending_rewards: List[PendingReward] = field(default_factory=list)

    def get_domain_score(self, domain: str) -> DomainScore:
        """Get or create score for a domain."""
        if domain not in self.scores:
            self.scores[domain] = DomainScore(
                domain=domain,
                last_updated=datetime.now().isoformat()
            )
        return self.scores[domain]

    def update_score(
        self,
        domain: str,
        event: str,
        confidence: float = 0.5
    ) -> Tuple[float, float]:
        """
        Update domain score based on event.

        Returns: (old_score, new_score)
        """
        ds = self.get_domain_score(domain)
        old_score = ds.score

        adjustment = SCORE_ADJUSTMENTS.get(event, 0.0)

        # Track metrics
        if event == "successful_closure":
            ds.total_closures += 1
        elif event == "reopen":
            ds.total_reopens += 1
        elif event == "confident_revert":
            ds.confident_reverts += 1
            if confidence >= 0.7:
                ds.confident_actions += 1
        elif event in ("validation_success", "validation_failure"):
            if confidence >= 0.7:
                ds.confident_actions += 1

        # Apply adjustment with confidence weighting
        weighted_adjustment = adjustment * (0.5 + confidence * 0.5)
        ds.score = max(SCORE_MIN, min(SCORE_MAX, ds.score + weighted_adjustment))
        ds.last_updated = datetime.now().isoformat()

        # Update global score (weighted average of all domains)
        self._update_global_score()

        return old_score, ds.score

    def _update_global_score(self):
        """Recalculate global score from domain scores."""
        if not self.scores:
            self.global_score = 0.5
            return

        # Weight by activity (more closures = more weight)
        total_weight = 0
        weighted_sum = 0

        for ds in self.scores.values():
            weight = max(1, ds.total_closures)
            weighted_sum += ds.score * weight
            total_weight += weight

        self.global_score = weighted_sum / total_weight if total_weight > 0 else 0.5

    def get_allowed_level(self, domain: str) -> AutonomyLevel:
        """Get maximum autonomy level allowed for a domain."""
        ds = self.get_domain_score(domain)

        for level in reversed(list(AutonomyLevel)):
            threshold = DOMAIN_THRESHOLDS.get(level, 0.0)
            if ds.score >= threshold:
                return level

        return AutonomyLevel.L0_OBSERVE

    # === Time-window rewards ===

    def record_provisional_success(
        self,
        action_id: str,
        domain: str,
        confidence: float = 0.5,
        maturation_days: int = None
    ) -> PendingReward:
        """
        Record a provisional success that will mature into a real reward.

        The reward only applies if not cancelled (by reopen/revert) before maturation.
        """
        now = datetime.now()
        days = maturation_days or REWARD_MATURATION_DAYS
        mature_at = now + timedelta(days=days)

        reward = PendingReward(
            action_id=action_id,
            domain=domain,
            confidence=confidence,
            recorded_at=now.isoformat(),
            mature_at=mature_at.isoformat()
        )
        self.pending_rewards.append(reward)
        return reward

    def cancel_pending_reward(self, action_id: str, apply_penalty: bool = True) -> bool:
        """
        Cancel a pending reward (on reopen/revert).

        If apply_penalty is True, also applies the reopen penalty.
        Returns True if a pending reward was found and cancelled.
        """
        for reward in self.pending_rewards:
            if reward.action_id == action_id and not reward.cancelled and not reward.matured:
                reward.cancelled = True

                if apply_penalty:
                    self.update_score(reward.domain, "reopen", reward.confidence)

                return True
        return False

    def mature_pending_rewards(self) -> Dict[str, Any]:
        """
        Process all pending rewards that have passed their maturation date.

        Call this periodically (e.g., on startup, daily job).
        Returns summary of matured rewards.
        """
        now = datetime.now()
        matured = []
        still_pending = []

        for reward in self.pending_rewards:
            if reward.cancelled or reward.matured:
                continue

            mature_at = datetime.fromisoformat(reward.mature_at)
            if now >= mature_at:
                # Matured! Apply the reward
                old_score, new_score = self.update_score(
                    reward.domain,
                    "successful_closure",
                    reward.confidence
                )
                reward.matured = True
                matured.append({
                    "action_id": reward.action_id,
                    "domain": reward.domain,
                    "old_score": old_score,
                    "new_score": new_score
                })
            else:
                still_pending.append(reward.action_id)

        return {
            "matured_count": len(matured),
            "matured": matured,
            "still_pending": len(still_pending),
            "total_pending": len([r for r in self.pending_rewards if not r.cancelled and not r.matured])
        }

    def get_pending_rewards(self, domain: str = None) -> List[PendingReward]:
        """Get active (non-cancelled, non-matured) pending rewards."""
        active = [r for r in self.pending_rewards if not r.cancelled and not r.matured]
        if domain:
            active = [r for r in active if r.domain == domain]
        return active

    def save(self, path: str = None):
        """Persist scores to disk."""
        save_path = path or self.store_path
        if not save_path:
            return

        data = {
            "global_score": self.global_score,
            "last_updated": datetime.now().isoformat(),
            "domains": {
                domain: ds.to_dict()
                for domain, ds in self.scores.items()
            },
            "pending_rewards": [
                {
                    "action_id": r.action_id,
                    "domain": r.domain,
                    "confidence": r.confidence,
                    "recorded_at": r.recorded_at,
                    "mature_at": r.mature_at,
                    "cancelled": r.cancelled,
                    "matured": r.matured
                }
                for r in self.pending_rewards
            ]
        }

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "ReputationStore":
        """Load scores from disk."""
        store = cls(store_path=path)

        if not os.path.exists(path):
            return store

        try:
            with open(path, 'r') as f:
                data = json.load(f)

            store.global_score = data.get("global_score", 0.5)

            for domain, ds_data in data.get("domains", {}).items():
                store.scores[domain] = DomainScore(
                    domain=domain,
                    score=ds_data.get("score", 0.5),
                    total_closures=ds_data.get("total_closures", 0),
                    total_reopens=ds_data.get("total_reopens", 0),
                    total_reverts=ds_data.get("total_reverts", 0),
                    confident_actions=ds_data.get("confident_actions", 0),
                    confident_reverts=ds_data.get("confident_reverts", 0),
                    last_updated=ds_data.get("last_updated", ""),
                )

            # Load pending rewards
            for pr_data in data.get("pending_rewards", []):
                store.pending_rewards.append(PendingReward(
                    action_id=pr_data["action_id"],
                    domain=pr_data["domain"],
                    confidence=pr_data["confidence"],
                    recorded_at=pr_data["recorded_at"],
                    mature_at=pr_data["mature_at"],
                    cancelled=pr_data.get("cancelled", False),
                    matured=pr_data.get("matured", False)
                ))
        except Exception:
            pass

        return store


# === ENFORCEMENT ===

@dataclass
class PermissionCheck:
    """Result of an autonomy permission check."""
    allowed: bool
    required_level: AutonomyLevel
    current_level: AutonomyLevel
    domain: str
    domain_score: float
    action_risk: ActionRisk
    reason: str
    downgrade_to: Optional[str] = None  # "propose" if must downgrade
    requires_approval: bool = False


@dataclass
class ApprovalToken:
    """One-shot approval token with audit trail."""
    action_id: str
    granted_at: str
    expires_at: datetime
    used_at: Optional[str] = None
    used_by: Optional[str] = None
    reason: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid (not expired, not used)."""
        return self.used_at is None and self.expires_at > datetime.now()


class AutonomyEnforcer:
    """
    Enforcement hook for the orchestrator.
    Checks actions against autonomy levels and reputation scores.
    """

    def __init__(self, store: ReputationStore, base_level: AutonomyLevel = AutonomyLevel.L2_SAFE_EXEC):
        self.store = store
        self.base_level = base_level  # Default autonomy level
        self.approval_tokens: Dict[str, ApprovalToken] = {}  # action_id -> token
        self.approval_log: List[Dict[str, Any]] = []  # Audit trail

    def check_permission(
        self,
        action_risk: ActionRisk,
        domain: str,
        action_id: str = None,
        consume_token: bool = True
    ) -> PermissionCheck:
        """
        Check if an action is permitted given current autonomy state.

        Args:
            action_risk: Risk level of the action
            domain: Domain context (e.g., "code_changes", "incident_rca")
            action_id: Optional ID for approval token lookup
            consume_token: If True and token is used, mark it as consumed (one-shot)

        Returns:
            PermissionCheck with decision and reasoning
        """
        # Get domain-specific allowed level
        domain_level = self.store.get_allowed_level(domain)
        ds = self.store.get_domain_score(domain)

        # Use lower of base level and domain level
        effective_level = min(self.base_level, domain_level)

        # Check capabilities
        allowed_actions = LEVEL_CAPABILITIES.get(effective_level, set())

        # Check for approval token (one-shot: valid only if not used)
        has_approval = False
        if action_id and action_id in self.approval_tokens:
            token = self.approval_tokens[action_id]
            if token.is_valid:
                has_approval = True
            elif token.expires_at <= datetime.now():
                # Expired - cleanup
                del self.approval_tokens[action_id]

        # Determine required level for this action
        required_level = AutonomyLevel.L0_OBSERVE
        for level, capabilities in LEVEL_CAPABILITIES.items():
            if action_risk in capabilities:
                required_level = level
                break

        # Decision
        if action_risk in allowed_actions:
            return PermissionCheck(
                allowed=True,
                required_level=required_level,
                current_level=effective_level,
                domain=domain,
                domain_score=ds.score,
                action_risk=action_risk,
                reason=f"Action permitted at L{effective_level.value}"
            )

        # Not directly allowed - check if approval token exists
        if has_approval and action_risk == ActionRisk.DESTRUCTIVE:
            # Consume the token if requested (one-shot)
            if consume_token:
                self.use_approval(action_id, used_by="autonomy_enforcer")

            return PermissionCheck(
                allowed=True,
                required_level=required_level,
                current_level=effective_level,
                domain=domain,
                domain_score=ds.score,
                action_risk=action_risk,
                reason="Action permitted via approval token (one-shot consumed)"
            )

        # Not allowed - determine downgrade
        if action_risk in (ActionRisk.DESTRUCTIVE, ActionRisk.CRITICAL):
            return PermissionCheck(
                allowed=False,
                required_level=required_level,
                current_level=effective_level,
                domain=domain,
                domain_score=ds.score,
                action_risk=action_risk,
                reason=f"Domain score {ds.score:.2f} below threshold for L{required_level.value}",
                downgrade_to="propose",
                requires_approval=True
            )

        return PermissionCheck(
            allowed=False,
            required_level=required_level,
            current_level=effective_level,
            domain=domain,
            domain_score=ds.score,
            action_risk=action_risk,
            reason=f"Insufficient autonomy level (have L{effective_level.value}, need L{required_level.value})"
        )

    def grant_approval(self, action_id: str, duration_seconds: int = 300, reason: str = None):
        """
        Grant one-shot approval token for a specific action.

        Token can only be used once. Expires after duration_seconds.
        """
        now = datetime.now()
        expiry = now + timedelta(seconds=duration_seconds)

        token = ApprovalToken(
            action_id=action_id,
            granted_at=now.isoformat(),
            expires_at=expiry,
            reason=reason
        )

        self.approval_tokens[action_id] = token

        # Audit trail
        self.approval_log.append({
            "event": "grant",
            "action_id": action_id,
            "timestamp": now.isoformat(),
            "expires_at": expiry.isoformat(),
            "reason": reason
        })

    def use_approval(self, action_id: str, used_by: str = "orchestrator") -> bool:
        """
        Mark an approval token as used (one-shot consumption).

        Returns True if token was valid and consumed, False otherwise.
        """
        if action_id not in self.approval_tokens:
            return False

        token = self.approval_tokens[action_id]
        if not token.is_valid:
            return False

        # Mark as used
        now = datetime.now()
        token.used_at = now.isoformat()
        token.used_by = used_by

        # Audit trail
        self.approval_log.append({
            "event": "use",
            "action_id": action_id,
            "timestamp": now.isoformat(),
            "used_by": used_by
        })

        return True

    def revoke_approval(self, action_id: str, reason: str = None):
        """Revoke an approval token."""
        if action_id in self.approval_tokens:
            # Audit trail
            self.approval_log.append({
                "event": "revoke",
                "action_id": action_id,
                "timestamp": datetime.now().isoformat(),
                "reason": reason
            })
            del self.approval_tokens[action_id]

    def get_approval_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent approval audit log entries."""
        return self.approval_log[-limit:]


# === DOMAIN CLASSIFICATION ===

# Map action types to domains
ACTION_DOMAINS = {
    # Code operations
    "edit_file": "code_changes",
    "write_file": "code_changes",
    "delete_file": "code_changes",
    "refactor": "refactors",
    "scaffold": "code_changes",

    # Incident/debug operations
    "store_incident": "incident_rca",
    "debug_gate": "incident_rca",
    "query_recent_changes": "incident_rca",

    # Decision operations
    "store_decision": "decisions",
    "validate_decision": "decisions",
    "review_decision": "decisions",

    # Design operations
    "verify_design": "design_verification",
    "batch_design": "design_verification",

    # Memory operations
    "store_fact": "knowledge",
    "delete_artifact": "knowledge",

    # System operations
    "run_skill": "skill_execution",
    "bash_command": "system_ops",
    "deploy": "deployments",
}


def classify_action_domain(action: str) -> str:
    """Classify an action into its domain."""
    return ACTION_DOMAINS.get(action, "general")


def classify_action_risk(action: str, context: Dict[str, Any] = None) -> ActionRisk:
    """
    Classify the risk level of an action.

    Delegates to ActionRisk.from_action() which uses enum-based matching.
    This wrapper exists for backward compatibility.

    Context can provide hints like:
    - is_destructive: bool
    - affects_production: bool
    - is_reversible: bool
    """
    return ActionRisk.from_action(action, context)


# === INTEGRATION WITH VALIDATION HISTORY ===

def compute_scores_from_history(
    query_func,
    store: ReputationStore
) -> Dict[str, Any]:
    """
    Compute reputation scores from existing validation history.

    Args:
        query_func: Function to query artifacts (e.g., duro_query_memory)
        store: ReputationStore to update

    Returns:
        Summary of score updates
    """
    updates = {
        "domains_updated": [],
        "events_processed": 0,
        "errors": []
    }

    try:
        # Query decisions with validation history
        decisions = query_func(artifact_type="decision", limit=500)

        for decision in decisions.get("artifacts", []):
            domain = classify_action_domain(decision.get("context", "general"))

            # Check validation status
            status = decision.get("status", "pending")
            confidence = decision.get("confidence", 0.5)

            if status == "validated":
                store.update_score(domain, "validation_success", confidence)
                updates["events_processed"] += 1
            elif status == "reversed":
                store.update_score(domain, "validation_failure", confidence)
                if confidence >= 0.7:
                    store.update_score(domain, "confident_revert", confidence)
                updates["events_processed"] += 1
            elif status == "superseded":
                store.update_score(domain, "successful_closure", confidence)
                updates["events_processed"] += 1

            if domain not in updates["domains_updated"]:
                updates["domains_updated"].append(domain)

        # Query incidents for reopen tracking
        incidents = query_func(artifact_type="incident", limit=200)

        for incident in incidents.get("artifacts", []):
            domain = "incident_rca"

            # Check if incident was reopened (has related_incidents linking back)
            if incident.get("reopened"):
                store.update_score(domain, "reopen", 0.8)
                updates["events_processed"] += 1
            else:
                store.update_score(domain, "successful_closure", 0.7)
                updates["events_processed"] += 1

            if domain not in updates["domains_updated"]:
                updates["domains_updated"].append(domain)

    except Exception as e:
        updates["errors"].append(str(e))

    return updates


# === CONVENIENCE FUNCTIONS ===

# Global instances (lazy loaded)
_reputation_store: Optional[ReputationStore] = None
_autonomy_enforcer: Optional[AutonomyEnforcer] = None


def get_reputation_store(store_path: str = None) -> ReputationStore:
    """Get or create the global reputation store."""
    global _reputation_store

    if _reputation_store is None:
        default_path = os.path.expanduser("~/.agent/memory/reputation_scores.json")
        _reputation_store = ReputationStore.load(store_path or default_path)

    return _reputation_store


def get_autonomy_enforcer() -> AutonomyEnforcer:
    """Get or create the global autonomy enforcer (preserves approval tokens)."""
    global _autonomy_enforcer

    if _autonomy_enforcer is None:
        store = get_reputation_store()
        _autonomy_enforcer = AutonomyEnforcer(store)

    return _autonomy_enforcer


def check_action(
    action: str,
    context: Dict[str, Any] = None,
    action_id: str = None,
    consume_token: bool = True
) -> PermissionCheck:
    """
    Quick check if an action is permitted.

    Usage:
        check = check_action("delete_file", {"path": "/some/file"})
        if not check.allowed:
            if check.requires_approval:
                # Request approval
            else:
                # Downgrade to propose

    Args:
        action: The action being performed
        context: Optional context hints
        action_id: Optional ID for approval token lookup
        consume_token: If True and token is used, consume it (one-shot)
    """
    enforcer = get_autonomy_enforcer()

    domain = classify_action_domain(action)
    risk = classify_action_risk(action, context)

    # Use action as action_id if not provided
    effective_action_id = action_id or f"{action}_{domain}"

    return enforcer.check_permission(risk, domain, effective_action_id, consume_token)


def record_outcome(
    action: str,
    success: bool,
    confidence: float = 0.5,
    was_reverted: bool = False,
    action_id: str = None,
    store: ReputationStore = None,
    provisional: bool = True  # New: use time-window for successes
):
    """
    Record the outcome of an action to update reputation.

    Call this after an action completes to build reputation history.

    Args:
        action: The action description
        success: Whether the action succeeded
        confidence: Confidence level (0-1)
        was_reverted: Whether the action was later reverted
        action_id: Unique action identifier (for provisional tracking)
        store: ReputationStore instance
        provisional: If True, successes become pending rewards (time-window)
    """
    store = store or get_reputation_store()
    domain = classify_action_domain(action)

    # Failures and reverts apply immediately (no maturation needed)
    if was_reverted and confidence >= 0.7:
        store.update_score(domain, "confident_revert", confidence)
        store.save()
    elif not success:
        store.update_score(domain, "validation_failure", confidence)
        store.save()
    elif success:
        # Successes go through provisional rewards (time-window validation)
        if provisional and action_id:
            store.record_provisional_success(action_id, domain, confidence)
        else:
            # Immediate reward (legacy behavior or explicit skip)
            store.update_score(domain, "successful_closure", confidence)
            store.save()


def handle_reopen_event(
    artifact_type: str,
    artifact_id: str,
    linked_action_id: str = None,
    store: ReputationStore = None
) -> Dict[str, Any]:
    """
    Handle a reopen event (decision reversed, incident re-triggered).

    Reopen events cancel pending rewards and apply penalties.
    This is the core of "trust but verify" - closures that don't stick
    hurt reputation more than not closing in the first place.

    Args:
        artifact_type: "decision" or "incident"
        artifact_id: The artifact ID being reopened
        linked_action_id: Action ID that originally closed it
        store: ReputationStore instance

    Returns:
        {cancelled: bool, penalty_applied: bool, domain: str}
    """
    store = store or get_reputation_store()

    # Map artifact types to domains
    domain_map = {
        "decision": "decisions",
        "incident": "incident_rca",
    }
    domain = domain_map.get(artifact_type, "general")

    result = {
        "cancelled": False,
        "penalty_applied": False,
        "domain": domain,
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
    }

    # Try to cancel pending reward if linked action exists
    if linked_action_id:
        cancelled = store.cancel_pending_reward(linked_action_id, apply_penalty=True)
        result["cancelled"] = cancelled
        result["penalty_applied"] = cancelled  # Penalty applied via cancel

    # If no linked action or reward not found, still apply reopen penalty
    if not result["penalty_applied"]:
        store.update_score(domain, "reopen", 0.5)  # Generic reopen penalty
        result["penalty_applied"] = True

    store.save()
    return result


def run_maturation(store: ReputationStore = None) -> Dict[str, Any]:
    """
    Process pending rewards that have matured.

    Call this periodically (e.g., daily, on session start).
    Returns summary of what was processed.
    """
    store = store or get_reputation_store()
    return store.mature_pending_rewards()


# === CLI ===

if __name__ == "__main__":
    print("Autonomy Ladder + Reputation Score v0")
    print("=" * 50)

    print("\nAutonomy Levels:")
    for level in AutonomyLevel:
        caps = LEVEL_CAPABILITIES[level]
        cap_names = [c.value for c in caps]
        threshold = DOMAIN_THRESHOLDS[level]
        print(f"  L{level.value} {level.name}: {cap_names} (threshold: {threshold})")

    print("\nScore Adjustments:")
    for event, adj in SCORE_ADJUSTMENTS.items():
        sign = "+" if adj > 0 else ""
        print(f"  {event}: {sign}{adj}")

    print("\nExample domain classifications:")
    for action in ["edit_file", "delete_file", "store_decision", "deploy"]:
        domain = classify_action_domain(action)
        risk = classify_action_risk(action)
        print(f"  {action}: domain={domain}, risk={risk.value}")

    print("\nExample permission check:")
    store = ReputationStore()
    store.scores["code_changes"] = DomainScore(
        domain="code_changes",
        score=0.65,
        total_closures=20,
        total_reopens=2
    )

    enforcer = AutonomyEnforcer(store)
    check = enforcer.check_permission(ActionRisk.DESTRUCTIVE, "code_changes")
    print(f"  Destructive action in code_changes (score=0.65):")
    print(f"    Allowed: {check.allowed}")
    print(f"    Reason: {check.reason}")
    print(f"    Requires approval: {check.requires_approval}")
