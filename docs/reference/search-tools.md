# Search Tools

Tools for finding knowledge in Duro.

## duro_semantic_search

Search by meaning using hybrid vector + keyword matching.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Natural language search query |
| `artifact_type` | enum | No | Filter by type |
| `tags` | string[] | No | Filter by tags (any match) |
| `limit` | number | No | Max results (default: 20) |
| `explain` | boolean | No | Include score breakdown |

### Example

```javascript
duro_semantic_search({
  query: "how to handle API rate limiting",
  artifact_type: "fact",
  tags: ["api"],
  limit: 5,
  explain: true
})
```

### Notes

- Falls back to keyword-only if embeddings unavailable
- Results ranked by semantic similarity + recency
- Use `explain: true` for debugging relevance

---

## duro_query_memory

Search by attributes (tags, type, date).

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `artifact_type` | enum | No | `fact`, `decision`, `episode`, `incident` |
| `tags` | string[] | No | Filter by tags (any match) |
| `since` | string | No | ISO date to filter from |
| `sensitivity` | enum | No | `public`, `internal`, `sensitive` |
| `workflow` | string | No | Filter by source workflow |
| `search_text` | string | No | Search in titles/content |
| `limit` | number | No | Max results (default: 50) |

### Example

```javascript
duro_query_memory({
  artifact_type: "decision",
  tags: ["architecture", "performance"],
  since: "2026-01-01",
  limit: 20
})
```

---

## duro_proactive_recall

Automatically surface relevant memories for current context.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `context` | string | Yes | Current task or conversation context |
| `limit` | number | No | Max memories to return (default: 10) |
| `include_types` | string[] | No | Filter to specific artifact types |
| `force` | boolean | No | Always search even if classifier says no |

### Example

```javascript
duro_proactive_recall({
  context: "implementing batch API caller for external service",
  limit: 10,
  include_types: ["fact", "decision"]
})
```

### How It Works

1. Hot path classifier determines if recall is needed
2. If yes, runs hybrid search on context
3. Returns ranked results by relevance
4. Surfaces facts like "API limit is 100/min" when context mentions rate limits

---

## duro_get_artifact

Retrieve full artifact by ID.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `artifact_id` | string | Yes | The artifact ID to retrieve |

### Example

```javascript
duro_get_artifact({
  artifact_id: "decision_20260210_123456_abc123"
})
```

### Returns

Complete JSON envelope with all artifact fields.

---

## duro_list_artifacts

List recent artifacts.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `artifact_type` | enum | No | Filter by type |
| `limit` | number | No | Max results (default: 50) |

### Example

```javascript
duro_list_artifacts({
  artifact_type: "decision",
  limit: 10
})
```

---

## duro_get_related

Find artifacts related to a given artifact.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `artifact_id` | string | Yes | The artifact to find relations for |
| `relation_type` | string | No | Filter by relation type |
| `direction` | enum | No | `outgoing`, `incoming`, `both` (default) |

### Example

```javascript
duro_get_related({
  artifact_id: "decision_20260210_xxx",
  direction: "both"
})
```

### Relation Types

- `supersedes` - This artifact replaces another
- `references` - This artifact mentions another

---

## Search Patterns

### Find All Decisions About a Topic

```javascript
duro_semantic_search({
  query: "session storage architecture",
  artifact_type: "decision"
})
```

### Find Recent High-Confidence Facts

```javascript
duro_query_memory({
  artifact_type: "fact",
  since: "2026-02-01"
})
// Then filter by confidence in results
```

### Find Related Incidents

```javascript
duro_semantic_search({
  query: "deployment failures",
  artifact_type: "incident",
  limit: 5
})
```
