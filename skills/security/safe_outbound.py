"""
Skill: safe_outbound
Description: Single choke point for ALL irreversible outbound actions (send, submit, delete, pay, publish)
Version: 1.0.0
Tier: core

This skill MUST be called before any irreversible browser action:
- Send email
- Submit form
- Post/Publish content
- Delete anything
- Make payment

It enforces the draft-only workflow:
1. Scan content with sensitive_content_gate (locally, not through policy layer)
2. If BLOCK -> raise error, stop immediately
3. If REVIEW or irreversible -> require explicit approval token
4. Only with valid approval -> return permission to proceed

Interface:
- guard(content, action, approval_token) -> GateResult
- IRREVERSIBLE_ACTIONS: set of action types that always need approval

Usage in Playwright automation:
    from safe_outbound import guard

    # Before clicking Send
    result = guard(
        content=email_body,
        action="send_email",
        approval_token=user_approval  # Must be "APPROVED" from user
    )
    # If we get here without exception, safe to proceed
    page.click("button[type=submit]")
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


# Skill metadata
SKILL_META = {
    "name": "safe_outbound",
    "description": "Single choke point for irreversible actions - enforces draft-only workflow",
    "tier": "core",
    "version": "1.0.0",
    "author": "duro",
    "phase": "security",
    "triggers": ["send", "submit", "delete", "pay", "publish", "post", "irreversible"],
}

REQUIRES = []


# Types
Decision = Literal["ALLOW", "BLOCK", "REVIEW"]


class OutboundError(Exception):
    """Raised when outbound action is blocked."""
    pass


class ApprovalRequired(Exception):
    """Raised when action requires explicit approval."""
    pass


@dataclass
class GateResult:
    """Result from the outbound guard."""
    decision: Decision
    action: str
    findings: List[Dict[str, Any]]
    redacted_content: Optional[str] = None
    approval_required: bool = False
    approved: bool = False


# Actions that ALWAYS require approval, regardless of content scan result
IRREVERSIBLE_ACTIONS = {
    "send",
    "send_email",
    "submit",
    "submit_form",
    "publish",
    "post",
    "delete",
    "remove",
    "pay",
    "payment",
    "purchase",
    "transfer",
}


def normalize_action(action: str) -> str:
    """Normalize action name for matching."""
    return action.lower().strip().replace("-", "_").replace(" ", "_")


def is_irreversible(action: str) -> bool:
    """Check if action is classified as irreversible."""
    normalized = normalize_action(action)
    # Check exact match
    if normalized in IRREVERSIBLE_ACTIONS:
        return True
    # Check if action contains any irreversible keyword
    for irreversible in IRREVERSIBLE_ACTIONS:
        if irreversible in normalized:
            return True
    return False


def run_sensitive_gate_local(content: str, action_type: str, redact: bool = True) -> Dict[str, Any]:
    """
    Run sensitive_content_gate LOCALLY (not through MCP/policy layer).

    This bypasses the policy gate that would block secrets in arguments,
    allowing us to scan content that contains secrets.
    """
    # Path to the scanner skill
    scanner_path = Path(__file__).parent / "sensitive_content_gate.py"

    if not scanner_path.exists():
        raise FileNotFoundError(f"Scanner not found at {scanner_path}")

    # Prepare input
    input_data = json.dumps({
        "content": content,
        "action_type": action_type,
        "redact": redact,
    })

    # Run scanner as subprocess with --json flag
    try:
        result = subprocess.run(
            [sys.executable, str(scanner_path), "--json"],
            input=input_data.encode("utf-8"),
            capture_output=True,
            timeout=30,
            check=False,
        )

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"Scanner failed: {stderr}")

        output = result.stdout.decode("utf-8")
        return json.loads(output)

    except subprocess.TimeoutExpired:
        raise RuntimeError("Scanner timed out after 30 seconds")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Scanner returned invalid JSON: {e}")


def validate_approval_token(token: Optional[str]) -> bool:
    """
    Validate the approval token.

    Token must be exactly "APPROVED" - this ensures explicit user consent.
    In future, could extend to time-limited tokens, signatures, etc.
    """
    if token is None:
        return False
    return token.strip().upper() == "APPROVED"


def guard(
    content: str,
    action: str,
    approval_token: Optional[str] = None,
    strict: bool = True,
) -> GateResult:
    """
    Main guard function - the single choke point for all outbound actions.

    Args:
        content: The content being sent/submitted/posted
        action: The action type (send_email, submit_form, etc.)
        approval_token: Must be "APPROVED" for irreversible actions
        strict: If True, raise exceptions on BLOCK/no approval

    Returns:
        GateResult with decision and metadata

    Raises:
        OutboundError: If content is blocked by sensitive_content_gate
        ApprovalRequired: If action requires approval but token not provided
    """
    # Step 1: Run sensitive content scan LOCALLY
    scan_result = run_sensitive_gate_local(content, action, redact=True)

    decision = scan_result.get("recommendation", "REVIEW")
    findings = scan_result.get("findings", [])
    redacted = scan_result.get("redacted_content")

    # Step 2: If BLOCK, stop immediately
    if decision == "BLOCK":
        result = GateResult(
            decision="BLOCK",
            action=action,
            findings=findings,
            redacted_content=redacted,
            approval_required=False,
            approved=False,
        )
        if strict:
            finding_summary = ", ".join(
                f"{f['pattern_type']}({f['severity']})"
                for f in findings[:3]
            )
            raise OutboundError(
                f"BLOCKED: Sensitive content detected in {action}. "
                f"Findings: {finding_summary}. "
                f"Redacted preview: {redacted[:200] if redacted else 'N/A'}..."
            )
        return result

    # Step 3: Check if approval is required
    needs_approval = (decision == "REVIEW") or is_irreversible(action)
    has_approval = validate_approval_token(approval_token)

    result = GateResult(
        decision=decision,
        action=action,
        findings=findings,
        redacted_content=redacted,
        approval_required=needs_approval,
        approved=has_approval,
    )

    # Step 4: If needs approval but not approved, block
    if needs_approval and not has_approval:
        if strict:
            raise ApprovalRequired(
                f"Action '{action}' requires explicit approval. "
                f"Content scan: {decision}. "
                f"Provide approval_token='APPROVED' after reviewing: "
                f"{redacted[:200] if redacted else content[:200]}..."
            )
        return result

    # Step 5: All checks passed - safe to proceed
    return result


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Skill execution function for MCP integration.

    Args:
        args: {
            content: str - content to scan
            action: str - action type
            approval_token: str (optional) - must be "APPROVED"
            strict: bool (optional) - raise exceptions vs return result
        }

    Returns:
        {
            success: bool,
            decision: str,
            action: str,
            approval_required: bool,
            approved: bool,
            findings: list,
            redacted_content: str,
            error: str (if failed)
        }
    """
    content = args.get("content", "")
    action = args.get("action", "unknown")
    approval_token = args.get("approval_token")
    strict = args.get("strict", False)  # Non-strict for MCP to return result

    try:
        result = guard(
            content=content,
            action=action,
            approval_token=approval_token,
            strict=strict,
        )

        return {
            "success": True,
            "decision": result.decision,
            "action": result.action,
            "approval_required": result.approval_required,
            "approved": result.approved,
            "findings": result.findings,
            "redacted_content": result.redacted_content,
            "can_proceed": result.decision != "BLOCK" and (result.approved or (not result.approval_required)),
        }

    except OutboundError as e:
        return {
            "success": False,
            "decision": "BLOCK",
            "action": action,
            "error": str(e),
            "can_proceed": False,
        }

    except ApprovalRequired as e:
        return {
            "success": True,  # Not a failure, just needs approval
            "decision": "REVIEW",
            "action": action,
            "approval_required": True,
            "approved": False,
            "error": str(e),
            "can_proceed": False,
        }

    except Exception as e:
        return {
            "success": False,
            "decision": "BLOCK",  # Fail closed
            "action": action,
            "error": f"Guard error: {str(e)}",
            "can_proceed": False,
        }


