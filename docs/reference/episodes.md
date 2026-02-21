# Episodes

Episodes track goal-level work with outcomes.

## Structure

```json
{
  "id": "episode_20260210_345678_ghi789",
  "type": "episode",
  "created_at": "2026-02-10T12:00:00Z",
  "closed_at": "2026-02-10T12:45:00Z",
  "sensitivity": "internal",
  "tags": ["debugging", "auth"],
  "content": {
    "goal": "Fix authentication bug in login flow",
    "plan": [
      "Investigate error logs",
      "Reproduce the issue",
      "Find root cause",
      "Implement fix"
    ],
    "context": {
      "domain": "authentication",
      "constraints": ["No breaking changes"],
      "environment": {"service": "auth-api"}
    },
    "actions": [
      {
        "timestamp": "2026-02-10T12:10:00Z",
        "summary": "Found JWT validation failing on malformed tokens",
        "tool": "grep"
      },
      {
        "timestamp": "2026-02-10T12:30:00Z",
        "summary": "Fixed validation and added test",
        "tool": "edit"
      }
    ],
    "result": "success",
    "result_summary": "Fixed JWT validation, added test coverage",
    "duration_mins": 45,
    "links": {
      "decisions_used": ["decision_abc"],
      "facts_created": ["fact_xyz"],
      "decisions_created": []
    }
  }
}
```

## Content Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `goal` | string | Yes | What to achieve |
| `plan` | string[] | No | Planned steps |
| `context` | object | No | Domain, constraints, environment |
| `actions` | array | Auto | What actually happened |
| `result` | enum | On close | `success`, `partial`, `failed` |
| `result_summary` | string | On close | Brief outcome |
| `links` | object | No | Related artifacts |

## Episode Lifecycle

```
CREATE → OPEN → [work] → CLOSE → EVALUATE → APPLY
```

## Creating Episodes

```javascript
duro_create_episode({
  goal: "Fix authentication bug in login flow",
  plan: [
    "Investigate error logs",
    "Reproduce the issue",
    "Find root cause",
    "Implement fix"
  ],
  context: {
    domain: "authentication",
    constraints: ["No breaking changes"]
  },
  tags: ["debugging", "auth"]
})
```

## Tracking Actions

Log what happens:

```javascript
duro_add_episode_action({
  episode_id: "episode_xxx",
  summary: "Found JWT validation failing on malformed tokens",
  tool: "grep"
})
```

### Action Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `summary` | string | Yes | What the action did |
| `tool` | string | No | Tool used |
| `run_id` | string | No | Orchestration run ID |

## Closing Episodes

```javascript
duro_close_episode({
  episode_id: "episode_xxx",
  result: "success",
  result_summary: "Fixed JWT validation, added test coverage",
  links: {
    decisions_used: ["decision_abc"],
    facts_created: ["fact_xyz"]
  }
})
```

### Result Values

| Result | Meaning |
|--------|---------|
| `success` | Goal fully achieved |
| `partial` | Partially achieved |
| `failed` | Goal not achieved |

## Evaluating Episodes

Grade the completed work:

```javascript
duro_evaluate_episode({
  episode_id: "episode_xxx",
  grade: "A",
  rubric: {
    outcome_quality: { score: 5, notes: "Bug fully fixed" },
    correctness_risk: { score: 1, notes: "Low risk change" },
    reusability: { score: 4, notes: "Pattern applies to JWT issues" },
    reproducibility: { score: 5, notes: "Well documented" },
    cost: {
      tokens_bucket: "M",
      tools_used: 8,
      duration_mins: 45
    }
  },
  next_change: "Add JWT validation to integration tests"
})
```

### Rubric Dimensions

| Dimension | Scale | Measures |
|-----------|-------|----------|
| `outcome_quality` | 0-5 | Goal achievement |
| `correctness_risk` | 0-5 | Risk level (lower is better) |
| `reusability` | 0-5 | Pattern applicability |
| `reproducibility` | 0-5 | Documentation quality |
| `cost` | object | Resource usage |

### Grades

| Grade | Meaning |
|-------|---------|
| A+ / A | Excellent |
| B+ / B | Good |
| C | Acceptable |
| D | Below expectations |
| F | Failed |

## Applying Evaluations

Update memory based on outcomes:

```javascript
duro_apply_evaluation({
  evaluation_id: "evaluation_xxx"
})
```

This:
- Reinforces facts used in success
- Adjusts skill confidence
- Updates domain reputation

## Finding Episodes

### List Recent

```javascript
duro_list_episodes({
  status: "closed",
  limit: 10
})
```

### Get Details

```javascript
duro_get_episode({
  episode_id: "episode_xxx"
})
```

## Episode Suggestions

Check if work should be an episode:

```javascript
duro_suggest_episode({
  goal_summary: "Investigating performance issue",
  tools_used: true,
  duration_mins: 15,
  artifacts_produced: true
})
```

### Episode Triggers

Create episodes for:
- Duration > 3 minutes
- Tools are used
- Artifacts produced
- Complex multi-step work

## Links

Episodes link to other artifacts:

```javascript
links: {
  decisions_used: ["decision_abc"],     // Decisions applied
  facts_created: ["fact_xyz"],          // Facts discovered
  decisions_created: ["decision_def"],  // Decisions made
  skills_used: ["debugging", "jwt"]     // Skills exercised
}
```

## Best Practices

### Create for Significant Work

Not every task needs an episode. Use for:
- Debugging sessions
- Feature implementations
- Architecture decisions
- Complex investigations

### Track Actions

Log key milestones:
```javascript
duro_add_episode_action({
  episode_id: "episode_xxx",
  summary: "Identified root cause: JWT expiry"
})
```

### Close with Results

Always close with outcome:
```javascript
duro_close_episode({
  episode_id: "episode_xxx",
  result: "success",
  result_summary: "Fixed JWT validation"
})
```

### Evaluate Honestly

Accurate grades improve the system.

## Next Steps

- [Expertise concepts](/concepts/expertise)
- [Validation tools](/reference/validation-tools)
- [Memory tools](/reference/memory-tools)
