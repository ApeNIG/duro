# REVIEW REQUEST: Phase 2.2 Adversarial Testing

## Overview

Build adversarial tests that prove Duro's memory system is trustworthy under stress, not just functional. These tests go beyond "does it work" to "does it fail safely and correctly."

## Why This Matters

Current smoke tests verify the happy path:
- Store artifact → retrieve artifact ✓
- Evaluate episode → confidence updates ✓
- Search query → results returned ✓

But we haven't tested:
- What happens when similar-but-wrong facts exist?
- Can bad data corrupt the system?
- Does decay actually work over time?
- Can the audit chain be tampered with?

## Proposed Test Categories

### Test 1: Adversarial Retrieval (Precision Under Confusion)

**Goal:** Verify semantic search returns the RIGHT fact, not just A fact.

**Test Design:**
```python
# Store 5 similar facts with subtle differences
facts = [
    "Duro uses SQLite for storage",           # TRUE
    "Duro uses PostgreSQL for storage",       # FALSE - wrong DB
    "Duro uses SQLite for caching",           # FALSE - wrong purpose
    "Durok uses SQLite for storage",          # FALSE - typo in name
    "Duro utilized SQLite for storage",       # TRUE - synonym
]

# Query: "What database does Duro use?"
# Expected: Return facts[0] and facts[4] with high confidence
# Expected: NOT return facts[1], facts[2], facts[3]
```

**Metrics:**
- Precision@1: Is the top result correct?
- Precision@3: Are top 3 results all correct?
- Wrong-but-confident rate: How often do we return wrong facts with confidence > 0.7?

**Pass Criteria:**
- Precision@1 >= 0.9
- Wrong-but-confident rate < 0.05

---

### Test 2: Bad Memory Injection (Garbage In, Garbage Stays Low)

**Goal:** Verify low-confidence garbage doesn't rise to influence decisions.

**Test Design:**
```python
# Inject obviously wrong facts with low confidence
bad_facts = [
    {"claim": "Python is a compiled language", "confidence": 0.2},
    {"claim": "SQLite cannot handle concurrent reads", "confidence": 0.15},
    {"claim": "JSON is a binary format", "confidence": 0.1},
]

# Create episodes that DON'T use these facts
# Run evaluations with success results

# Verify: Bad facts should NOT gain confidence
# Verify: Bad facts should decay over time
# Verify: Bad facts should NOT appear in proactive_recall
```

**Metrics:**
- Confidence creep rate: Do unused bad facts stay low?
- Pollution rate: Do bad facts contaminate good queries?

**Pass Criteria:**
- Bad facts never exceed 0.3 confidence without explicit reinforcement
- Bad facts don't appear in top 5 of unrelated queries

---

### Test 3: Staleness/Drift Simulation (Time Decay Works)

**Goal:** Verify unreinforced facts decay and newer facts win.

**Test Design:**
```python
# Create fact at T=0
old_fact = store_fact("React 17 is the latest version", confidence=0.8)

# Simulate 30 days passing (mock time or use valid_from manipulation)
simulate_time_passing(days=30)

# Run decay
apply_decay(dry_run=False)

# Verify: old_fact confidence should have decreased
# Verify: pinned facts should NOT decay

# Create newer contradicting fact
new_fact = store_fact("React 19 is the latest version", confidence=0.8)

# Query: "What is the latest React version?"
# Verify: new_fact should rank higher than old_fact
```

**Metrics:**
- Decay rate correctness: Does confidence drop as expected per formula?
- Recency bias: Do newer facts beat stale facts?
- Pin immunity: Do pinned facts resist decay?

**Pass Criteria:**
- Unpinned facts at 30 days show measurable confidence drop
- Pinned facts show zero confidence change
- Newer facts rank above older facts with same initial confidence

---

### Test 4: Audit Chain Attack (Tamper Detection)

**Goal:** Verify the audit log detects tampering.

**Test Design:**
```python
# Perform legitimate operations
delete_artifact(id="test_fact_1", reason="Test cleanup")
delete_artifact(id="test_fact_2", reason="Test cleanup")

# Get current audit chain state
chain_before = query_audit_log(verify_chain=True)
assert chain_before["chain_valid"] == True

# ATTACK 1: Delete an entry from audit log
manually_delete_audit_entry(index=1)
chain_after = query_audit_log(verify_chain=True)
assert chain_after["chain_valid"] == False  # Should detect

# ATTACK 2: Modify an entry's content
reset_audit_log()  # Restore valid state
manually_modify_audit_entry(index=0, new_reason="Hacked")
chain_after = query_audit_log(verify_chain=True)
assert chain_after["chain_valid"] == False  # Should detect

# ATTACK 3: Replay old entry
reset_audit_log()
replay_old_entry()
chain_after = query_audit_log(verify_chain=True)
assert chain_after["chain_valid"] == False  # Should detect
```

