"""
Provenance Signing Tests
========================

Tests for cryptographic signing and verification of artifact provenance.

Run: python test_provenance_signing.py

For CI: Set DURO_PROVENANCE_HMAC_KEYS to a test key before running.
"""

import json
import os
import sys
from copy import deepcopy

# === TEST SETUP ===
# Set test key before importing provenance_signing (it caches on import)
_TEST_KEY_ID = "test_v1"
_TEST_KEY_HEX = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # 32 bytes
_ORIGINAL_KEYS = os.environ.get("DURO_PROVENANCE_HMAC_KEYS")


def _setup_test_keys():
    """Set up test HMAC keys."""
    os.environ["DURO_PROVENANCE_HMAC_KEYS"] = f"{_TEST_KEY_ID}:{_TEST_KEY_HEX}"
    # Clear cache if module already loaded
    try:
        from provenance_signing import clear_key_cache
        clear_key_cache()
    except ImportError:
        pass


def _teardown_test_keys():
    """Restore original HMAC keys."""
    if _ORIGINAL_KEYS:
        os.environ["DURO_PROVENANCE_HMAC_KEYS"] = _ORIGINAL_KEYS
    elif "DURO_PROVENANCE_HMAC_KEYS" in os.environ:
        del os.environ["DURO_PROVENANCE_HMAC_KEYS"]
    # Clear cache
    try:
        from provenance_signing import clear_key_cache
        clear_key_cache()
    except ImportError:
        pass


# =============================================================================
# Tests
# =============================================================================

def test_sign_verify_valid():
    """Test: sign -> verify == valid"""
    from provenance_signing import sign_artifact, verify_artifact

    artifact = {
        "id": "fact_20260222_120000_abc123",
        "type": "fact",
        "version": "1.1",
        "created_at": "2026-02-22T12:00:00Z",
        "sensitivity": "public",
        "tags": ["test"],
        "source": {"workflow": "test"},
        "data": {"claim": "Test claim"},
        "provenance": {
            "trust_tier": "external",
            "workflow": "test",
            "created_by": "mcp",
            "created_via": "test",
            "validators": [],
        }
    }

    # Sign
    signed = sign_artifact(artifact)

    # Verify signature was added
    assert "signature" in signed.get("provenance", {}), "Signature not added to provenance"
    sig = signed["provenance"]["signature"]
    assert sig["key_id"] == _TEST_KEY_ID, f"Wrong key_id: {sig['key_id']}"
    assert sig["alg"] == "hmac-sha256", f"Wrong algorithm: {sig['alg']}"
    assert len(sig["mac_hex"]) == 64, f"Wrong MAC length: {len(sig['mac_hex'])}"

    # Verify
    status = verify_artifact(signed)
    assert status == "valid", f"Expected 'valid', got '{status}'"

    print("[PASS] test_sign_verify_valid")
    return True


def test_tamper_claim_invalid():
    """Test: tamper claim field -> invalid"""
    from provenance_signing import sign_artifact, verify_artifact

    artifact = {
        "id": "fact_20260222_120001_def456",
        "type": "fact",
        "version": "1.1",
        "created_at": "2026-02-22T12:00:01Z",
        "sensitivity": "public",
        "tags": ["test"],
        "source": {"workflow": "test"},
        "data": {"claim": "Original claim"},
        "provenance": {
            "trust_tier": "external",
            "workflow": "test",
            "created_by": "mcp",
            "created_via": "test",
            "validators": [],
        }
    }

    # Sign
    signed = sign_artifact(deepcopy(artifact))

    # Tamper with claim
    signed["data"]["claim"] = "TAMPERED claim"

    # Verify should fail
    status = verify_artifact(signed)
    assert status == "invalid", f"Expected 'invalid' after tampering claim, got '{status}'"

    print("[PASS] test_tamper_claim_invalid")
    return True


def test_tamper_workflow_invalid():
    """Test: tamper workflow field -> invalid"""
    from provenance_signing import sign_artifact, verify_artifact

    artifact = {
        "id": "fact_20260222_120002_ghi789",
        "type": "fact",
        "version": "1.1",
        "created_at": "2026-02-22T12:00:02Z",
        "sensitivity": "public",
        "tags": ["test"],
        "source": {"workflow": "test"},
        "data": {"claim": "Test claim"},
        "provenance": {
            "trust_tier": "external",
            "workflow": "test",
            "created_by": "mcp",
            "created_via": "test",
            "validators": [],
        }
    }

    # Sign
    signed = sign_artifact(deepcopy(artifact))

    # Tamper with workflow (try to escalate to look authoritative)
    signed["provenance"]["workflow"] = "orchestrator"

    # Verify should fail
    status = verify_artifact(signed)
    assert status == "invalid", f"Expected 'invalid' after tampering workflow, got '{status}'"

    print("[PASS] test_tamper_workflow_invalid")
    return True