# CLI support for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Safe Outbound Guard")
    parser.add_argument("--json", action="store_true", help="JSON input/output mode")
    parser.add_argument("--action", type=str, default="test", help="Action type")
    parser.add_argument("--content", type=str, help="Content to check")
    parser.add_argument("--approve", action="store_true", help="Provide approval token")

    args = parser.parse_args()

    if args.json:
        # JSON mode: read from stdin
        input_data = json.loads(sys.stdin.read())
        result = run(input_data, {}, {})
        print(json.dumps(result, indent=2))
    else:
        # Interactive mode
        content = args.content or "Test content with no secrets"
        approval = "APPROVED" if args.approve else None

        print(f"Testing guard with action='{args.action}'")
        print(f"Content: {content[:50]}...")
        print(f"Approval: {approval}")
        print()

        try:
            result = guard(content, args.action, approval, strict=True)
            print(f"Result: {result.decision}")
            print(f"Approval required: {result.approval_required}")
            print(f"Approved: {result.approved}")
            print("Can proceed!")
        except (OutboundError, ApprovalRequired) as e:
            print(f"STOPPED: {e}")


__all__ = [
    "SKILL_META",
    "REQUIRES",
    "run",
    "guard",
    "is_irreversible",
    "GateResult",
    "OutboundError",
    "ApprovalRequired",
    "IRREVERSIBLE_ACTIONS",
]