**Metrics:**
- Deletion detection rate: Catch missing entries
- Modification detection rate: Catch altered entries
- Replay detection rate: Catch duplicate/out-of-order entries

**Pass Criteria:**
- 100% detection of deletions
- 100% detection of modifications
- 100% detection of replays

---

## Implementation Plan

### Phase A: Test Infrastructure (Day 1 morning)
- [ ] A.1 Create `tests/adversarial/` directory
- [ ] A.2 Create `AdversarialTestHarness` class with:
  - Isolated test database (not production)
  - Time simulation helpers
  - Metric collection
  - Cleanup utilities
- [ ] A.3 Create `conftest.py` with fixtures

### Phase B: Retrieval Tests (Day 1 afternoon)
- [ ] B.1 Implement `test_adversarial_retrieval.py`
- [ ] B.2 Create confusion sets (similar facts)
- [ ] B.3 Add precision@k metric calculation
- [ ] B.4 Add wrong-but-confident detection

### Phase C: Injection Tests (Day 2 morning)
- [ ] C.1 Implement `test_bad_memory_injection.py`
- [ ] C.2 Create bad fact templates
- [ ] C.3 Add confidence creep detection
- [ ] C.4 Add pollution rate measurement

### Phase D: Decay Tests (Day 2 afternoon)
- [ ] D.1 Implement `test_staleness_decay.py`
- [ ] D.2 Create time simulation utilities
- [ ] D.3 Add decay formula verification
- [ ] D.4 Add recency ranking tests

### Phase E: Audit Tests (Day 3 morning)
- [ ] E.1 Implement `test_audit_chain_attack.py`
- [ ] E.2 Create tamper simulation utilities
- [ ] E.3 Add chain integrity verification
- [ ] E.4 Test all three attack vectors

### Phase F: Integration (Day 3 afternoon)
- [ ] F.1 Create `run_adversarial_suite.py` runner
- [ ] F.2 Add to pre-push hook (optional, may be slow)
- [ ] F.3 Create `ADVERSARIAL_TESTING.md` documentation
- [ ] F.4 Log results to Duro memory

---

## My Assumptions

1. The current embedding model (bge-small-en-v1.5) can distinguish subtle semantic differences
2. Decay formula is: `new_conf = old_conf * (0.99 ^ days_since_reinforcement)`
3. Audit chain uses SHA256 hash chaining
4. Test database can be isolated from production database

## What I'm Uncertain About

1. Is the embedding model actually good enough for adversarial retrieval? May need threshold tuning.
2. Should decay tests use real time.sleep() or mock time? Mock is faster but less realistic.
3. How do we "tamper" with the audit log for testing without breaking things?
4. Should these tests run in CI or only manually?

## Potential Bugs If We Don't Do This Right

1. **Test pollution:** If tests use production DB, they'll corrupt real memory
2. **Flaky tests:** If we rely on embedding similarity thresholds, tests may be non-deterministic
3. **Time-dependent bugs:** If decay tests use wall clock, they'll behave differently on different days
4. **Audit chain corruption:** If tamper tests don't clean up, audit chain may be permanently invalid

## Questions for Reviewer

1. What edge cases am I missing in the adversarial retrieval tests?
2. Is the decay formula I assumed correct? Should I verify it first?
3. For audit chain attacks, is there a safer way to test tampering without actually tampering?
4. Should we add a 5th test category? (e.g., concurrent access, embedding drift over model updates)
5. Are the pass criteria thresholds reasonable or too strict/lenient?

---

## Files to Create

```
~/.agent/
├── tests/
│   └── adversarial/
│       ├── __init__.py
│       ├── conftest.py
│       ├── harness.py
│       ├── test_adversarial_retrieval.py
│       ├── test_bad_memory_injection.py
│       ├── test_staleness_decay.py
│       ├── test_audit_chain_attack.py
│       └── run_adversarial_suite.py
└── ADVERSARIAL_TESTING.md
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Retrieval Precision@1 | >= 90% |
| Wrong-but-confident rate | < 5% |
| Bad fact confidence creep | 0% without reinforcement |
| Decay formula accuracy | Exact match to spec |
| Audit tampering detection | 100% |
| Test suite runtime | < 60 seconds |

---

_Generated by Claude Code for review by Codex/ChatGPT_
