# Validation Tools

Tools for tracking outcomes and validating decisions.

## duro_validate_decision

Validate or reverse a decision based on evidence.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `decision_id` | string | Yes | The decision ID to validate |
| `status` | enum | Yes | `validated`, `reversed`, `superseded` |
| `expected_outcome` | string | No | What was expected to happen |
| `actual_outcome` | string | No | What actually happened |
| `result` | enum | No | `success`, `partial`, `failed` |
| `notes` | string | No | Additional context |
| `next_action` | string | No | What to do next |
| `confidence_delta` | number | No | Override confidence adjustment |
| `episode_id` | string | No | Episode ID that provides evidence |

### Example: Validate Success

```javascript
duro_validate_decision({
  decision_id: "decision_20260210_xxx",
  status: "validated",
  expected_outcome: "Faster session lookups",
  actual_outcome: "60% latency reduction, from 200ms to 80ms",
  result: "success"
})
```

### Example: Reverse Failure

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

### Status Meanings

| Status | Effect |
|--------|--------|
| `validated` | Confidence increases, surfaces with higher priority |
| `reversed` | Marked as didn't work, won't be recommended |
| `superseded` | Replaced by newer decision, archived |

---

## duro_supersede_fact

Mark an old fact as replaced by a new fact.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `old_fact_id` | string | Yes | The fact being superseded |
| `new_fact_id` | string | Yes | The fact that replaces it |
| `reason` | string | No | Explanation for the supersession |

### Example

```javascript
duro_supersede_fact({
  old_fact_id: "fact_20260101_xxx",
  new_fact_id: "fact_20260210_yyy",
  reason: "API v2 changed the rate limit from 100 to 500/min"
})
```

### Notes

- Old fact gets `valid_until` timestamp
- Old fact links to new fact via `superseded_by`
- Old fact still exists for historical reference

---

## duro_reinforce_fact

Confirm a fact is still valid, reset decay clock.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `fact_id` | string | Yes | The fact ID to reinforce |

### Example

```javascript
duro_reinforce_fact({
  fact_id: "fact_20260210_xxx"
})
```

### Effect

- Resets decay clock
- Increments reinforcement count
- Confirms fact is still accurate

---

## duro_apply_decay

Apply time-based confidence decay to unreinforced facts.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dry_run` | boolean | No | Calculate without modifying (default: true) |
| `min_importance` | number | No | Only decay facts with importance >= this |
| `include_stale_report` | boolean | No | Include list of stale facts (default: true) |

### Example

```javascript
// Preview decay effects
duro_apply_decay({
  dry_run: true
})

// Actually apply decay
duro_apply_decay({
  dry_run: false
})
```

### Notes

- Pinned facts never decay
- Run with `dry_run: true` first to preview
- Stale high-importance facts are flagged for review

---

## duro_get_validation_history

Get full validation history for a decision.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `decision_id` | string | Yes | The decision ID |

### Example

```javascript
duro_get_validation_history({
  decision_id: "decision_20260210_xxx"
})
```

### Returns

Chronological list of all validation events:
- Initial creation
- Validation attempts
- Reversals
- Re-validations

---

## duro_list_unreviewed_decisions

Find decisions that need review.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `older_than_days` | number | No | Only decisions older than N days (default: 14) |
| `include_tags` | string[] | No | Only include decisions with these tags |
| `exclude_tags` | string[] | No | Exclude decisions with these tags |
| `limit` | number | No | Max decisions to return (default: 20) |

### Example

```javascript
duro_list_unreviewed_decisions({
  older_than_days: 14,
  include_tags: ["architecture"],
  limit: 10
})
```

---

## duro_review_decision

Review a decision with full context preload.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `decision_id` | string | Yes | The decision ID to review |
| `dry_run` | boolean | No | Show context only (default: true) |
| `status` | enum | No | Validation status (required if dry_run=false) |
| `result` | enum | No | Outcome result |
| `expected_outcome` | string | No | What was expected |
| `actual_outcome` | string | No | What actually happened |
| `next_action` | string | No | One concrete next action |

### Example

```javascript
// First, review context
duro_review_decision({
  decision_id: "decision_20260210_xxx",
  dry_run: true
})

// Then validate
duro_review_decision({
  decision_id: "decision_20260210_xxx",
  dry_run: false,
  status: "validated",
  result: "success",
  actual_outcome: "Latency reduced as expected"
})
```

### Context Loaded

1. Decision core (id, decision, rationale, age, tags)
2. Validation timeline (last 3 events)
3. Linked work (episodes + incidents)
4. 48-hour recent changes scan
