"""Security endpoints - audit log, policy gate, autonomy system."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter()

# Paths to Duro security files
DURO_HOME = Path.home() / ".agent"
AUDIT_LOG_PATH = DURO_HOME / "security" / "audit.jsonl"
GATE_LOG_PATH = DURO_HOME / "security" / "gate_audit.jsonl"
REPUTATION_PATH = DURO_HOME / "autonomy" / "reputation.json"
APPROVALS_PATH = DURO_HOME / "autonomy" / "approvals.json"


def _read_jsonl(path: Path, limit: int = 100, offset: int = 0) -> list[dict]:
    """Read last N lines from a JSONL file."""
    if not path.exists():
        return []

    lines = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            # Get from end, reverse so most recent first
            start = max(0, len(all_lines) - limit - offset)
            end = len(all_lines) - offset
            for line in reversed(all_lines[start:end]):
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return []
    return lines[:limit]


def _read_json(path: Path) -> dict | None:
    """Read JSON file."""
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


@router.get("/security/audit")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: str | None = None,
    severity: str | None = None,
    decision: str | None = None,
) -> dict[str, Any]:
    """Get security audit log entries."""
    entries = _read_jsonl(AUDIT_LOG_PATH, limit=limit * 2, offset=offset)  # Read more to filter

    # Filter
    filtered = []
    for entry in entries:
        if event_type and entry.get('event_type') != event_type:
            continue
        if severity and entry.get('severity') != severity:
            continue
        if decision and entry.get('decision') != decision:
            continue
        filtered.append(entry)
        if len(filtered) >= limit:
            break

    return {
        "entries": filtered,
        "total": len(entries),
        "has_more": len(entries) > len(filtered),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/security/gate")
async def get_gate_audit(
    limit: int = Query(50, ge=1, le=200),
    decision: str | None = None,
    tool: str | None = None,
) -> dict[str, Any]:
    """Get policy gate audit log."""
    entries = _read_jsonl(GATE_LOG_PATH, limit=limit * 2)

    # Filter and count stats
    filtered = []
    stats = {"ALLOW": 0, "DENY": 0, "NEED_APPROVAL": 0}

    for entry in entries:
        d = entry.get('decision', 'ALLOW')
        if d in stats:
            stats[d] += 1

        if decision and d != decision:
            continue
        if tool and entry.get('tool') != tool:
            continue
        if len(filtered) < limit:
            filtered.append(entry)

    return {
        "entries": filtered,
        "stats": stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/security/autonomy")
async def get_autonomy_status() -> dict[str, Any]:
    """Get autonomy system status including reputation."""
    reputation = _read_json(REPUTATION_PATH) or {}
    approvals = _read_json(APPROVALS_PATH) or {}

    # Format domain scores
    domains = []
    for domain, data in reputation.get("domains", {}).items():
        domains.append({
            "domain": domain,
            "score": data.get("score", 0.5),
            "total_actions": data.get("total_actions", 0),
            "success_rate": data.get("success_rate", 0),
            "last_action": data.get("last_action"),
        })

    # Get active approvals (filter expired)
    now = datetime.now(timezone.utc)
    active_approvals = []
    for action_id, approval in approvals.items():
        expires_at = approval.get("expires_at")
        if expires_at:
            try:
                exp_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if exp_time > now:
                    active_approvals.append({
                        "action_id": action_id,
                        "expires_at": expires_at,
                        "reason": approval.get("reason"),
                    })
            except (ValueError, TypeError):
                continue

    return {
        "overall_score": reputation.get("overall_score", 0.5),
        "domains": sorted(domains, key=lambda x: x["score"], reverse=True),
        "active_approvals": active_approvals,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/security/layer6")
async def get_layer6_status() -> dict[str, Any]:
    """Get Layer 6 security status (intent guard + prompt firewall)."""
    # These would be read from actual state files in production
    return {
        "intent_guard": {
            "active_tokens": 0,
            "untrusted_content": False,
        },
        "prompt_firewall": {
            "blocked_count": 0,
            "vault_entries": 0,
            "sanitized_count": 0,
        },
        "status": "active",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/security/summary")
async def get_security_summary() -> dict[str, Any]:
    """Get summary of all security components."""
    audit = _read_jsonl(AUDIT_LOG_PATH, limit=100)
    gate = _read_jsonl(GATE_LOG_PATH, limit=100)
    autonomy = await get_autonomy_status()

    # Count severities
    severity_counts = {"info": 0, "warn": 0, "high": 0, "critical": 0}
    for entry in audit:
        sev = entry.get("severity", "info")
        if sev in severity_counts:
            severity_counts[sev] += 1

    # Gate stats
    gate_stats = {"ALLOW": 0, "DENY": 0, "NEED_APPROVAL": 0}
    for entry in gate:
        d = entry.get("decision", "ALLOW")
        if d in gate_stats:
            gate_stats[d] += 1

    return {
        "audit": {
            "total_events": len(audit),
            "by_severity": severity_counts,
            "recent_critical": sum(1 for e in audit[:20] if e.get("severity") == "critical"),
        },
        "gate": {
            "total_decisions": len(gate),
            "by_decision": gate_stats,
            "deny_rate": gate_stats["DENY"] / max(len(gate), 1) * 100,
        },
        "autonomy": {
            "overall_score": autonomy["overall_score"],
            "domain_count": len(autonomy["domains"]),
            "active_approvals": len(autonomy["active_approvals"]),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
