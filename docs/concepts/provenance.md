# Provenance

> "Every fact has a source"

Provenance is how Duro tracks where knowledge comes from.

## Why Provenance Matters

Without provenance:
- Can't verify claims
- Can't trace errors
- Can't update when sources change

With provenance:
- Full audit trail
- Verifiable knowledge
- Update when sources change

## Provenance Fields

### source_urls

Where the information came from:

```javascript
duro_store_fact({
  claim: "API rate limit is 100 requests per minute",
  source_urls: [
    "https://api.example.com/docs/rate-limits",
    "https://status.example.com/incident/123"
  ]
})
```

Multiple URLs for corroborated facts.

### evidence_type

How the evidence supports the claim:

| Type | Meaning | Example |
|------|---------|---------|
| `quote` | Direct quote from source | "Max connections: 100" |
| `paraphrase` | Reworded from source | Docs say ~100 connections |
| `inference` | Derived from evidence | Based on error patterns |
| `none` | No direct evidence | Assumption |

```javascript
duro_store_fact({
  claim: "Rate limit is 100/min",
  evidence_type: "quote",
  snippet: "Rate limiting: 100 requests per 60 seconds"
})
```

### provenance

Where the knowledge originated:

| Source | When to Use |
|--------|-------------|
| `web` | From websites, APIs, docs |
| `local_file` | From local files |
| `user` | User provided |
| `tool_output` | From tool execution |
| `unknown` | Source unclear |

```javascript
duro_store_fact({
  claim: "Current DB size is 50GB",
  provenance: "tool_output",
  snippet: "pg_database_size: 53687091200"
})
```

### snippet

Relevant excerpt or context:

```javascript
duro_store_fact({
  claim: "JWT tokens expire after 1 hour",
  source_urls: ["https://auth.example.com/docs/tokens"],
  evidence_type: "quote",
  snippet: "Access tokens have a TTL of 3600 seconds (1 hour)"
})
```

## Full Example

High-quality fact with complete provenance:

```javascript
duro_store_fact({
  claim: "External API rate limit is 100 requests per minute per API key",
  confidence: 0.95,
  source_urls: [
    "https://api.example.com/docs/rate-limiting",
    "https://api.example.com/changelog#2026-01-15"
  ],
  evidence_type: "quote",
  provenance: "web",
  snippet: "Each API key is limited to 100 requests per rolling 60-second window. Exceeding this limit returns HTTP 429.",
  tags: ["api", "rate-limit", "external"]
})
```

## Provenance for Decisions

Decisions track rationale:

```javascript
duro_store_decision({
  decision: "Use Redis for session storage",
  rationale: "PostgreSQL sessions causing 200ms latency, verified by APM traces",
  alternatives: [
    "Keep PostgreSQL with connection pooling",
    "Use in-memory sessions"
  ],
  context: "Performance optimization sprint, week of 2026-02-10"
})
```

## Provenance Chain

When facts build on other facts:

```javascript
// Base fact
duro_store_fact({
  claim: "API limit is 100/min",
  source_urls: ["https://api.example.com/docs"],
  evidence_type: "quote"
})

// Derived decision
duro_store_decision({
  decision: "Implement request queuing",
  rationale: "API limit is 100/min (fact_xxx), we need 200/min",
  // Links to the source fact
})
```

## Supersession

When information changes, link old to new:

```javascript
// New fact with updated info
duro_store_fact({
  claim: "API rate limit increased to 500/min",
  source_urls: ["https://api.example.com/changelog#v2"]
})

// Supersede the old fact
duro_supersede_fact({
  old_fact_id: "fact_old_limit",
  new_fact_id: "fact_new_limit",
  reason: "API v2 increased rate limit"
})
```

The old fact:
- Gets `valid_until` timestamp
- Links to new fact via `superseded_by`
- Still exists for historical reference

## Searching with Provenance

Find facts by provenance:

```javascript
// Find all web-sourced facts
duro_query_memory({
  artifact_type: "fact",
  workflow: "web"  // or provenance filter if available
})
```

## Best Practices

### Always Include Sources for Important Facts

```javascript
// Don't do this for important facts
duro_store_fact({
  claim: "Production DB password in 1Password",
  confidence: 1.0
  // No source!
})

// Do this
duro_store_fact({
  claim: "Production DB password in 1Password vault",
  confidence: 1.0,
  provenance: "user",
  snippet: "User confirmed on 2026-02-10"
})
```

### Use Appropriate Evidence Types

- `quote`: When you have exact text
- `paraphrase`: When you're summarizing
- `inference`: When you're deriving
- `none`: Be honest when there's no evidence

### Include Snippets

Snippets help verify claims later:

```javascript
// Without snippet - hard to verify
duro_store_fact({
  claim: "Max file size is 10MB"
})

// With snippet - easy to verify
duro_store_fact({
  claim: "Max file size is 10MB",
  snippet: "config.maxFileSize = 10 * 1024 * 1024"
})
```

### Update When Sources Change

When source information changes:
1. Store new fact with new source
2. Supersede old fact
3. Maintain the provenance chain

## Next Steps

- [Confidence & Decay](/concepts/confidence)
- [Memory concepts](/concepts/memory)
- [Memory tools reference](/reference/memory-tools)
