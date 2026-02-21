"""
Quick test for audit_log.py - Layer 5 unified security audit
"""
import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, '.')

# Set a test HMAC key
os.environ["DURO_AUDIT_HMAC_KEY"] = "test-hmac-key-for-testing-only"

from audit_log import (
    AuditEvent, AuditActor, ChainInfo,
    append_event, query_log, verify_log, get_audit_stats,
    build_gate_event, build_secrets_event, build_workspace_event, build_browser_event,
    canonical_json, compute_payload_hash, compute_chain_hash, compute_hmac_signature,
    get_head, GENESIS_HASH, EventType, Severity,
    UNIFIED_AUDIT_FILE, AUDIT_HEAD_FILE
)


def test_canonical_json():
    """Test canonical JSON serialization."""
    print("=== Testing Canonical JSON ===\n")

    # Order shouldn't matter
    d1 = {"b": 2, "a": 1, "c": 3}
    d2 = {"a": 1, "b": 2, "c": 3}

    c1 = canonical_json(d1)
    c2 = canonical_json(d2)

    print(f"  d1 = {d1}")
    print(f"  d2 = {d2}")
    print(f"  canonical(d1) = {c1}")
    print(f"  canonical(d2) = {c2}")
    print(f"  Equal: {c1 == c2}")

    passed = c1 == c2
    print(f"\n  {'PASS' if passed else 'FAIL'}\n")
    return passed


def test_hash_chain():
    """Test hash chain computation."""
    print("=== Testing Hash Chain ===\n")

    event = AuditEvent(
        event_type=EventType.GATE_DECISION,
        tool="test_tool",
        decision="ALLOW",
        reason="test reason",
    )

    payload_hash = compute_payload_hash(event)
    chain_hash = compute_chain_hash(GENESIS_HASH, payload_hash)

    print(f"  Payload hash: {payload_hash[:40]}...")
    print(f"  Chain hash: {chain_hash[:40]}...")

    # Verify HMAC signature
    from audit_log import get_hmac_key
    hmac_key = get_hmac_key()
    if hmac_key:
        sig = compute_hmac_signature(chain_hash, hmac_key)
        print(f"  HMAC signature: {sig[:40]}...")
        has_sig = sig.startswith("hmac-sha256:")
    else:
        has_sig = False
        print("  HMAC key not available")

    passed = payload_hash.startswith("sha256:") and chain_hash.startswith("sha256:")
    print(f"\n  {'PASS' if passed else 'FAIL'}\n")
    return passed


def test_event_creation():
    """Test creating various event types."""
    print("=== Testing Event Creation ===\n")

    # Gate event
    gate_event = build_gate_event(
        tool_name="duro_delete_artifact",
        decision="DENY",
        reason="Not allowed without approval",
        risk_level="destructive",
        domain="knowledge",
        action_id="duro_delete_artifact:abc123",
        args_hash="abc123",
        args_preview={"artifact_id": "[REDACTED]"},
    )
    print(f"  Gate event type: {gate_event.event_type}")
    print(f"  Gate severity: {gate_event.severity}")

    # Secrets event
    secrets_event = build_secrets_event(
        event_type=EventType.SECRETS_BLOCKED,
        tool_name="duro_store_fact",
        action="blocked",
        reason="API key detected in claim",
        match_count=1,
        patterns=["openai_key"],
    )
    print(f"  Secrets event type: {secrets_event.event_type}")

    # Workspace event
    ws_event = build_workspace_event(
        event_type=EventType.WORKSPACE_DENYLIST,
        path="C:/Windows/System32",
        reason="Path in critical denylist",
        tool_name="Write",
    )
    print(f"  Workspace event type: {ws_event.event_type}")

    # Browser event
    browser_event = build_browser_event(
        event_type=EventType.BROWSER_DOMAIN_BLOCKED,
        url="https://accounts.google.com",
        reason="Auth endpoint blocked",
    )
    print(f"  Browser event type: {browser_event.event_type}")

    passed = (
        gate_event.event_type == EventType.GATE_DECISION and
        secrets_event.event_type == EventType.SECRETS_BLOCKED and
        ws_event.event_type == EventType.WORKSPACE_DENYLIST and
        browser_event.event_type == EventType.BROWSER_DOMAIN_BLOCKED
    )
    print(f"\n  {'PASS' if passed else 'FAIL'}\n")
    return passed


