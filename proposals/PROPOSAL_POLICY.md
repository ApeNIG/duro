# Proposal Policy

## Gating Rule

**No new skill or rule without an eval link.**

Every proposal MUST include:

1. **Target eval(s)** - Which eval(s) is this meant to improve?
2. **Before score** - Current baseline metrics
3. **Expected after** - What improvement is predicted?
4. **5-minute test** - How to verify the change works

If a proposal can't answer these, it's not ready.

---

## Three-Stage Pipeline

```
proposals/pending/    →    proposals/trial/    →    proposals/approved/
     (raw ideas)           (testing phase)          (permanent)
                                 ↓
                          proposals/rejected/
                           (anti-patterns)
```

### Stage 1: Pending
- Raw idea captured
- Not yet tested
- Needs eval linkage

### Stage 2: Trial
- Allowed for testing but not permanent
- Must specify trial duration (default: 7 days)
- Must have success criteria
- Automatically demoted to rejected if criteria not met

### Stage 3: Approved
- Permanently integrated into rules/skills
- Survived trial period
- Measurably improved eval scores

### Rejected
- Keep as anti-pattern history
- Include reason for rejection
- Prevents re-proposing the same bad idea

---

## Proposal Template (Updated)

```markdown
# Proposal: [Name]

**Date:** YYYY-MM-DD
**Type:** new_rule | new_skill | rule_update | skill_update
**Status:** pending | trial | approved | rejected

## Eval Linkage (REQUIRED)
- **Target eval(s):** [eval_id(s)]
- **Current baseline:** [metric: value]
- **Expected improvement:** [metric: expected_value]
- **5-minute test:** [How to verify]

## What I Learned
[Description of the insight]

## Proposed Change
[Specific change to make]

## Evidence
[Data supporting the proposal]

## Risk Assessment
Low | Medium | High - [Explanation]

---
**Trial period:** [N days, if applicable]
**Trial start:**
**Trial end:**
**Trial result:**
**Approved by:**
**Date approved:**
```

---

## Weekly Review Loop

1. Pick 1-3 proposals from `pending/` to move to `trial/`
2. Run eval suite at end of trial period
3. Approve only if metrics improved
4. Move failures to `rejected/` with notes
5. Consolidate approved items into main rules/skills

---

*Policy established: 2026-02-10*
