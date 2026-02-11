# Proposal: Behavior-Based Rule Triggering

**Date:** 2026-02-11
**Type:** enhancement
**Status:** pending
**Target:** Duro MCP / Claude Code hooks

---

## Problem

Rule `rule_006` (Layered Governance Constitution) enforces critical boundaries:
- No silent waiver creation
- No direct edits to devkit.config.json
- Waivers must go through PRs

**Current enforcement:** Keyword matching against task description.

**Vulnerability:** Users can bypass by rephrasing:

| Phrasing | Contains Keyword? | Triggered? |
|----------|-------------------|------------|
| "add a waiver for lint" | Yes ("waiver") | ✅ |
| "exempt lint temporarily" | No | ❌ |
| "skip check in CI" | No | ❌ |
| "bypass the failing test" | No | ❌ |

The rule fires on *description*, not *behavior*. A creative prompt can slip past.

---

## Proposed Solution

### Behavior-Based Triggering

Trigger rules based on **what the agent is about to do**, not what the user said.

```
Before executing:
  Write(file_path=".devkit-waiver.yml", ...)

Check:
  Does file_path match any rule's file_patterns?

If yes:
  Trigger rule, apply enforcement checks
```

### Implementation Options

#### Option A: Pre-Execution Hook in Claude Code

Claude Code already has hooks. Add a pre-write hook:

```yaml
# .claude/hooks/pre-write.yml
triggers:
  - pattern: "**/.devkit-waiver.yml"
    action: "duro_check_rules --file-trigger"
  - pattern: "**/devkit.config.json"
    action: "duro_check_rules --file-trigger"
```

**Pros:** Uses existing hook system
**Cons:** Requires hook configuration per repo

#### Option B: Duro MCP Enhancement

Extend `duro_check_rules` to accept tool context:

```python
duro_check_rules(
  task_description="exempt lint",
  pending_action={
    "tool": "Write",
    "file_path": ".devkit-waiver.yml"
  }
)
```

The MCP checks both keywords AND file patterns.

**Pros:** Centralized, works across all repos
**Cons:** Requires MCP code change

#### Option C: Wrapper Function

Create a "safe write" function that checks rules before writing:

```typescript
async function safeWrite(filePath: string, content: string) {
  const rules = await duro.checkRules({ file_trigger: filePath });
  if (rules.some(r => r.decision === 'deny')) {
    throw new GovernanceViolation(rules);
  }
  return write(filePath, content);
}
```

**Pros:** Can implement immediately
**Cons:** Requires discipline to use wrapper

---

## Recommended Approach

**Phase 1 (Now):** Document the limitation. The constitution works for obvious cases.

**Phase 2 (When needed):** Implement Option B - enhance Duro MCP to accept pending action context.

**Phase 3 (Hardening):** Add Claude Code hooks as defense-in-depth.

---

## Evidence

Test results from 2026-02-11:

```
Task: "bypass the lint check"        → No trigger
Task: "skip check in CI pipeline"    → No trigger
Task: "edit .devkit-waiver.yml file" → Triggered (substring "waiver")
```

Adding new keywords to index.json did not make them matchable - the MCP has fixed matching logic.

---

## Risk Assessment

**Medium risk.** The constitution can be bypassed, but:
1. Requires intentional rephrasing
2. Git history shows what actually happened
3. CI (DevKit) still enforces at merge time

The current keyword-based system is "advisory with teeth" rather than "bulletproof."

---

## Decision Requested

- [ ] Accept limitation for now, revisit when needed
- [ ] Prioritize Option B (Duro MCP enhancement)
- [ ] Implement Option C (wrapper) as interim solution

---

**Proposed by:** Claude
**References:**
- decision_20260211_092101_jn3f9k (Constitution)
- fact_20260211_093659_6tqobx (Bypass vulnerability)
- rule_006 (Layered Governance Constitution)
