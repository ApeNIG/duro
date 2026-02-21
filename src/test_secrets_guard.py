"""
Quick test for secrets_guard.py
"""
import sys
sys.path.insert(0, '.')

from secrets_guard import (
    scan_string, scan_arguments, redact_arguments,
    check_secrets_policy, check_bash_secrets,
    SECRET_PATTERNS, SENSITIVE_TOOLS
)

def test_pattern_detection():
    """Test various secret patterns are detected."""
    print("=== Testing Pattern Detection ===\n")

    # NOTE: These are intentionally fake patterns for testing. They will NOT work
    # with any real service. The patterns are designed to match our regex while
    # being obviously fake to avoid false positives in secret scanning.
    # NOTE: Stripe patterns (sk_live_/sk_test_) are excluded from testing because
    # GitHub's push protection blocks them even with fake values.
    test_cases = [
        ("OpenAI Key", "sk-FAKE123TEST456DEMO789XXXX012XXp"),
        ("Anthropic Key", "sk-ant-FAKE-abcdefghijklmnopqrst"),
        ("AWS Access Key", "AKIATESTFAKEKEY7DEMO"),
        ("GitHub PAT", "ghp_FAKEtestTOKENforTESTINGonlyXXxxxYYYZ"),
        # Stripe Secret excluded - GitHub blocks sk_test_* patterns
        ("JWT Token", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0dXNlciJ9.TESTsignatureFAKE"),
        ("Database URL", "postgres://testuser:testpass@localhost:5432/testdb"),
        ("Password Assign", 'password = "testpassword123"'),
        ("API Key Assign", 'api_key: "FAKETESTKEY12345678901234"'),
        ("Private Key", "-----BEGIN RSA PRIVATE KEY-----"),
    ]

    passed = 0
    for name, content in test_cases:
        result = scan_string(content)
        status = "PASS" if result.has_secrets else "FAIL"
        if result.has_secrets:
            passed += 1
        print(f"  [{status}] {name}: {len(result.matches)} matches")
        if result.matches:
            for m in result.matches:
                print(f"       -> {m.pattern_name} (severity={m.severity})")
                print(f"          preview: {m.redacted_preview}")

    print(f"\n  {passed}/{len(test_cases)} patterns detected correctly\n")
    return passed == len(test_cases)


def test_argument_scanning():
    """Test scanning tool arguments."""
    print("=== Testing Argument Scanning ===\n")

    args = {
        "claim": "The API uses OpenAI with key sk-FAKE123TEST456DEMO789XXXX012XXp",
        "metadata": {
            "api_key": "fake_secret_for_testing",
            "nested": {
                "password": "testpass123"
            }
        },
        "tags": ["test", "AKIATESTFAKEKEY7DEMO"]
    }

    result = scan_arguments(args)
    print(f"  Found {len(result.matches)} secrets in arguments")
    print(f"  Blocked: {result.blocked}")

    for m in result.matches:
        print(f"    - {m.pattern_name} at {m.location}")

    print()
    return result.has_secrets


def test_argument_redaction():
    """Test that secrets are properly redacted."""
    print("=== Testing Argument Redaction ===\n")

    args = {
        "command": "curl -H 'Authorization: Bearer sk-FAKE123TEST456DEMO789XXXX012XXp' https://api.example.com",
        "claim": "Using database postgres://testuser:testpass@localhost:5432/testdb",
    }

    redacted = redact_arguments(args)
    print("  Original:")
    print(f"    command: {args['command'][:60]}...")
    print(f"    claim: {args['claim']}")
    print("\n  Redacted:")
    print(f"    command: {redacted['command'][:60]}...")
    print(f"    claim: {redacted['claim']}")

    # Check that secrets are actually redacted
    has_redacted = "[REDACTED:" in redacted['command'] or "[REDACTED:" in redacted['claim']
    print(f"\n  Contains [REDACTED:...]: {has_redacted}")
    print()
    return has_redacted


def test_sensitive_tools():
    """Test that sensitive tools block secrets."""
    print("=== Testing Sensitive Tool Blocking ===\n")

    args_with_secret = {
        "claim": "API key is sk-FAKE123TEST456DEMO789XXXX012XXp"
    }

    # Should block on memory tools
    allowed, reason, _ = check_secrets_policy("duro_store_fact", args_with_secret)
    print(f"  duro_store_fact: allowed={allowed}")
    print(f"    reason: {reason}")

    # Should allow on Bash (it handles secrets legitimately)
    allowed2, reason2, _ = check_secrets_policy("Bash", args_with_secret)
    print(f"  Bash: allowed={allowed2}")
    print(f"    reason: {reason2}")

    print()
    return not allowed and allowed2


def test_bash_env_exposure():
    """Test bash command secret exposure detection."""
    print("=== Testing Bash Env Var Exposure ===\n")

    test_cases = [
        ("echo $API_KEY", False, "echoing secret env var"),
        ("echo $PATH", True, "safe env var"),
        ("printenv", False, "dumps all env"),
        ("env | grep -v SECRET", True, "filtered env dump"),
        ("env", False, "unfiltered env dump"),
        ("export MY_VAR=value", True, "setting non-secret var"),
        ("echo $SECRET_TOKEN", False, "echoing secret token"),
    ]

    passed = 0
    for cmd, expected_allowed, desc in test_cases:
        allowed, reason = check_bash_secrets(cmd)
        status = "PASS" if allowed == expected_allowed else "FAIL"
        if allowed == expected_allowed:
            passed += 1
        print(f"  [{status}] {desc}: allowed={allowed}")
        if not allowed:
            print(f"       -> {reason}")

    print(f"\n  {passed}/{len(test_cases)} cases correct\n")
    return passed == len(test_cases)


def test_output_scanning():
    """Test post-execution output scanning and redaction."""
    print("=== Testing Output Scanning (Post-Execution) ===\n")

    from secrets_guard import scan_and_redact_output, should_scan_output

    # Test output with embedded secret
    output = """Command output:
    API Response: {"auth": "sk-FAKE123TEST456DEMO789XXXX012XXp", "data": "success"}
    Connection established to postgres://testuser:testpass@localhost:5432/testdb
    """

    result = scan_and_redact_output(output, "Bash")

    print(f"  Had secrets: {result.had_secrets}")
    print(f"  Redaction count: {result.redaction_count}")

    if result.had_secrets:
        print(f"  Original length: {len(output)}")
        print(f"  Redacted length: {len(result.redacted_output)}")
        # Check that secrets are actually redacted
        has_redacted = "[REDACTED:" in result.redacted_output
        print(f"  Contains [REDACTED:]: {has_redacted}")

        # Check original secrets are gone
        original_secrets_gone = "sk-FAKE" not in result.redacted_output and "testpass" not in result.redacted_output
        print(f"  Original secrets removed: {original_secrets_gone}")
    else:
        has_redacted = False
        original_secrets_gone = False

    # Test should_scan_output
    should_scan_bash = should_scan_output("Bash")
    should_scan_status = should_scan_output("duro_status")

    print(f"\n  should_scan_output('Bash'): {should_scan_bash}")
    print(f"  should_scan_output('duro_status'): {should_scan_status}")

    passed = result.had_secrets and has_redacted and original_secrets_gone and should_scan_bash and not should_scan_status
    print(f"\n  {'PASS' if passed else 'FAIL'}\n")
    return passed


def test_safe_content():
    """Test that normal content is not flagged."""
    print("=== Testing Safe Content (No False Positives) ===\n")

    safe_cases = [
        ("Normal text", "This is just regular text without any secrets."),
        ("Short values", "key=123"),
        ("Code", "def my_function(api_client): return api_client.get()"),
        ("UUID", "550e8400-e29b-41d4-a716-446655440000"),
    ]

    passed = 0
    for name, content in safe_cases:
        result = scan_string(content)
        status = "PASS" if not result.has_secrets else "FAIL"
        if not result.has_secrets:
            passed += 1
        print(f"  [{status}] {name}: {len(result.matches)} false positives")

    print(f"\n  {passed}/{len(safe_cases)} cases had no false positives\n")
    return passed == len(safe_cases)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SECRETS GUARD TEST SUITE")
    print("=" * 60 + "\n")

    results = []
    results.append(("Pattern Detection", test_pattern_detection()))
    results.append(("Argument Scanning", test_argument_scanning()))
    results.append(("Argument Redaction", test_argument_redaction()))
    results.append(("Sensitive Tools", test_sensitive_tools()))
    results.append(("Bash Env Exposure", test_bash_env_exposure()))
    results.append(("Output Scanning", test_output_scanning()))
    results.append(("Safe Content", test_safe_content()))

    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            all_passed = False

    print("\n" + ("ALL TESTS PASSED" if all_passed else "SOME TESTS FAILED"))
    sys.exit(0 if all_passed else 1)