def test_tamper_trust_tier_invalid():
    """Test: tamper trust_tier field -> invalid"""
    from provenance_signing import sign_artifact, verify_artifact

    artifact = {
        "id": "fact_20260222_120003_jkl012",
        "type": "fact",
        "version": "1.1",
        "created_at": "2026-02-22T12:00:03Z",
        "sensitivity": "public",
        "tags": ["test"],
        "source": {"workflow": "test"},
        "data": {"claim": "Test claim"},
        "provenance": {
            "trust_tier": "external",
            "workflow": "test",
            "created_by": "mcp",
            "created_via": "test",
            "validators": [],
        }
    }

    # Sign
    signed = sign_artifact(deepcopy(artifact))

    # Tamper with trust_tier (try to escalate trust)
    signed["provenance"]["trust_tier"] = "human_verified"

    # Verify should fail
    status = verify_artifact(signed)
    assert status == "invalid", f"Expected 'invalid' after tampering trust_tier, got '{status}'"

    print("[PASS] test_tamper_trust_tier_invalid")
    return True


def test_unknown_key_id():
    """Test: change key_id to unknown -> unknown_key"""
    from provenance_signing import sign_artifact, verify_artifact

    artifact = {
        "id": "fact_20260222_120004_mno345",
        "type": "fact",
        "version": "1.1",
        "created_at": "2026-02-22T12:00:04Z",
        "sensitivity": "public",
        "tags": ["test"],
        "source": {"workflow": "test"},
        "data": {"claim": "Test claim"},
        "provenance": {
            "trust_tier": "external",
            "workflow": "test",
            "created_by": "mcp",
            "created_via": "test",
            "validators": [],
        }
    }

    # Sign
    signed = sign_artifact(deepcopy(artifact))

    # Change key_id to unknown
    signed["provenance"]["signature"]["key_id"] = "unknown_key_v99"

    # Verify should return unknown_key
    status = verify_artifact(signed)
    assert status == "unknown_key", f"Expected 'unknown_key', got '{status}'"

    print("[PASS] test_unknown_key_id")
    return True


def test_unsigned_artifact():
    """Test: artifact without signature -> unsigned"""
    from provenance_signing import verify_artifact

    artifact = {
        "id": "fact_20260222_120005_pqr678",
        "type": "fact",
        "version": "1.1",
        "created_at": "2026-02-22T12:00:05Z",
        "sensitivity": "public",
        "tags": ["test"],
        "source": {"workflow": "test"},
        "data": {"claim": "Test claim"},
        # No provenance block
    }

    status = verify_artifact(artifact)
    assert status == "unsigned", f"Expected 'unsigned', got '{status}'"

    # Also test with provenance but no signature
    artifact["provenance"] = {
        "trust_tier": "external",
        "workflow": "test",
        "created_by": "mcp",
        "created_via": "test",
        "validators": [],
    }

    status = verify_artifact(artifact)
    assert status == "unsigned", f"Expected 'unsigned' for provenance without signature, got '{status}'"

    print("[PASS] test_unsigned_artifact")
    return True


def test_key_rotation():
    """Test: key rotation - old keys can still verify"""
    from provenance_signing import sign_artifact, verify_artifact, clear_key_cache

    # Create artifact and sign with v1 key
    artifact = {
        "id": "fact_20260222_120006_stu901",
        "type": "fact",
        "version": "1.1",
        "created_at": "2026-02-22T12:00:06Z",
        "sensitivity": "public",
        "tags": ["test"],
        "source": {"workflow": "test"},
        "data": {"claim": "Test claim"},
        "provenance": {
            "trust_tier": "external",
            "workflow": "test",
            "created_by": "mcp",
            "created_via": "test",
            "validators": [],
        }
    }

    # Sign with v1
    signed = sign_artifact(deepcopy(artifact))
    assert signed["provenance"]["signature"]["key_id"] == _TEST_KEY_ID

    # Simulate key rotation: add v2 as active, keep v1 for verification
    v2_key = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
    os.environ["DURO_PROVENANCE_HMAC_KEYS"] = f"test_v2:{v2_key},{_TEST_KEY_ID}:{_TEST_KEY_HEX}"
    clear_key_cache()

    # Old artifact signed with v1 should still verify
    status = verify_artifact(signed)
    assert status == "valid", f"Expected 'valid' with rotated keys, got '{status}'"

    # New artifacts should be signed with v2
    new_artifact = deepcopy(artifact)
    new_artifact["id"] = "fact_20260222_120007_vwx234"
    new_signed = sign_artifact(new_artifact)
    assert new_signed["provenance"]["signature"]["key_id"] == "test_v2", \
        f"New artifact should use v2 key, got {new_signed['provenance']['signature']['key_id']}"

    # New artifact should also verify
    status = verify_artifact(new_signed)
    assert status == "valid", f"Expected 'valid' for v2-signed artifact, got '{status}'"

    # Restore original test key
    os.environ["DURO_PROVENANCE_HMAC_KEYS"] = f"{_TEST_KEY_ID}:{_TEST_KEY_HEX}"
    clear_key_cache()

    print("[PASS] test_key_rotation")
    return True


