"""
Trust Architecture Sanity Gauntlet
Tests the verification_state, blast_radius, and verified field fixes.
"""
import sys
import os

# Set HMAC key
os.environ["DURO_PROVENANCE_HMAC_KEYS"] = "v1:d2cfb01f37385f2f935f4d2ac36b0b867af52038f0d3b49552d116cb51111a11"

sys.path.insert(0, "src")
from artifacts import ArtifactStore

MEMORY_DIR = "C:/Users/sibag/.agent/memory"
DB_PATH = "C:/Users/sibag/.agent/duro_index.db"

store = ArtifactStore(MEMORY_DIR, DB_PATH)
test_facts = []

print("=" * 60)
print("TRUST ARCHITECTURE SANITY GAUNTLET")
print("=" * 60)
print()

# Test 1: Store fact claiming "verified" but no evidence
# Expect: verification_state should be downgraded to "unverified"
print("Test 1: Store verified fact WITHOUT evidence")
print("-" * 40)
success, fact_id, msg = store.store_fact(
    claim="TEST: Critical fact - should be downgraded",
    confidence=0.9,
    verification_state="verified",  # Trying to claim verified
    blast_radius="critical",
    # NO source_urls - should trigger downgrade
    tags=["test", "gauntlet"]
)
test_facts.append(fact_id)
print(f"  Store result: {msg}")

artifact = store.get_artifact(fact_id)
if artifact:
    data = artifact.get("data", {})
    vs = data.get("verification_state")
    v = data.get("verified")
    br = data.get("blast_radius")
    print(f"  verification_state: {vs} (expected: unverified)")
    print(f"  verified (deprecated): {v} (expected: False)")
    print(f"  blast_radius: {br} (expected: critical)")
    t1_pass = vs == "unverified" and v == False and br == "critical"
    print(f"  RESULT: {'PASS' if t1_pass else 'FAIL'}")
else:
    print("  ERROR: Could not retrieve artifact")
    t1_pass = False
print()

# Test 2: Store fact WITH evidence but verification_state="unverified"
# Expect: Should stay unverified (no auto-verify)
print("Test 2: Store fact WITH evidence but unverified")
print("-" * 40)
success2, fact_id2, msg2 = store.store_fact(
    claim="TEST: Has evidence but explicitly unverified",
    confidence=0.8,
    verification_state="unverified",
    source_urls=["https://example.com/evidence"],
    evidence_type="quote",
    tags=["test", "gauntlet"]
)
test_facts.append(fact_id2)
print(f"  Store result: {msg2}")

artifact2 = store.get_artifact(fact_id2)
if artifact2:
    data2 = artifact2.get("data", {})
    vs2 = data2.get("verification_state")
    v2 = data2.get("verified")
    print(f"  verification_state: {vs2} (expected: unverified)")
    print(f"  verified (deprecated): {v2} (expected: False)")
    t2_pass = vs2 == "unverified" and v2 == False
    print(f"  RESULT: {'PASS' if t2_pass else 'FAIL'}")
else:
    print("  ERROR: Could not retrieve artifact")
    t2_pass = False
print()

# Test 3: Store fact WITH evidence AND verification_state="verified"
# Expect: Should be verified (has evidence to support it)
print("Test 3: Store fact WITH evidence AND verified")
print("-" * 40)
success3, fact_id3, msg3 = store.store_fact(
    claim="TEST: Has evidence and explicitly verified",
    confidence=0.8,
    verification_state="verified",
    source_urls=["https://example.com/evidence"],
    evidence_type="quote",
    tags=["test", "gauntlet"]
)
test_facts.append(fact_id3)
print(f"  Store result: {msg3}")

artifact3 = store.get_artifact(fact_id3)
if artifact3:
    data3 = artifact3.get("data", {})
    vs3 = data3.get("verification_state")
    v3 = data3.get("verified")
    lva = data3.get("last_verified_at")
    print(f"  verification_state: {vs3} (expected: verified)")
    print(f"  verified (deprecated): {v3} (expected: True)")
    print(f"  last_verified_at: {lva} (expected: non-null)")
    t3_pass = vs3 == "verified" and v3 == True and lva is not None
    print(f"  RESULT: {'PASS' if t3_pass else 'FAIL'}")
else:
    print("  ERROR: Could not retrieve artifact")
    t3_pass = False
print()

# Summary
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Test 1 (downgrade verified without evidence): {'PASS' if t1_pass else 'FAIL'}")
print(f"Test 2 (evidence does NOT auto-verify):       {'PASS' if t2_pass else 'FAIL'}")
print(f"Test 3 (verified with evidence works):        {'PASS' if t3_pass else 'FAIL'}")
all_pass = t1_pass and t2_pass and t3_pass
print()
print(f"ALL TESTS: {'PASS' if all_pass else 'FAIL'}")
print("=" * 60)

# Cleanup
print()
print("Cleaning up test artifacts...")
for fid in test_facts:
    if fid:
        path = os.path.join(MEMORY_DIR, "facts", f"{fid}.json")
        try:
            os.remove(path)
            print(f"  Removed: {fid}")
        except Exception as e:
            print(f"  Failed to remove {fid}: {e}")

# Exit with appropriate code
sys.exit(0 if all_pass else 1)
