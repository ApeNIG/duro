"""
Skill: playwright_safe_logger
Description: Playwright logging interceptor that masks sensitive data before logging
Version: 1.0.0
Tier: core

This module provides safe logging wrappers for Playwright actions that:
1. Mask typed text (passwords, secrets) before logging
2. Redact sensitive patterns in console output
3. Integrate with sensitive_content_gate for pattern detection

Usage:
    from playwright_safe_logger import SafePlaywright

    sp = SafePlaywright(page)
    await sp.safe_type("#password", actual_password)  # Logs: Type into #password text=[REDACTED] (len=12)
    await sp.safe_fill("#email", email)               # Logs with masking
    await sp.safe_click("button:text('Send')")        # Checks if irreversible
"""

import re
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass


# Skill metadata
SKILL_META = {
    "name": "playwright_safe_logger",
    "description": "Playwright logging interceptor that masks sensitive data",
    "tier": "core",
    "version": "1.0.0",
    "author": "duro",
    "phase": "security",
    "triggers": ["playwright", "browser", "logging", "mask", "redact"],
}

REQUIRES = []


# Configure module logger
logger = logging.getLogger("playwright_safe")
logger.setLevel(logging.INFO)


# Patterns that should ALWAYS be masked in logs
SENSITIVE_PATTERNS = [
    # Passwords
    (r'\bpassword\s*[=:]\s*["\']?([^"\'\s]{4,})["\']?', "password"),
    (r'\bpwd\s*[=:]\s*["\']?([^"\'\s]{4,})["\']?', "password"),
    # API keys
    (r'\bsk-[a-zA-Z0-9]{8,}\b', "api_key"),
    (r'\bsk_(?:live|test)_[a-zA-Z0-9]{8,}\b', "api_key"),
    (r'\bghp_[a-zA-Z0-9]{36}\b', "token"),
    (r'\bAKIA[0-9A-Z]{16}\b', "aws_key"),
    # Connection strings
    (r'://[^:]+:([^@]{4,})@', "connection_password"),
    # JWT tokens
    (r'\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b', "jwt"),
]

# Actions that should trigger approval flow
IRREVERSIBLE_ACTIONS = {
    "send", "submit", "delete", "remove", "pay", "purchase",
    "publish", "post", "confirm", "approve", "transfer"
}


def mask_text(text: str, keep_chars: int = 0) -> str:
    """Mask text for logging, keeping only length info."""
    if not text:
        return "[EMPTY]"
    return f"[REDACTED] (len={len(text)})"


def redact_sensitive_patterns(text: str) -> str:
    """Redact known sensitive patterns from text."""
    result = text
    for pattern, pattern_type in SENSITIVE_PATTERNS:
        def replace_match(m):
            matched = m.group(0)
            # Keep first 4 and last 2 chars for identification
            if len(matched) > 8:
                return matched[:4] + "*" * (len(matched) - 6) + matched[-2:]
            return "*" * len(matched)

        result = re.sub(pattern, replace_match, result, flags=re.IGNORECASE)
    return result


def is_sensitive_field(selector: str) -> bool:
    """Check if a field selector suggests sensitive content."""
    sensitive_keywords = [
        "password", "pwd", "secret", "token", "key", "auth",
        "credential", "ssn", "credit", "card", "cvv", "cvc",
        "pin", "otp", "code", "verify"
    ]
    selector_lower = selector.lower()
    return any(kw in selector_lower for kw in sensitive_keywords)


def is_irreversible_action(selector: str) -> bool:
    """Check if a click selector suggests an irreversible action."""
    selector_lower = selector.lower()
    for action in IRREVERSIBLE_ACTIONS:
        if action in selector_lower:
            return True
    return False


@dataclass
class SafeLogEntry:
    """A log entry with safety metadata."""
    action: str
    selector: str
    masked_value: Optional[str]
    is_sensitive: bool
    is_irreversible: bool
    original_length: Optional[int]


class SafeLogger:
    """
    Logger that masks sensitive data before output.

    Usage:
        safe_log = SafeLogger()
        safe_log.type("#password", actual_password)  # Logs masked
        safe_log.click("button:text('Send')")        # Warns if irreversible
    """

    def __init__(self, name: str = "playwright"):
        self.logger = logging.getLogger(f"safe.{name}")
        self.entries: List[SafeLogEntry] = []

    def type(self, selector: str, text: str) -> SafeLogEntry:
        """Log a type action with masked content."""
        is_sensitive = is_sensitive_field(selector) or self._quick_scan(text)

        entry = SafeLogEntry(
            action="type",
            selector=selector,
            masked_value=mask_text(text) if is_sensitive else redact_sensitive_patterns(text[:20] + "..."),
            is_sensitive=is_sensitive,
            is_irreversible=False,
            original_length=len(text),
        )

        self.entries.append(entry)

        # Always mask in log output
        self.logger.info(
            f"Type into {selector} text={mask_text(text)} sensitive={is_sensitive}"
        )

        return entry

    def fill(self, selector: str, text: str) -> SafeLogEntry:
        """Log a fill action with masked content."""
        return self.type(selector, text)  # Same logic as type

    def click(self, selector: str) -> SafeLogEntry:
        """Log a click action, warn if irreversible."""
        is_irreversible = is_irreversible_action(selector)

        entry = SafeLogEntry(
            action="click",
            selector=selector,
            masked_value=None,
            is_sensitive=False,
            is_irreversible=is_irreversible,
            original_length=None,
        )

        self.entries.append(entry)

        log_msg = f"Click on {selector}"
        if is_irreversible:
            log_msg += " [IRREVERSIBLE ACTION - APPROVAL REQUIRED]"
            self.logger.warning(log_msg)
        else:
            self.logger.info(log_msg)

        return entry

    def _quick_scan(self, text: str) -> bool:
        """Quick check if text looks sensitive."""
        for pattern, _ in SENSITIVE_PATTERNS[:5]:  # Check first few patterns
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def get_entries(self) -> List[SafeLogEntry]:
        """Get all logged entries."""
        return self.entries.copy()

    def clear(self) -> None:
        """Clear logged entries."""
        self.entries.clear()


