# Searching Knowledge

Find relevant knowledge when you need it.

## Semantic Search

Search by meaning, not just keywords:

```javascript
duro_semantic_search({
  query: "how to handle rate limiting",
  limit: 5
})
```

Returns ranked results based on semantic similarity.

### With Filters

```javascript
duro_semantic_search({
  query: "authentication issues",
  artifact_type: "incident",
  tags: ["auth"],
  limit: 10
})
```

## Query by Attributes

Search by specific attributes:

```javascript
duro_query_memory({
  artifact_type: "decision",
  tags: ["architecture"],
  since: "2026-01-01",
  limit: 20
})
```

### Filter Options

| Parameter | Description |
|-----------|-------------|
| `artifact_type` | `fact`, `decision`, `episode`, `incident` |
| `tags` | Match any of these tags |
| `since` | ISO date to filter from |
| `sensitivity` | `public`, `internal`, `sensitive` |
| `workflow` | Source workflow name |

## Proactive Recall

Let Duro automatically surface relevant memories:

```javascript
duro_proactive_recall({
  context: "implementing batch API caller for external service",
  limit: 10
})
```

When context mentions rate limits, Duro surfaces facts like "API limit is 100/min, not 1000."

### How It Works

1. **Hot path classifier** determines if recall is needed
2. **Hybrid search** combines semantic and keyword matching
3. **Results ranked** by relevance and confidence
4. **High-importance items** surface first

## Get Specific Artifact

Retrieve full details by ID:

```javascript
duro_get_artifact({
  artifact_id: "decision_20260210_123456_abc123"
})
```

## List Recent

See recent artifacts:

```javascript
duro_list_artifacts({
  artifact_type: "decision",
  limit: 10
})
```

## 48-Hour Rule

When debugging, check recent changes:

```javascript
duro_query_recent_changes({
  hours: 48,
  risk_tags: ["config", "deploy"]
})
```

This surfaces changes that might have caused issues.

## Search Patterns

### Find Related Decisions

```javascript
// When implementing a feature
duro_semantic_search({
  query: "session storage performance architecture",
  artifact_type: "decision"
})
```

### Find Past Incidents

```javascript
// When seeing similar symptoms
duro_semantic_search({
  query: "API 500 errors after deployment",
  artifact_type: "incident"
})
```

### Find Facts About a Topic

```javascript
// When you need to remember specifics
duro_semantic_search({
  query: "PostgreSQL connection limits configuration",
  artifact_type: "fact"
})
```

## Tips

### Use Natural Language

```javascript
// Good - natural question
duro_semantic_search({
  query: "what's the rate limit for the external API?"
})

// Also works - keywords
duro_semantic_search({
  query: "rate limit external API"
})
```

### Combine Methods

Start broad, then narrow:

```javascript
// 1. Broad semantic search
duro_semantic_search({ query: "authentication" })

// 2. Narrow by type and tags
duro_query_memory({
  artifact_type: "incident",
  tags: ["auth", "jwt"]
})
```

### Check Confidence

Results include confidence scores. Higher confidence = more reliable:

```
fact_abc123 (confidence: 0.9) - "API limit is 100/min"
fact_def456 (confidence: 0.5) - "API might have burst mode"
```

## Next Steps

- [Validate decisions](/concepts/verification)
- [Debug with 48-hour rule](/guide/debugging)
- [Search tools reference](/reference/search-tools)
