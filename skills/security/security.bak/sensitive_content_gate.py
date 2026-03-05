"""
Skill: sensitive_content_gate
Description: Pre-send scanner that detects passwords, API keys, tokens, and other sensitive data before browser automation actions
Version: 1.0.0
Tier: core

This is a security gate that MUST be called before any outbound browser action:
- Sending emails
- Submitting forms
- Posting messages
- Making API calls with user-provided content

It scans text content for sensitive patterns and returns:
- Whether sensitive content was detected
- What patterns were found (redacted)
- Recommendation: ALLOW, BLOCK, or REVIEW

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
- scan_content(text) -> ScanResult: direct scanning function

Usage:
    result = run({
        "content": "Email body with password123 inside",
        "action_type": "email",
        "redact": True
    }, tools, context)

    if result["recommendation"] == "BLOCK":
        raise SecurityError("Sensitive content detected")
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


# Skill metadata
SKILL_META = {
    "name": "sensitive_content_gate",
    "description": "Pre-send scanner for sensitive data (passwords, API keys, tokens) before browser actions",
    "tier": "core",
    "version": "1.0.0",
    "author": "duro",
    "phase": "security",
    "triggers": ["scan content", "check sensitive", "pre-send scan", "content gate"],
}

# Required capabilities (none - this is a pure function skill)
REQUIRES = []


class Severity(Enum):
    """Finding severity levels."""
    LOW = "low"          # Possibly sensitive, needs review
    MEDIUM = "medium"    # Likely sensitive, should redact
    HIGH = "high"        # Definitely sensitive, should block
    CRITICAL = "critical"  # Known credential pattern, must block


class PatternType(Enum):
    """Types of sensitive patterns."""
    PASSWORD = "password"
    API_KEY = "api_key"
    TOKEN = "token"
    CONNECTION_STRING = "connection_string"
    PRIVATE_KEY = "private_key"
    AWS_CREDENTIAL = "aws_credential"
    GENERIC_SECRET = "generic_secret"


@dataclass
class Finding:
    """A detected sensitive pattern."""
    pattern_type: PatternType
    severity: Severity
    matched_text: str      # The actual matched text (for internal use)
    redacted_text: str     # Redacted version for display
    context: str           # Surrounding context
    line_number: int
    confidence: float


@dataclass
class ScanResult:
    """Result of a content scan."""
    has_sensitive: bool
    findings: List[Finding]
    recommendation: str    # ALLOW, BLOCK, REVIEW
    redacted_content: Optional[str]
    summary: Dict[str, int]
    scan_time_ms: int


# === SENSITIVE PATTERNS ===

PATTERNS = {
    # Password patterns
    PatternType.PASSWORD: [
        # Explicit password assignments (code)
        (r'password\s*[=:]\s*["\']([^"\']{4,})["\']', Severity.CRITICAL, 0.95),
        (r'pwd\s*[=:]\s*["\']([^"\']{4,})["\']', Severity.HIGH, 0.9),
        (r'passwd\s*[=:]\s*["\']([^"\']{4,})["\']', Severity.HIGH, 0.9),
        # Password in URL
        (r'://[^:]+:([^@]{4,})@', Severity.CRITICAL, 0.95),
        # Natural language: "password is: xyz", "your password: xyz", "new password is xyz"
        (r'\b(?:new\s+)?password\s+(?:is[:\s]*|[:]\s*)([A-Za-z0-9!@#$%^&*_-]{6,})\b', Severity.CRITICAL, 0.95),
        (r'\b(?:password|pwd|pass)[:\s]+([A-Za-z0-9!@#$%^&*_-]{8,})\b', Severity.HIGH, 0.85),
        # Password followed by value on same or next line
        (r'password[:\s]*\n?\s*([A-Za-z0-9!@#$%^&*_-]{8,})\b', Severity.HIGH, 0.85),
    ],

    # API Key patterns
    PatternType.API_KEY: [
        # OpenAI
        (r'sk-[a-zA-Z0-9]{20,}', Severity.CRITICAL, 0.99),
        # Anthropic
        (r'sk-ant-[a-zA-Z0-9-]{20,}', Severity.CRITICAL, 0.99),
        # Generic API key patterns
        (r'api[_-]?key\s*[=:]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?', Severity.HIGH, 0.9),
        (r'apikey\s*[=:]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?', Severity.HIGH, 0.9),
        # Stripe
        (r'sk_(?:live|test)_[a-zA-Z0-9]{20,}', Severity.CRITICAL, 0.99),
        (r'pk_(?:live|test)_[a-zA-Z0-9]{20,}', Severity.HIGH, 0.95),
        # Sendgrid
        (r'SG\.[a-zA-Z0-9_-]{22,}\.[a-zA-Z0-9_-]{22,}', Severity.CRITICAL, 0.99),
    ],

    # Token patterns
    PatternType.TOKEN: [
        # JWT
        (r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*', Severity.HIGH, 0.95),
        # Bearer token
        (r'bearer\s+([a-zA-Z0-9_-]{20,})', Severity.MEDIUM, 0.8),
        # Generic token
        (r'token\s*[=:]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?', Severity.MEDIUM, 0.75),
        # GitHub tokens
        (r'ghp_[a-zA-Z0-9]{36}', Severity.CRITICAL, 0.99),
        (r'gho_[a-zA-Z0-9]{36}', Severity.CRITICAL, 0.99),
        (r'ghu_[a-zA-Z0-9]{36}', Severity.CRITICAL, 0.99),
    ],

    # Connection strings
    PatternType.CONNECTION_STRING: [
        # PostgreSQL
        (r'postgres(?:ql)?://[^\s]{10,}', Severity.CRITICAL, 0.95),
        # MySQL
        (r'mysql://[^\s]{10,}', Severity.CRITICAL, 0.95),
        # MongoDB
        (r'mongodb(?:\+srv)?://[^\s]{10,}', Severity.CRITICAL, 0.95),
        # Redis
        (r'redis://[^\s]{10,}', Severity.HIGH, 0.9),
        # Generic database URLs
        (r'(?:jdbc|odbc):[^\s]{10,}', Severity.HIGH, 0.85),
    ],

    # Private keys
    PatternType.PRIVATE_KEY: [
        (r'-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----', Severity.CRITICAL, 0.99),
        (r'-----BEGIN PGP PRIVATE KEY BLOCK-----', Severity.CRITICAL, 0.99),
    ],

    # AWS credentials
    PatternType.AWS_CREDENTIAL: [
        # AWS Access Key ID
        (r'AKIA[0-9A-Z]{16}', Severity.CRITICAL, 0.99),
        # AWS Secret Access Key (40 chars base64)
        (r'aws_secret_access_key\s*[=:]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?', Severity.CRITICAL, 0.95),
    ],

    # Generic secrets
    PatternType.GENERIC_SECRET: [
        # Secret assignments
        (r'secret\s*[=:]\s*["\']([^"\']{8,})["\']', Severity.HIGH, 0.8),
        # Credential assignments
        (r'credential[s]?\s*[=:]\s*["\']([^"\']{8,})["\']', Severity.HIGH, 0.8),
        # Private/auth key assignments
        (r'(?:private|auth)[_-]?key\s*[=:]\s*["\']?([a-zA-Z0-9_-]{16,})["\']?', Severity.HIGH, 0.85),
    ],
}

# Context patterns that indicate higher sensitivity
HIGH_RISK_CONTEXTS = [
    r'email',
    r'send',
    r'post',
    r'submit',
    r'public',
    r'share',
    r'forward',
    r'external',
]


def redact_text(text: str, keep_chars: int = 4) -> str:
    """Redact sensitive text, keeping first/last few chars for identification."""
    if len(text) <= keep_chars * 2:
        return '*' * len(text)
    return text[:keep_chars] + '*' * (len(text) - keep_chars * 2) + text[-keep_chars:]


def get_context(content: str, match_start: int, match_end: int, context_chars: int = 30) -> str:
    """Extract surrounding context for a match."""
    start = max(0, match_start - context_chars)
    end = min(len(content), match_end + context_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    return prefix + content[start:end] + suffix


def get_line_number(content: str, position: int) -> int:
    """Get line number for a position in content."""
    return content[:position].count('\n') + 1


def scan_content(content: str) -> ScanResult:
    """
    Scan content for sensitive patterns.

    Args:
        content: The text content to scan

    Returns:
        ScanResult with findings and recommendation
    """
    import time
    start_time = time.time()

    findings: List[Finding] = []

    # Scan for each pattern type
    for pattern_type, patterns in PATTERNS.items():
        for pattern, severity, base_confidence in patterns:
            try:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    matched_text = match.group(0)
                    # Try to get captured group if exists, otherwise use full match
                    if match.groups():
                        sensitive_part = match.group(1)
                    else:
                        sensitive_part = matched_text

                    # Calculate confidence based on context
                    confidence = base_confidence
                    context = get_context(content, match.start(), match.end())

                    # Boost confidence if in high-risk context
                    for ctx_pattern in HIGH_RISK_CONTEXTS:
                        if re.search(ctx_pattern, context, re.IGNORECASE):
                            confidence = min(1.0, confidence + 0.05)

                    findings.append(Finding(
                        pattern_type=pattern_type,
                        severity=severity,
                        matched_text=sensitive_part,
                        redacted_text=redact_text(sensitive_part),
                        context=context,
                        line_number=get_line_number(content, match.start()),
                        confidence=confidence
                    ))
            except re.error:
                # Skip invalid patterns
                continue

    # Deduplicate findings by matched_text
    seen = set()
    unique_findings = []
    for f in findings:
        if f.matched_text not in seen:
            seen.add(f.matched_text)
            unique_findings.append(f)
    findings = unique_findings

    # Calculate recommendation
    has_sensitive = len(findings) > 0

    if not has_sensitive:
        recommendation = "ALLOW"
    elif any(f.severity == Severity.CRITICAL for f in findings):
        recommendation = "BLOCK"
    elif any(f.severity == Severity.HIGH for f in findings):
        recommendation = "BLOCK"
    elif any(f.severity == Severity.MEDIUM for f in findings):
        recommendation = "REVIEW"
    else:
        recommendation = "REVIEW"

    # Create summary
    summary = {
        "critical": sum(1 for f in findings if f.severity == Severity.CRITICAL),
        "high": sum(1 for f in findings if f.severity == Severity.HIGH),
        "medium": sum(1 for f in findings if f.severity == Severity.MEDIUM),
        "low": sum(1 for f in findings if f.severity == Severity.LOW),
    }

    # Create redacted content
    redacted_content = content
    for finding in sorted(findings, key=lambda f: len(f.matched_text), reverse=True):
        redacted_content = redacted_content.replace(
            finding.matched_text,
            finding.redacted_text
        )

    scan_time_ms = int((time.time() - start_time) * 1000)

    return ScanResult(
        has_sensitive=has_sensitive,
        findings=findings,
        recommendation=recommendation,
        redacted_content=redacted_content,
        summary=summary,
        scan_time_ms=scan_time_ms
    )


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            content: str - the text content to scan
            action_type: str - type of action (email, form, chat, api)
            redact: bool - whether to include redacted version
        }
        tools: {} - no external tools required
        context: {run_id, etc.}

    Returns:
        {
            success: bool,
            has_sensitive: bool,
            recommendation: str - ALLOW, BLOCK, or REVIEW
            findings: List[dict] - detected patterns
            redacted_content: str (if redact=True)
            summary: dict - counts by severity
            action_type: str
            scan_time_ms: int
        }
    """
    content = args.get("content", "")
    action_type = args.get("action_type", "unknown")
    include_redacted = args.get("redact", True)

    if not content:
        return {
            "success": True,
            "has_sensitive": False,
            "recommendation": "ALLOW",
            "findings": [],
            "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "action_type": action_type,
            "scan_time_ms": 0,
        }

    result = scan_content(content)

    response = {
        "success": True,
        "has_sensitive": result.has_sensitive,
        "recommendation": result.recommendation,
        "findings": [
            {
                "pattern_type": f.pattern_type.value,
                "severity": f.severity.value,
                "redacted_match": f.redacted_text,
                "line_number": f.line_number,
                "confidence": f.confidence,
                # Do NOT include matched_text or context in output - security risk
            }
            for f in result.findings
        ],
        "summary": result.summary,
        "action_type": action_type,
        "scan_time_ms": result.scan_time_ms,
    }

    if include_redacted:
        response["redacted_content"] = result.redacted_content

    return response


# Export key components
__all__ = [
    "SKILL_META",
    "REQUIRES",
    "run",
    "scan_content",
    "ScanResult",
    "Finding",
    "Severity",
    "PatternType",
]


if __name__ == "__main__":
    # Test the scanner
    print("sensitive_content_gate Skill v1.0")
    print("=" * 50)
    print()

    test_content = """
    Here is the report:

    The Supabase project password is Cinematch2026!
    API key: sk-1234567890abcdef1234567890abcdef
    Database: postgres://user:pass@host:5432/db

    Please review and let me know.
    """

    result = run({"content": test_content, "action_type": "email", "redact": True}, {}, {})

    print(f"Has sensitive: {result['has_sensitive']}")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Summary: {result['summary']}")
    print()
    print("Findings:")
    for f in result['findings']:
        print(f"  - [{f['severity']}] {f['pattern_type']}: {f['redacted_match']}")
    print()
    print("Redacted content:")
    print(result.get('redacted_content', 'N/A'))