class SafePlaywrightWrapper:
    """
    Wrapper for Playwright page that enforces safe logging and approval workflows.

    This is meant to be used in browser automation scripts to ensure:
    1. All typed text is masked in logs
    2. Irreversible actions require approval
    3. Sensitive content is blocked before sending

    Usage:
        from playwright_safe_logger import SafePlaywrightWrapper

        # Wrap your page
        safe_page = SafePlaywrightWrapper(page)

        # Use wrapped methods
        await safe_page.safe_fill("#email", email)
        await safe_page.safe_type("#password", password)  # Masked in logs

        # Irreversible actions require approval
        await safe_page.safe_click_irreversible(
            "button:text('Send')",
            content=email_body,
            approval_token="APPROVED"
        )
    """

    def __init__(self, page: Any, approval_callback: Optional[Callable] = None):
        """
        Initialize wrapper.

        Args:
            page: Playwright page object
            approval_callback: Optional async function to call for approval
        """
        self.page = page
        self.logger = SafeLogger("playwright")
        self.approval_callback = approval_callback

    async def safe_fill(self, selector: str, text: str) -> None:
        """Fill a field with masked logging."""
        self.logger.fill(selector, text)
        await self.page.fill(selector, text)

    async def safe_type(self, selector: str, text: str, **kwargs) -> None:
        """Type into a field with masked logging."""
        self.logger.type(selector, text)
        await self.page.type(selector, text, **kwargs)

    async def safe_click(self, selector: str) -> None:
        """Click an element with logging."""
        entry = self.logger.click(selector)
        if entry.is_irreversible:
            raise RuntimeError(
                f"Irreversible action detected: {selector}. "
                f"Use safe_click_irreversible() with approval_token."
            )
        await self.page.click(selector)

    async def safe_click_irreversible(
        self,
        selector: str,
        content: str,
        approval_token: Optional[str] = None,
    ) -> None:
        """
        Click an irreversible action button with full safety checks.

        Args:
            selector: Button selector
            content: Content being sent (for scanning)
            approval_token: Must be "APPROVED" to proceed
        """
        from safe_outbound import guard, OutboundError, ApprovalRequired

        # Determine action type from selector
        action = "submit"
        for act in IRREVERSIBLE_ACTIONS:
            if act in selector.lower():
                action = act
                break

        # Run through the choke point
        try:
            result = guard(
                content=content,
                action=action,
                approval_token=approval_token,
                strict=True,
            )
        except OutboundError as e:
            self.logger.logger.error(f"BLOCKED: {e}")
            raise
        except ApprovalRequired as e:
            self.logger.logger.warning(f"APPROVAL REQUIRED: {e}")

            # Try callback if available
            if self.approval_callback:
                approved = await self.approval_callback(content, action)
                if approved:
                    result = guard(content, action, "APPROVED", strict=True)
                else:
                    raise
            else:
                raise

        # If we get here, we're approved
        self.logger.logger.info(f"APPROVED: Executing {action} via {selector}")
        await self.page.click(selector)


def create_safe_page(page: Any) -> SafePlaywrightWrapper:
    """Factory function to wrap a Playwright page."""
    return SafePlaywrightWrapper(page)


# MCP skill interface
def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Skill execution function.

    This skill is primarily used as a library, but can be invoked to:
    - Test pattern detection
    - Get masked version of text
    - Check if selector is irreversible
    """
    action = args.get("action", "mask")
    text = args.get("text", "")
    selector = args.get("selector", "")

    if action == "mask":
        return {
            "success": True,
            "masked": mask_text(text),
            "redacted": redact_sensitive_patterns(text),
            "is_sensitive": is_sensitive_field(selector) if selector else False,
        }

    elif action == "check_selector":
        return {
            "success": True,
            "selector": selector,
            "is_sensitive_field": is_sensitive_field(selector),
            "is_irreversible": is_irreversible_action(selector),
        }

    elif action == "redact":
        return {
            "success": True,
            "original_length": len(text),
            "redacted": redact_sensitive_patterns(text),
        }

    else:
        return {
            "success": False,
            "error": f"Unknown action: {action}. Use: mask, check_selector, redact",
        }


__all__ = [
    "SKILL_META",
    "REQUIRES",
    "run",
    "SafeLogger",
    "SafePlaywrightWrapper",
    "create_safe_page",
    "mask_text",
    "redact_sensitive_patterns",
    "is_sensitive_field",
    "is_irreversible_action",
]


if __name__ == "__main__":
    # Test the logger
    import sys

    logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

    safe_log = SafeLogger("test")

    print("Testing SafeLogger:")
    print()

    # Test type logging
    safe_log.type("#username", "john.doe@example.com")
    safe_log.type("#password", "SuperSecret123!")
    safe_log.type("#api-key", "sk-1234567890abcdef")

    # Test click logging
    safe_log.click("button:text('Login')")
    safe_log.click("button:text('Send Email')")
    safe_log.click("button:text('Delete Account')")

    print()
    print("Logged entries:")
    for entry in safe_log.get_entries():
        print(f"  {entry}")