def test_append_and_query():
    """Test appending events and querying them back."""
    print("=== Testing Append and Query ===\n")

    # Clear any existing test events
    events_before = len(query_log(limit=1000))

    # Append a test event
    test_event = AuditEvent(
        event_type=EventType.GATE_DECISION,
        severity=Severity.INFO,
        tool="test_append_query",
        decision="ALLOW",
        reason="Test event for Layer 5",
        tags=["test", "layer5"],
    )

    event_id = append_event(test_event)
    print(f"  Appended event: {event_id}")

    # Query it back
    events = query_log(limit=10, tool="test_append_query")
    print(f"  Found {len(events)} matching events")

    if events:
        latest = events[0]
        print(f"  Latest event_id: {latest.get('event_id')}")
        print(f"  Has chain: {'chain' in latest}")
        if 'chain' in latest:
            chain = latest['chain']
            print(f"  Chain prev: {chain.get('prev', '')[:30]}...")
            print(f"  Chain hash: {chain.get('hash', '')[:30]}...")
            has_sig = chain.get('sig') is not None
            print(f"  Chain sig: {'present' if has_sig else 'absent'}")

    passed = len(events) > 0 and events[0].get('event_id') == event_id
    print(f"\n  {'PASS' if passed else 'FAIL'}\n")
    return passed


def test_verify_chain():
    """Test chain verification."""
    print("=== Testing Chain Verification ===\n")

    result = verify_log()

    print(f"  Valid: {result.valid}")
    print(f"  Total events: {result.total_events}")
    print(f"  Verified events: {result.verified_events}")
    print(f"  Signed: {result.signed}")
    if result.signed:
        print(f"  Signature valid: {result.signature_valid}")
    if not result.valid:
        print(f"  First broken line: {result.first_broken_line}")
        print(f"  Error: {result.error}")

    passed = result.valid
    print(f"\n  {'PASS' if passed else 'FAIL'}\n")
    return passed


def test_stats():
    """Test audit statistics."""
    print("=== Testing Audit Stats ===\n")

    stats = get_audit_stats()

    print(f"  Log exists: {stats['log_exists']}")
    print(f"  Log size: {stats['log_size_bytes']} bytes")
    print(f"  Total events: {stats['total_events']}")
    print(f"  HMAC key available: {stats['hmac_key_available']}")
    print(f"  Signed: {stats['signed']}")

    if stats['by_event_type']:
        print(f"  Event types: {list(stats['by_event_type'].keys())[:5]}")

    passed = stats['log_exists'] and stats['total_events'] > 0
    print(f"\n  {'PASS' if passed else 'FAIL'}\n")
    return passed


def test_head_management():
    """Test head file management."""
    print("=== Testing Head Management ===\n")

    prev_hash, last_event_id = get_head()

    print(f"  Current head hash: {prev_hash[:40]}...")
    print(f"  Last event ID: {last_event_id}")

    # Verify head file exists
    head_exists = AUDIT_HEAD_FILE.exists()
    print(f"  Head file exists: {head_exists}")

    passed = prev_hash != GENESIS_HASH or last_event_id == ""
    print(f"\n  {'PASS' if passed else 'FAIL'}\n")
    return passed


def test_multiple_events_chain():
    """Test that multiple events form a proper chain."""
    print("=== Testing Multiple Events Chain ===\n")

    # Append multiple events
    event_ids = []
    for i in range(3):
        event = AuditEvent(
            event_type=EventType.GATE_DECISION,
            severity=Severity.INFO,
            tool=f"test_chain_{i}",
            decision="ALLOW",
            reason=f"Chain test event {i}",
        )
        event_id = append_event(event)
        event_ids.append(event_id)

    print(f"  Created {len(event_ids)} events")

    # Verify chain integrity
    result = verify_log()
    print(f"  Chain valid: {result.valid}")
    print(f"  All verified: {result.verified_events == result.total_events}")

    passed = result.valid
    print(f"\n  {'PASS' if passed else 'FAIL'}\n")
    return passed


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("AUDIT LOG TEST SUITE (Layer 5)")
    print("=" * 60 + "\n")

    results = []
    results.append(("Canonical JSON", test_canonical_json()))
    results.append(("Hash Chain", test_hash_chain()))
    results.append(("Event Creation", test_event_creation()))
    results.append(("Append and Query", test_append_and_query()))
    results.append(("Chain Verification", test_verify_chain()))
    results.append(("Audit Stats", test_stats()))
    results.append(("Head Management", test_head_management()))
    results.append(("Multiple Events Chain", test_multiple_events_chain()))

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
