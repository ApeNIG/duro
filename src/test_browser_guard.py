"""
Quick test for browser_guard.py
"""
import sys
sys.path.insert(0, '.')

from browser_guard import (
    check_domain_allowed, normalize_domain, matches_domain_pattern,
    get_sandbox_config, check_browser_policy, get_browser_status,
    create_ephemeral_profile, cleanup_profile, validate_download,
    BrowserSandboxConfig
)


def test_domain_normalization():
    """Test domain normalization from URLs."""
    print("=== Testing Domain Normalization ===\n")

    test_cases = [
        ("https://example.com/path", "example.com"),
        ("http://www.example.com", "example.com"),
        ("https://api.example.com:8080/v1", "api.example.com"),
        ("example.com", "example.com"),
        ("https://sub.domain.example.com", "sub.domain.example.com"),
    ]

    passed = 0
    for url, expected in test_cases:
        result = normalize_domain(url)
        status = "PASS" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        print(f"  [{status}] {url} -> {result}")
        if result != expected:
            print(f"       expected: {expected}")

    print(f"\n  {passed}/{len(test_cases)} cases correct\n")
    return passed == len(test_cases)


def test_domain_pattern_matching():
    """Test wildcard domain pattern matching."""
    print("=== Testing Domain Pattern Matching ===\n")

    test_cases = [
        ("example.com", "example.com", True),
        ("api.example.com", "example.com", False),
        ("api.example.com", "*.example.com", True),
        ("example.com", "*.example.com", True),  # Wildcard matches root too
        ("sub.api.example.com", "*.example.com", True),
        ("example.org", "*.example.com", False),
        ("login.github.com", "github.com/login", False),  # Path not matched
    ]

    passed = 0
    for domain, pattern, expected in test_cases:
        result = matches_domain_pattern(domain, pattern)
        status = "PASS" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        print(f"  [{status}] '{domain}' matches '{pattern}': {result}")

    print(f"\n  {passed}/{len(test_cases)} cases correct\n")
    return passed == len(test_cases)


def test_domain_allowlist_blocklist():
    """Test domain allowlist and blocklist enforcement."""
    print("=== Testing Domain Allow/Block Lists ===\n")

    # Create test config with specific allow/block lists
    config = BrowserSandboxConfig(
        mode="strict",
        domain_allowlist=["example.com", "*.trusted.com"],
        domain_blocklist=["accounts.google.com", "*.bank.com"]
    )

    test_cases = [
        ("https://example.com", True, "in allowlist"),
        ("https://api.trusted.com", True, "matches wildcard allowlist"),
        ("https://untrusted.com", False, "not in strict allowlist"),
        ("https://accounts.google.com", False, "in blocklist"),
        ("https://chase.bank.com", False, "matches wildcard blocklist"),
    ]

    passed = 0
    for url, expected_allowed, desc in test_cases:
        allowed, reason = check_domain_allowed(url, config)
        status = "PASS" if allowed == expected_allowed else "FAIL"
        if allowed == expected_allowed:
            passed += 1
        print(f"  [{status}] {desc}: allowed={allowed}")
        print(f"       URL: {url}")
        print(f"       reason: {reason}")

    print(f"\n  {passed}/{len(test_cases)} cases correct\n")
    return passed == len(test_cases)


def test_standard_mode():
    """Test standard mode (no allowlist, only blocklist)."""
    print("=== Testing Standard Mode ===\n")

    config = BrowserSandboxConfig(mode="standard")

    test_cases = [
        ("https://example.com", True, "normal site"),
        ("https://api.github.com", True, "API endpoint"),
        ("https://accounts.google.com", False, "blocked auth endpoint"),
    ]

    passed = 0
    for url, expected_allowed, desc in test_cases:
        allowed, reason = check_domain_allowed(url, config)
        status = "PASS" if allowed == expected_allowed else "FAIL"
        if allowed == expected_allowed:
            passed += 1
        print(f"  [{status}] {desc}: allowed={allowed}")
        if not allowed:
            print(f"       reason: {reason}")

    print(f"\n  {passed}/{len(test_cases)} cases correct\n")
    return passed == len(test_cases)


