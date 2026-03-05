"""
Skill: sensitive_content_gate
Description: Pre-send scanner that detects passwords, API keys, tokens, and other sensitive data before browser automation actions
Version: 1.1.0
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
    "description": "Pre-send scanner for sensitive data (passwords, API keys, tokens, cloud credentials, PII) before browser actions",
    "tier": "core",
    "version": "1.1.0",
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
    CLOUD_CREDENTIAL = "cloud_credential"
    PII = "pii"
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


# === VALIDATION HELPERS ===

def luhn_check(card_number: str) -> bool:
    """
    Validate credit card number using Luhn algorithm.
    Returns True if the number passes the checksum.
    """
    # Remove any non-digit characters
    digits = ''.join(c for c in card_number if c.isdigit())

    if len(digits) < 13 or len(digits) > 19:
        return False

    # Luhn algorithm
    total = 0
    reverse_digits = digits[::-1]

    for i, digit in enumerate(reverse_digits):
        n = int(digit)
        if i % 2 == 1:  # Double every second digit
            n *= 2
            if n > 9:
                n -= 9
        total += n

    return total % 10 == 0


# Patterns that need post-match validation
REQUIRES_VALIDATION = {
    "credit_card": luhn_check,
}


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
        # OpenAI (sk-... with 8+ chars, covers project keys too)
        (r'\bsk-[a-zA-Z0-9]{8,}\b', Severity.CRITICAL, 0.95),
        (r'\bsk-proj-[a-zA-Z0-9]{8,}\b', Severity.CRITICAL, 0.99),
        # Anthropic
        (r'\bsk-ant-[a-zA-Z0-9-]{8,}\b', Severity.CRITICAL, 0.99),
        # Stripe
        (r'\bsk_(?:live|test)_[a-zA-Z0-9]{8,}\b', Severity.CRITICAL, 0.99),
        (r'\bpk_(?:live|test)_[a-zA-Z0-9]{8,}\b', Severity.HIGH, 0.95),
        (r'\brk_(?:live|test)_[a-zA-Z0-9]{8,}\b', Severity.CRITICAL, 0.99),
        # Sendgrid
        (r'\bSG\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b', Severity.CRITICAL, 0.99),
        # Twilio
        (r'\bAC[a-f0-9]{32}\b', Severity.CRITICAL, 0.99),
        (r'\bSK[a-f0-9]{32}\b', Severity.CRITICAL, 0.99),
        # Slack
        (r'\bxox[baprs]-[a-zA-Z0-9-]{10,}\b', Severity.CRITICAL, 0.99),
        # Discord
        (r'\b[MN][a-zA-Z0-9]{23,}\.[a-zA-Z0-9_-]{6}\.[a-zA-Z0-9_-]{27}\b', Severity.CRITICAL, 0.95),
        # Mailchimp
        (r'\b[a-f0-9]{32}-us[0-9]{1,2}\b', Severity.HIGH, 0.9),
        # Mailgun
        (r'\bkey-[a-zA-Z0-9]{32}\b', Severity.CRITICAL, 0.99),
        # Supabase
        (r'\beyJ[a-zA-Z0-9_-]{50,}\.eyJ[a-zA-Z0-9_-]{50,}\b', Severity.HIGH, 0.9),
        (r'\bsbp_[a-f0-9]{40}\b', Severity.CRITICAL, 0.99),
        # Vercel
        (r'\bvercel_[a-zA-Z0-9]{24}\b', Severity.CRITICAL, 0.99),
        # Netlify
        (r'\bnfp_[a-zA-Z0-9]{40}\b', Severity.CRITICAL, 0.99),
        # Heroku API key (specific format, not generic UUIDs)
        # REMOVED: Generic UUID pattern caused too many false positives
        # Render
        (r'\brnd_[a-zA-Z0-9]{24,}\b', Severity.CRITICAL, 0.99),
        # Generic API key patterns (lowered threshold)
        (r'api[_-]?key\s*[=:]\s*["\']?([a-zA-Z0-9_-]{12,})["\']?', Severity.HIGH, 0.85),
        (r'apikey\s*[=:]\s*["\']?([a-zA-Z0-9_-]{12,})["\']?', Severity.HIGH, 0.85),
        # Generic patterns with common prefixes
        (r'\b(?:api|key|secret|token)[_-]?[a-zA-Z0-9]{16,}\b', Severity.MEDIUM, 0.7),
    ],

    # Token patterns
    PatternType.TOKEN: [
        # JWT (compact detection)
        (r'\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b', Severity.HIGH, 0.95),
        # Bearer token
        (r'bearer\s+([a-zA-Z0-9_-]{16,})', Severity.MEDIUM, 0.8),
        # Generic token
        (r'token\s*[=:]\s*["\']?([a-zA-Z0-9_-]{16,})["\']?', Severity.MEDIUM, 0.75),
        # GitHub tokens (all types)
        (r'\bghp_[a-zA-Z0-9]{36}\b', Severity.CRITICAL, 0.99),
        (r'\bgho_[a-zA-Z0-9]{36}\b', Severity.CRITICAL, 0.99),
        (r'\bghu_[a-zA-Z0-9]{36}\b', Severity.CRITICAL, 0.99),
        (r'\bghs_[a-zA-Z0-9]{36}\b', Severity.CRITICAL, 0.99),
        (r'\bghr_[a-zA-Z0-9]{36}\b', Severity.CRITICAL, 0.99),
        # GitLab tokens
        (r'\bglpat-[a-zA-Z0-9_-]{20,}\b', Severity.CRITICAL, 0.99),
        # npm tokens
        (r'\bnpm_[a-zA-Z0-9]{36}\b', Severity.CRITICAL, 0.99),
        # PyPI tokens
        (r'\bpypi-[a-zA-Z0-9_-]{50,}\b', Severity.CRITICAL, 0.99),
        # Figma tokens
        (r'\bfigd_[a-zA-Z0-9_-]{40,}\b', Severity.HIGH, 0.95),
        # Auth0
        (r'\bA0[a-zA-Z0-9]{32}\b', Severity.HIGH, 0.9),
        # Session/refresh tokens
        (r'(?:session|refresh)[_-]?token\s*[=:]\s*["\']?([a-zA-Z0-9_-]{20,})["\']?', Severity.HIGH, 0.85),
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
        (r'\bAKIA[0-9A-Z]{16}\b', Severity.CRITICAL, 0.99),
        (r'\bASIA[0-9A-Z]{16}\b', Severity.CRITICAL, 0.99),  # Temporary credentials
        (r'\bAIDA[0-9A-Z]{16}\b', Severity.CRITICAL, 0.99),  # IAM user
        # AWS Secret Access Key (40 chars base64)
        (r'aws_secret_access_key\s*[=:]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?', Severity.CRITICAL, 0.95),
        (r'aws_session_token\s*[=:]\s*["\']?([a-zA-Z0-9/+=]{100,})["\']?', Severity.CRITICAL, 0.95),
    ],

    # Other cloud provider credentials
    PatternType.CLOUD_CREDENTIAL: [
        # Google Cloud / GCP
        (r'\bAIza[a-zA-Z0-9_-]{35}\b', Severity.CRITICAL, 0.99),  # GCP API key
        (r'"type"\s*:\s*"service_account"', Severity.HIGH, 0.9),  # Service account JSON
        (r'"private_key"\s*:\s*"-----BEGIN', Severity.CRITICAL, 0.99),
        # Azure - GUID pattern removed (too many false positives with normal UUIDs)
        (r'DefaultEndpointsProtocol=https;AccountName=[^;]+;AccountKey=[a-zA-Z0-9+/=]{88}', Severity.CRITICAL, 0.99),  # Azure Storage connection
        (r'SharedAccessSignature=[a-zA-Z0-9%&=]+', Severity.HIGH, 0.9),  # Azure SAS token
        # DigitalOcean
        (r'\bdop_v1_[a-f0-9]{64}\b', Severity.CRITICAL, 0.99),
        (r'\bdoctl_[a-f0-9]{64}\b', Severity.CRITICAL, 0.99),
        # Cloudflare - 37-hex pattern removed (too many false positives)
        # Firebase
        (r'firebase[_-]?api[_-]?key\s*[=:]\s*["\']?([a-zA-Z0-9_-]{30,})["\']?', Severity.HIGH, 0.9),
    ],

    # PII - Personally Identifiable Information
    PatternType.PII: [
        # Credit card numbers (Visa, MC, Amex, Discover) - Luhn validated
        (r'\b4[0-9]{12}(?:[0-9]{3})?\b', Severity.CRITICAL, 0.9, "credit_card"),  # Visa
        (r'\b5[1-5][0-9]{14}\b', Severity.CRITICAL, 0.9, "credit_card"),  # Mastercard
        (r'\b3[47][0-9]{13}\b', Severity.CRITICAL, 0.9, "credit_card"),  # Amex
        (r'\b6(?:011|5[0-9]{2})[0-9]{12}\b', Severity.CRITICAL, 0.9, "credit_card"),  # Discover
        # SSN (US) - formatted only (xxx-xx-xxxx)
        (r'\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b', Severity.CRITICAL, 0.85),
        # REMOVED: 9 bare digits - too many false positives
        # UK National Insurance
        (r'\b[A-Z]{2}[0-9]{6}[A-Z]\b', Severity.HIGH, 0.85),
        # REMOVED: Phone numbers and emails - too many false positives, not secrets
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
        for pattern_tuple in patterns:
            # Handle both 3-tuples and 4-tuples (with validation type)
            if len(pattern_tuple) == 4:
                pattern, severity, base_confidence, validation_type = pattern_tuple
            else:
                pattern, severity, base_confidence = pattern_tuple
                validation_type = None

            try:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    matched_text = match.group(0)
                    # Try to get captured group if exists, otherwise use full match
                    if match.groups():
                        sensitive_part = match.group(1)
                    else:
                        sensitive_part = matched_text

                    # Apply validation if required (e.g., Luhn check for credit cards)
                    if validation_type and validation_type in REQUIRES_VALIDATION:
                        validator = REQUIRES_VALIDATION[validation_type]
                        if not validator(sensitive_part):
                            continue  # Skip this match - failed validation

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
    import argparse
    import sys
    import json

    parser = argparse.ArgumentParser(description="Sensitive Content Gate Scanner")
    parser.add_argument("--json", action="store_true",
                        help="JSON mode: read args from stdin, output JSON to stdout")
    parser.add_argument("--content", type=str, help="Content to scan (interactive mode)")
    parser.add_argument("--action", type=str, default="test", help="Action type")

    args = parser.parse_args()

    if args.json:
        # JSON mode for subprocess calling
        # Read input from stdin
        try:
            input_data = json.loads(sys.stdin.read())
            result = run(input_data, {}, {})
            print(json.dumps(result))
            sys.exit(0)
        except Exception as e:
            error_result = {
                "success": False,
                "error": str(e),
                "recommendation": "BLOCK",  # Fail closed
                "findings": [],
                "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            }
            print(json.dumps(error_result))
            sys.exit(1)

    # Interactive/test mode
    print("sensitive_content_gate Skill v1.1")
    print("=" * 50)
    print()

    if args.content:
        test_content = args.content
    else:
        test_content = """
        Here is the report:

        API key: sk-testkey12345678
        Database: postgres://user:testpass@host:5432/db

        Please review and let me know.
        """

    result = run({"content": test_content, "action_type": args.action, "redact": True}, {}, {})

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
