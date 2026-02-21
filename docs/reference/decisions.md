# Decisions

Decisions capture choices with rationale.

## Structure

```json
{
  "id": "decision_20260210_234567_def456",
  "type": "decision",
  "created_at": "2026-02-10T12:34:56Z",
  "sensitivity": "internal",
  "tags": ["architecture", "performance"],
  "content": {
    "decision": "Use Redis for session storage instead of PostgreSQL",
    "rationale": "PostgreSQL sessions causing 200ms latency per request",
    "alternatives": [
      "Keep PostgreSQL with connection pooling",
      "Use in-memory sessions"
    ],
    "context": "Performance optimization sprint",
    "reversible": true,
    "status": "validated",
    "confidence": 0.75,
    "outcome": {
      "expected": "Faster session lookups",
      "actual": "Latency reduced by 90%",
      "result": "success"
    },
    "validation_history": [
      {
        "timestamp": "2026-02-15T10:00:00Z",
        "status": "validated",
        "result": "success"
      }
    ]
  }
}
```

## Content Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `decision` | string | Yes | The decision made |
| `rationale` | string | Yes | Why this decision |
| `alternatives` | string[] | No | Other options considered |
| `context` | string | No | Situation context |
| `reversible` | boolean | No | Can be undone (default: true) |
| `status` | enum | Auto | `pending`, `validated`, `reversed`, `superseded` |
| `confidence` | number | Auto | Current confidence (0.0-1.0) |

## Creating Decisions

### Basic Decision

```javascript
duro_store_decision({
  decision: "Use Redis for session storage",
  rationale: "PostgreSQL sessions causing 200ms latency",
  tags: ["architecture", "performance"]
})
```

### With Alternatives

```javascript
duro_store_decision({
  decision: "Use Redis for session storage",
  rationale: "PostgreSQL sessions causing 200ms latency",
  alternatives: [
    "Keep PostgreSQL with connection pooling",
    "Use in-memory sessions (loses persistence)",
    "Use JWT tokens (stateless)"
  ],
  context: "Performance optimization sprint",
  reversible: true,
  tags: ["architecture", "performance"]
})
```

## Decision Lifecycle

```
CREATE → PENDING → [use in practice] → VALIDATED/REVERSED/SUPERSEDED
```

| Status | Meaning | Confidence |
|--------|---------|------------|
| `pending` | Just created, not tested | 0.5 |
| `validated` | Confirmed working | Increases |
| `reversed` | Didn't work | Decreases |
| `superseded` | Replaced by newer | Archived |

## Validating Decisions

### Success

```javascript
duro_validate_decision({
  decision_id: "decision_xxx",
  status: "validated",
  expected_outcome: "Faster session lookups",
  actual_outcome: "Latency reduced from 200ms to 20ms",
  result: "success"
})
```

### Failure

```javascript
duro_validate_decision({
  decision_id: "decision_xxx",
  status: "reversed",
  expected_outcome: "Faster builds",
  actual_outcome: "Broke incremental compilation",
  result: "failed",
  next_action: "Revert to previous config"
})
```

### Supersede

```javascript
duro_validate_decision({
  decision_id: "decision_old",
  status: "superseded",
  notes: "Replaced by Redis Cluster decision"
})
```

## Finding Decisions

### Unreviewed Decisions

```javascript
duro_list_unreviewed_decisions({
  older_than_days: 14,
  include_tags: ["architecture"]
})
```

### Semantic Search

```javascript
duro_semantic_search({
  query: "session storage performance",
  artifact_type: "decision"
})
```

### By Tags

```javascript
duro_query_memory({
  artifact_type: "decision",
  tags: ["architecture"]
})
```

## Validation History

Get full history:

```javascript
duro_get_validation_history({
  decision_id: "decision_xxx"
})
```

Returns all validation events chronologically.

## Linking to Episodes

Decisions can link to episodes:

```javascript
duro_link_decision({
  decision_id: "decision_xxx",
  episode_id: "episode_yyy"
})
```

This tracks where decisions were applied.

## Reviewing Decisions

### With Context

```javascript
duro_review_decision({
  decision_id: "decision_xxx",
  dry_run: true  // Show context
})
```

Loads:
- Decision details
- Validation history
- Linked episodes
- Recent changes

## Confidence Changes

| Event | Confidence Change |
|-------|-------------------|
| Validated + success | +0.1 to +0.2 |
| Validated + partial | +0.05 to +0.1 |
| Reversed + failed | -0.2 to -0.3 |

## Best Practices

### Include Rationale

Good rationale helps future reference:

```javascript
// Good
rationale: "PostgreSQL sessions causing 200ms latency per request,
           verified by APM traces showing 95th percentile"

// Less useful
rationale: "Faster"
```

### Document Alternatives

Show what else was considered:

```javascript
alternatives: [
  "Keep PostgreSQL with connection pooling - still too slow",
  "Use in-memory sessions - loses persistence on restart"
]
```

### Validate When Evidence Exists

Wait for real data before validating:
- Performance metrics
- Error rates
- User feedback
- Time in production

## Next Steps

- [Validation tools reference](/reference/validation-tools)
- [Verification concepts](/concepts/verification)
- [Episodes reference](/reference/episodes)
