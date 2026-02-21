# Facts

Facts are objective claims with provenance.

## Structure

```json
{
  "id": "fact_20260210_123456_abc123",
  "type": "fact",
  "created_at": "2026-02-10T12:34:56Z",
  "sensitivity": "internal",
  "tags": ["api", "rate-limit"],
  "content": {
    "claim": "API rate limit is 100 requests per minute",
    "confidence": 0.9,
    "source_urls": ["https://api.example.com/docs"],
    "evidence_type": "quote",
    "provenance": "web",
    "snippet": "Rate limiting: 100 requests per 60 seconds",
    "reinforced_at": "2026-02-15T10:00:00Z",
    "reinforcement_count": 2
  }
}
```

## Content Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claim` | string | Yes | The factual claim |
| `confidence` | number | No | 0.0 to 1.0 (default: 0.5) |
| `source_urls` | string[] | No* | URLs supporting the fact |
| `evidence_type` | enum | No* | `quote`, `paraphrase`, `inference`, `none` |
| `provenance` | enum | No | `web`, `local_file`, `user`, `tool_output`, `unknown` |
| `snippet` | string | No | Relevant excerpt |

*Required for confidence >= 0.8

## Creating Facts

### Basic Fact

```javascript
duro_store_fact({
  claim: "PostgreSQL default max connections is 100",
  tags: ["database", "postgresql"]
})
```

### High-Confidence Fact

```javascript
duro_store_fact({
  claim: "API rate limit is 100 requests per minute",
  confidence: 0.9,
  source_urls: ["https://api.example.com/docs"],
  evidence_type: "quote",
  provenance: "web",
  snippet: "Rate limiting: 100 requests per 60 seconds",
  tags: ["api", "rate-limit"]
})
```

## Confidence Levels

| Score | Meaning |
|-------|---------|
| 0.0 - 0.3 | Low confidence, needs verification |
| 0.4 - 0.6 | Medium confidence |
| 0.7 - 0.8 | High confidence, has evidence |
| 0.9 - 1.0 | Very high, multiple confirmations |

## Evidence Types

| Type | Use When |
|------|----------|
| `quote` | Direct quote from source |
| `paraphrase` | Reworded from source |
| `inference` | Derived from evidence |
| `none` | No direct evidence |

## Provenance Types

| Type | Use When |
|------|----------|
| `web` | From websites, APIs, docs |
| `local_file` | From local files |
| `user` | User provided |
| `tool_output` | From tool execution |
| `unknown` | Source unclear |

## Reinforcing Facts

Reset the decay clock:

```javascript
duro_reinforce_fact({
  fact_id: "fact_xxx"
})
```

Effects:
- Resets `reinforced_at`
- Increments `reinforcement_count`
- Confirms fact is still accurate

## Superseding Facts

When information changes:

```javascript
duro_supersede_fact({
  old_fact_id: "fact_old",
  new_fact_id: "fact_new",
  reason: "API v2 changed the limit"
})
```

The old fact:
- Gets `valid_until` timestamp
- Links to new fact via `superseded_by`
- Still exists for historical reference

## Confidence Decay

Unreinforced facts lose confidence over time:
- Decay is gradual
- Pinned facts don't decay
- Use `duro_apply_decay` to apply

## Searching Facts

```javascript
// Semantic search
duro_semantic_search({
  query: "rate limiting",
  artifact_type: "fact"
})

// By tags
duro_query_memory({
  artifact_type: "fact",
  tags: ["api"]
})
```

## Best Practices

### Include Sources

For important facts, always include:
- `source_urls` - Where from
- `evidence_type` - How it supports the claim
- `snippet` - Relevant excerpt

### Use Appropriate Confidence

- 0.5 for reasonable assumptions
- 0.3 for uncertain claims
- 0.9+ only with solid evidence

### Tag Consistently

Use consistent tags across facts:
```
api, database, auth, config, performance
```

## Next Steps

- [Memory tools reference](/reference/memory-tools)
- [Confidence & Decay](/concepts/confidence)
- [Provenance](/concepts/provenance)
