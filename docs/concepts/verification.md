# Verification

> "Every decision gets validated"

Verification is how Duro builds institutional memory that's actually correct. Storing knowledge is easy. Knowing if it worked is what matters.

## The Validation Loop

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   1. Make a decision                                │
│              ↓                                      │
│   2. Track the outcome (success/partial/failed)    │
│              ↓                                      │
│   3. Evaluate: what worked? what didn't?           │
│              ↓                                      │
│   4. Update confidence / create new rule           │
│              ↓                                      │
│   5. Next time: agent checks past decisions first  │
│              ↓                                      │
│   [COMPOUND INTELLIGENCE]                          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Decision Lifecycle

Every decision goes through states:

| Status | Meaning | Confidence |
|--------|---------|------------|
| `pending` | Just created, not yet tested | 0.5 |
| `validated` | Confirmed working | Increases |
| `reversed` | Didn't work, changed approach | Decreases |
| `superseded` | Replaced by newer decision | Archived |

## Validating a Decision

After a decision has been in use:

```javascript
duro_validate_decision({
  decision_id: "decision_20260210_xxx",
  status: "validated",
  expected_outcome: "Faster session lookups",
  actual_outcome: "60% latency reduction",
  result: "success"
})
```

The decision's confidence increases and it surfaces with higher priority in future recalls.

## Reversing a Decision

When a decision doesn't work:

```javascript
duro_validate_decision({
  decision_id: "decision_20260210_xxx",
  status: "reversed",
  expected_outcome: "Faster builds",
  actual_outcome: "Broke incremental compilation",
  result: "failed",
  next_action: "Revert to previous build config"
})
```

The decision is marked reversed and won't be recommended again.

## Superseding Decisions

When a newer decision replaces an older one:

```javascript
duro_supersede_fact({
  old_fact_id: "fact_20260101_xxx",
  new_fact_id: "fact_20260210_yyy",
  reason: "API v2 changed the rate limit"
})
```

The old decision links to the new one.

## Validation History

Every decision tracks its full history:

```javascript
duro_get_validation_history({
  decision_id: "decision_20260210_xxx"
})

// Returns:
// - Initial creation
// - First validation attempt
// - Reversal (if any)
// - Re-validation
// - etc.
```

This creates an audit trail of how knowledge evolved.

## Episode Evaluation

For complex work, Duro tracks episodes:

```javascript
// 1. Create episode
duro_create_episode({
  goal: "Fix authentication bug",
  plan: ["Investigate logs", "Find root cause", "Implement fix"]
})

// 2. Track actions
duro_add_episode_action({
  episode_id: "episode_xxx",
  summary: "Found JWT validation failing"
})

// 3. Close with result
duro_close_episode({
  episode_id: "episode_xxx",
  result: "success",
  result_summary: "Fixed JWT signature verification"
})

// 4. Evaluate
duro_evaluate_episode({
  episode_id: "episode_xxx",
  grade: "A",
  rubric: {
    outcome_quality: { score: 5, notes: "Bug fully fixed" },
    correctness_risk: { score: 1, notes: "Low risk" }
  }
})
```

## Why Verification Matters

Without verification:
- Stored decisions might be wrong
- No one knows what actually worked
- Bad advice persists forever

With verification:
- Validated decisions are trusted
- Failed approaches are marked
- Knowledge quality improves over time

## The Compound Effect

Each validation cycle:
1. Increases confidence in good decisions
2. Decreases confidence in bad ones
3. Creates patterns for skills
4. Builds institutional memory

Over time, your AI agent gets genuinely smarter—not just more verbose.

## Next Steps

- [Orchestration: Permission controls](/concepts/orchestration)
- [Validation tools reference](/reference/validation-tools)
- [Decision lifecycle guide](/guide/validation)