def test_download_validation():
    """Test download file validation."""
    print("=== Testing Download Validation ===\n")

    config = BrowserSandboxConfig()

    test_cases = [
        ("document.pdf", 1024 * 1024, True, "allowed PDF"),
        ("data.csv", 5 * 1024 * 1024, True, "allowed CSV"),
        ("image.png", 2 * 1024 * 1024, True, "allowed image"),
        ("malware.exe", 1024, False, "blocked executable"),
        ("script.bat", 512, False, "blocked batch file"),
        ("payload.dll", 2048, False, "blocked DLL"),
        ("huge.pdf", 200 * 1024 * 1024, False, "file too large"),
        ("data.json", 50 * 1024 * 1024, True, "large but allowed JSON"),
    ]

    passed = 0
    for filename, size, expected_allowed, desc in test_cases:
        allowed, reason = validate_download(filename, size, config)
        status = "PASS" if allowed == expected_allowed else "FAIL"
        if allowed == expected_allowed:
            passed += 1
        print(f"  [{status}] {desc}: allowed={allowed}")
        if not allowed:
            print(f"       reason: {reason}")

    print(f"\n  {passed}/{len(test_cases)} cases correct\n")
    return passed == len(test_cases)


def test_ephemeral_profile():
    """Test ephemeral profile creation and cleanup."""
    print("=== Testing Ephemeral Profile ===\n")

    config = get_sandbox_config()
    profile = create_ephemeral_profile(config)

    profile_exists = profile.profile_dir.exists()
    print(f"  Profile created: {profile_exists}")
    print(f"  Profile ID: {profile.profile_id}")
    print(f"  Profile dir: {profile.profile_dir}")

    # Check subdirectories
    downloads_exists = (profile.profile_dir / "downloads").exists()
    cache_exists = (profile.profile_dir / "cache").exists()
    print(f"  Downloads subdir: {downloads_exists}")
    print(f"  Cache subdir: {cache_exists}")

    # Cleanup
    cleanup_success = cleanup_profile(profile)
    profile_gone = not profile.profile_dir.exists()
    print(f"  Cleanup success: {cleanup_success}")
    print(f"  Profile removed: {profile_gone}")

    passed = profile_exists and downloads_exists and cache_exists and cleanup_success and profile_gone
    print(f"\n  {'PASS' if passed else 'FAIL'}\n")
    return passed


def test_browser_status():
    """Test browser status reporting."""
    print("=== Testing Browser Status ===\n")

    status = get_browser_status()

    print(f"  Mode: {status['mode']}")
    print(f"  Active profiles: {status['active_profiles']}")
    print(f"  Downloads dir: {status['downloads_dir']}")
    print(f"  Max download size: {status['max_download_size_mb']}MB")
    print(f"  Disable clipboard: {status['disable_clipboard']}")
    print(f"  Disable password manager: {status['disable_password_manager']}")
    print(f"  Tag as untrusted: {status['tag_content_as_untrusted']}")

    # Check required fields exist
    required_fields = ['mode', 'active_profiles', 'downloads_dir', 'max_download_size_mb']
    all_present = all(f in status for f in required_fields)

    print(f"\n  {'PASS' if all_present else 'FAIL'}\n")
    return all_present


def test_browser_policy_check():
    """Test the main policy check function."""
    print("=== Testing Browser Policy Check ===\n")

    test_cases = [
        ("https://example.com", "navigate", True, "normal navigation"),
        ("https://api.github.com/repos", "navigate", True, "API endpoint"),
        ("https://accounts.google.com/signin", "navigate", False, "blocked auth"),
    ]

    passed = 0
    for url, action, expected_allowed, desc in test_cases:
        config = get_sandbox_config()
        allowed, reason = check_browser_policy(url, action, config)

        # In standard mode, blocklist still applies
        status = "PASS" if allowed == expected_allowed else "FAIL"
        if allowed == expected_allowed:
            passed += 1
        print(f"  [{status}] {desc}")
        print(f"       URL: {url}")
        print(f"       allowed: {allowed}, reason: {reason}")

    print(f"\n  {passed}/{len(test_cases)} cases correct\n")
    return passed == len(test_cases)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("BROWSER GUARD TEST SUITE")
    print("=" * 60 + "\n")

    results = []
    results.append(("Domain Normalization", test_domain_normalization()))
    results.append(("Domain Pattern Matching", test_domain_pattern_matching()))
    results.append(("Domain Allow/Block Lists", test_domain_allowlist_blocklist()))
    results.append(("Standard Mode", test_standard_mode()))
    results.append(("Download Validation", test_download_validation()))
    results.append(("Ephemeral Profile", test_ephemeral_profile()))
    results.append(("Browser Status", test_browser_status()))
    results.append(("Browser Policy Check", test_browser_policy_check()))

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
