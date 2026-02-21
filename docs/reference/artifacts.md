# Artifacts

All Duro knowledge is stored as artifacts.

## Artifact Types

| Type | Purpose | Example |
|------|---------|---------|
| `fact` | Objective claims with sources | "API limit is 100/min" |
| `decision` | Choices with rationale | "Use Redis because X" |
| `episode` | Goal → actions → outcome | Debugging session |
| `incident` | RCA with prevention | Production crash analysis |
| `recent_change` | Change ledger entry | "Updated config" |

## Common Envelope

All artifacts share a common structure:

```json
{
  "id": "fact_20260210_123456_abc123",
  "type": "fact",
  "created_at": "2026-02-10T12:34:56Z",
  "updated_at": "2026-02-10T12:34:56Z",
  "sensitivity": "internal",
  "tags": ["api", "rate-limit"],
  "workflow": "manual",
  "content": {
    // Type-specific fields
  }
}
```

## Common Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `type` | enum | Artifact type |
| `created_at` | ISO date | Creation timestamp |
| `updated_at` | ISO date | Last modification |
| `sensitivity` | enum | `public`, `internal`, `sensitive` |
| `tags` | string[] | Searchable tags |
| `workflow` | string | Source workflow name |

## Sensitivity Levels

| Level | Meaning |
|-------|---------|
| `public` | Can be shared freely |
| `internal` | Internal use only |
| `sensitive` | Requires extra protection |

Sensitive artifacts require `force: true` to delete.

## ID Format

```
{type}_{date}_{time}_{random}

Examples:
fact_20260210_123456_abc123
decision_20260210_234567_def456
episode_20260210_345678_ghi789
```

## Storage Location

```
~/.agent/memory/
├── facts/
│   └── fact_20260210_123456_abc123.json
├── decisions/
│   └── decision_20260210_234567_def456.json
├── episodes/
│   └── episode_20260210_345678_ghi789.json
├── incidents/
│   └── incident_20260210_456789_jkl012.json
└── changes/
    └── change_20260210_567890_mno345.json
```

## Querying Artifacts

### List Recent

```javascript
duro_list_artifacts({
  artifact_type: "decision",
  limit: 10
})
```

### Get by ID

```javascript
duro_get_artifact({
  artifact_id: "fact_20260210_123456_abc123"
})
```

### Search

```javascript
duro_semantic_search({
  query: "rate limiting",
  artifact_type: "fact"
})
```

## Deleting Artifacts

```javascript
duro_delete_artifact({
  artifact_id: "fact_xxx",
  reason: "Outdated information"
})
```

For sensitive artifacts:

```javascript
duro_delete_artifact({
  artifact_id: "fact_xxx",
  reason: "Cleanup",
  force: true  // Required for sensitive
})
```

## Next Steps

- [Facts reference](/reference/facts)
- [Decisions reference](/reference/decisions)
- [Episodes reference](/reference/episodes)
