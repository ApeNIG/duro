"""
Regression Tests for Security Guardrails

These tests ensure:
1. Sensitive content is BLOCKED and Send never occurs
2. Irreversible actions require approval token
3. Safe logging masks sensitive data

Run with: python test_guardrails.py
Or: pytest test_guardrails.py -v
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any

# Test counters
PASSED = 0
FAILED = 0
TESTS = []


def test(name: str):
    """Decorator to register a test."""
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_scanner(content: str, action_type: str = "test") -> Dict[str, Any]:
    """Run sensitive_content_gate via CLI."""
    scanner_path = Path(__file__).parent / "sensitive_content_gate.py"
    input_data = json.dumps({
        "content": content,
        "action_type": action_type,
        "redact": True,
    })

    result = subprocess.run(
        [sys.executable, str(scanner_path), "--json"],
        input=input_data.encode("utf-8"),
        capture_output=True,
        timeout=30,
    )

    return json.loads(result.stdout.decode("utf-8"))


def run_guard(content: str, action: str, approval: str = None) -> Dict[str, Any]:
    """Run safe_outbound guard via CLI."""
    guard_path = Path(__file__).parent / "safe_outbound.py"

    input_data = {
        "content": content,
        "action": action,
        "strict": False,  # Return result instead of raising
    }
    if approval:
        input_data["approval_token"] = approval

    result = subprocess.run(
        [sys.executable, str(guard_path), "--json"],
        input=json.dumps(input_data).encode("utf-8"),
        capture_output=True,
        timeout=30,
    )

    return json.loads(result.stdout.decode("utf-8"))


# ============ SCANNER TESTS ============

@test("Scanner: BLOCK on password pattern")
def test_scanner_blocks_password():
    result = run_scanner("My password is SecretPass123")
    assert result["recommendation"] == "BLOCK", f"Expected BLOCK, got {result['recommendation']}"
    assert result["has_sensitive"] == True
    assert any(f["pattern_type"] == "password" for f in result["findings"])


@test("Scanner: BLOCK on API key (short format)")
def test_scanner_blocks_short_api_key():
    result = run_scanner("API key: sk-abcd12345678")
    assert result["recommendation"] == "BLOCK", f"Expected BLOCK, got {result['recommendation']}"
    assert any(f["pattern_type"] == "api_key" for f in result["findings"])


@test("Scanner: BLOCK on connection string")
def test_scanner_blocks_connection_string():
    result = run_scanner("Database: postgres://user:secretpass@host:5432/db")
    assert result["recommendation"] == "BLOCK", f"Expected BLOCK, got {result['recommendation']}"


@test("Scanner: BLOCK on AWS credentials")
def test_scanner_blocks_aws_key():
    result = run_scanner("AWS key: AKIAIOSFODNN7EXAMPLE")
    assert result["recommendation"] == "BLOCK", f"Expected BLOCK, got {result['recommendation']}"
    assert any(f["pattern_type"] == "aws_credential" for f in result["findings"])


@test("Scanner: BLOCK on credit card")
def test_scanner_blocks_credit_card():
    result = run_scanner("Card number: 4111111111111111")
    assert result["recommendation"] == "BLOCK", f"Expected BLOCK, got {result['recommendation']}"
    assert any(f["pattern_type"] == "pii" for f in result["findings"])


@test("Scanner: ALLOW clean content")
def test_scanner_allows_clean():
    result = run_scanner("Hello, thank you for your interest. We will contact you soon.")
    assert result["recommendation"] == "ALLOW", f"Expected ALLOW, got {result['recommendation']}"
    assert result["has_sensitive"] == False


@test("Scanner: Redacts sensitive content")
def test_scanner_redacts():
    result = run_scanner("Key: sk-secret12345678")
    assert "sk-s" in result["redacted_content"]
    assert "secret12345678" not in result["redacted_content"]


# ============ GUARD TESTS ============

@test("Guard: Blocks sensitive content even with approval")
def test_guard_blocks_sensitive():
    result = run_guard(
        content="Password is SecretPass123",
        action="send_email",
        approval="APPROVED"
    )
    assert result["decision"] == "BLOCK", f"Expected BLOCK, got {result['decision']}"
    assert result["can_proceed"] == False


@test("Guard: Requires approval for irreversible action")
def test_guard_requires_approval():
    result = run_guard(
        content="Clean email content",
        action="send_email",
        approval=None
    )
    assert result["approval_required"] == True
    assert result["approved"] == False
    assert result["can_proceed"] == False


@test("Guard: Allows with approval for clean content")
def test_guard_allows_with_approval():
    result = run_guard(
        content="Clean email content",
        action="send_email",
        approval="APPROVED"
    )
    assert result["can_proceed"] == True
    assert result["approved"] == True


@test("Guard: Non-irreversible action allowed without approval")
def test_guard_allows_non_irreversible():
    result = run_guard(
        content="Just reading data",
        action="read",
        approval=None
    )
    assert result["can_proceed"] == True


@test("Guard: Delete is irreversible")
def test_guard_delete_requires_approval():
    result = run_guard(
        content="Deleting item",
        action="delete",
        approval=None
    )
    assert result["approval_required"] == True
    assert result["can_proceed"] == False


@test("Guard: Pay is irreversible")
def test_guard_pay_requires_approval():
    result = run_guard(
        content="Processing payment",
        action="pay",
        approval=None
    )
    assert result["approval_required"] == True
    assert result["can_proceed"] == False


# ============ SAFE LOGGER TESTS ============

@test("SafeLogger: Masks password fields")
def test_logger_masks_password():
    from playwright_safe_logger import SafeLogger, is_sensitive_field

    assert is_sensitive_field("#password") == True
    assert is_sensitive_field("#pwd") == True
    assert is_sensitive_field("#secret-key") == True
    assert is_sensitive_field("#username") == False


@test("SafeLogger: Detects irreversible actions")
def test_logger_detects_irreversible():
    from playwright_safe_logger import is_irreversible_action

    assert is_irreversible_action("button:text('Send')") == True
    assert is_irreversible_action("button:text('Delete')") == True
    assert is_irreversible_action("button:text('Submit')") == True
    assert is_irreversible_action("button:text('Pay Now')") == True
    assert is_irreversible_action("button:text('Login')") == False
    assert is_irreversible_action("button:text('Cancel')") == False


@test("SafeLogger: mask_text hides content")
def test_logger_mask_text():
    from playwright_safe_logger import mask_text

    masked = mask_text("SuperSecretPassword123")
    assert "SuperSecret" not in masked
    assert "len=22" in masked
    assert "REDACTED" in masked


# ============ TEST RUNNER ============

def run_tests():
    global PASSED, FAILED

    print("=" * 60)
    print("SECURITY GUARDRAILS REGRESSION TESTS")
    print("=" * 60)
    print()

    for name, test_func in TESTS:
        try:
            test_func()
            print(f"  [PASS] {name}")
            PASSED += 1
        except AssertionError as e:
            print(f"  [FAIL] {name}")
            print(f"         {e}")
            FAILED += 1
        except Exception as e:
            print(f"  [ERROR] {name}")
            print(f"          {type(e).__name__}: {e}")
            FAILED += 1

    print()
    print("=" * 60)
    print(f"RESULTS: {PASSED} passed, {FAILED} failed, {len(TESTS)} total")
    print("=" * 60)

    return FAILED == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
