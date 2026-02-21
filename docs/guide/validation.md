# Validating Decisions

Close the feedback loop by tracking what actually worked.

## Why Validate?

Storing decisions is easy. Knowing if they worked is what matters.

Without validation:
- Bad decisions persist
- No one knows what worked
- Same mistakes repeat

With validation:
- Confidence in good decisions
- Failed approaches are marked
- Knowledge quality improves

## Decision Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   CREATE ──► PENDING ──► [use in practice] ──►          │
│                                                         │
│   ┌───────────────────────────────────────────────────┐ │
│   │                                                   │ │
│   │   ┌──► VALIDATED (worked)                         │ │
│   │   │                                               │ │
│   │   ├──► REVERSED (didn't work)                     │ │
│   │   │                                               │ │
│   │   └──► SUPERSEDED (replaced)                      │ │
│   │                                                   │ │
│   └───────────────────────────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Storing a Decision

```javascript
duro_store_decision({
  decision: "Use Redis for session storage instead of PostgreSQL",
  rationale: "PostgreSQL sessions causing 200ms latency per request",
  alternatives: [
    "Keep PostgreSQL with connection pooling",
    "Use in-memory sessions"
  ],
  tags: ["architecture", "performance"]
})
```

The decision starts with:
- Status: `pending`
- Confidence: 0.5

## Validating Success

When the decision works out:

```javascript
duro_validate_decision({
  decision_id: "decision_20260210_xxx",
  status: "validated",
  expected_outcome: "Faster session lookups",
  actual_outcome: "Latency reduced from 200ms to 20ms (90% improvement)",
  result: "success"
})
```

Effects:
- Status changes to `validated`
- Confidence increases
- Surfaces with higher priority in future recalls

## Reversing Failure

When the decision doesn't work:

```javascript
duro_validate_decision({
  decision_id: "decision_20260210_xxx",
  status: "reversed",
  expected_outcome: "Faster builds",
  actual_outcome: "Broke incremental compilation, builds 3x slower",
  result: "failed",
  next_action: "Revert to previous build config"
})
```

Effects:
- Status changes to `reversed`
- Confidence decreases
- Won't be recommended in future

## Superseding Decisions

When a newer decision replaces an older one:

```javascript
// First, store the new decision
duro_store_decision({
  decision: "Use Redis Cluster instead of single Redis",
  rationale: "Single Redis hitting memory limits"
})

// Then supersede the old one
duro_validate_decision({
  decision_id: "decision_20260210_old",
  status: "superseded",
  notes: "Replaced by Redis Cluster decision"
})
```

## Finding Unreviewed Decisions

List decisions that need review:

```javascript
duro_list_unreviewed_decisions({
  older_than_days: 14,
  include_tags: ["architecture"],
  limit: 10
})
```

This surfaces decisions old enough to have outcomes but not yet validated.

## Review Workflow

### Full Context Review

```javascript
duro_review_decision({
  decision_id: "decision_20260210_xxx",
  dry_run: true  // Just show context
})
```

This loads:
- Decision details
- Validation history
- Linked episodes/incidents
- Recent related changes

### Then Validate

```javascript
duro_review_decision({
  decision_id: "decision_20260210_xxx",
  dry_run: false,
  status: "validated",
  result: "success",
  actual_outcome: "Working well after 2 weeks"
})
```

## Validation History

See full history of a decision:

```javascript
duro_get_validation_history({
  decision_id: "decision_20260210_xxx"
})
```

Returns chronological events:
- Initial creation
- First validation
- Any reversals
- Re-validations

## Best Practices

### Validate When You Have Evidence

Don't validate immediately. Wait until you have real outcome data:
- Performance metrics
- Error rates
- User feedback
- Time in production

### Be Honest About Failures

Reversing a decision is valuable:
- Prevents recommending bad approaches
- Documents what doesn't work
- Builds institutional knowledge

### Include Next Actions

When reversing, always specify what to do instead:

```javascript
duro_validate_decision({
  ...
  status: "reversed",
  next_action: "Use approach B instead"
})
```

### Link to Episodes

Connect validation to the work that provides evidence:

```javascript
duro_validate_decision({
  decision_id: "decision_xxx",
  episode_id: "episode_yyy",  // Links to supporting evidence
  status: "validated"
})
```

## Periodic Review

### Weekly Habit

```javascript
// Review 3 old decisions each week
duro_review_next_decisions({
  n: 3,
  older_than_days: 14
})
```

This installs the habit of closing feedback loops.

## Next Steps

- [Validation tools reference](/reference/validation-tools)
- [Verification concepts](/concepts/verification)
- [Episode tracking](/reference/episodes)