def test_canonical_json_deterministic():
    """Test: canonical JSON is deterministic regardless of field order"""
    from provenance_signing import _canonical_json

    # Same data, different field order
    obj1 = {"z": 1, "a": 2, "m": 3}
    obj2 = {"a": 2, "m": 3, "z": 1}
    obj3 = {"m": 3, "z": 1, "a": 2}

    canon1 = _canonical_json(obj1)
    canon2 = _canonical_json(obj2)
    canon3 = _canonical_json(obj3)

    assert canon1 == canon2 == canon3, "Canonical JSON should be deterministic"
    assert canon1 == b'{"a":2,"m":3,"z":1}', f"Unexpected canonical form: {canon1}"

    print("[PASS] test_canonical_json_deterministic")
    return True


def test_missing_keys_env():
    """Test: missing DURO_PROVENANCE_HMAC_KEYS raises RuntimeError"""
    from provenance_signing import clear_key_cache, _get_keys

    # Remove env var
    original = os.environ.pop("DURO_PROVENANCE_HMAC_KEYS", None)
    clear_key_cache()

    try:
        _get_keys()
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "DURO_PROVENANCE_HMAC_KEYS not set" in str(e)
        print("[PASS] test_missing_keys_env")
    finally:
        # Restore
        if original:
            os.environ["DURO_PROVENANCE_HMAC_KEYS"] = original
        else:
            os.environ["DURO_PROVENANCE_HMAC_KEYS"] = f"{_TEST_KEY_ID}:{_TEST_KEY_HEX}"
        clear_key_cache()

    return True


def test_key_too_short():
    """Test: key shorter than 32 bytes raises ValueError"""
    from provenance_signing import clear_key_cache, _get_keys

    # Set short key
    original = os.environ.get("DURO_PROVENANCE_HMAC_KEYS")
    os.environ["DURO_PROVENANCE_HMAC_KEYS"] = "short_key:0123456789abcdef"  # Only 8 bytes
    clear_key_cache()

    try:
        _get_keys()
        assert False, "Should have raised ValueError for short key"
    except ValueError as e:
        assert "too short" in str(e)
        print("[PASS] test_key_too_short")
    finally:
        # Restore
        if original:
            os.environ["DURO_PROVENANCE_HMAC_KEYS"] = original
        else:
            os.environ["DURO_PROVENANCE_HMAC_KEYS"] = f"{_TEST_KEY_ID}:{_TEST_KEY_HEX}"
        clear_key_cache()

    return True


# =============================================================================
# Main
# =============================================================================

def main():
    """Run all provenance signing tests."""
    print("=" * 60)
    print("Provenance Signing Tests")
    print("=" * 60)
    print()

    # Set up test keys
    _setup_test_keys()
    print(f"Test key ID: {_TEST_KEY_ID}")
    print()

    passed = 0
    failed = 0

    tests = [
        test_sign_verify_valid,
        test_tamper_claim_invalid,
        test_tamper_workflow_invalid,
        test_tamper_trust_tier_invalid,
        test_unknown_key_id,
        test_unsigned_artifact,
        test_key_rotation,
        test_canonical_json_deterministic,
        test_missing_keys_env,
        test_key_too_short,
    ]

    try:
        for test_fn in tests:
            try:
                test_fn()
                passed += 1
            except AssertionError as e:
                print(f"[FAIL] {test_fn.__name__}: {e}")
                failed += 1
            except Exception as e:
                print(f"[ERROR] {test_fn.__name__}: {e}")
                failed += 1
    finally:
        # Clean up
        _teardown_test_keys()

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
