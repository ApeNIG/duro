# Storing Knowledge

Learn how to store facts, decisions, and other artifacts in Duro.

## Facts

Facts are objective claims with provenance. Use them for things you learn that should be remembered.

### Basic Fact

```javascript
duro_store_fact({
  claim: "PostgreSQL default max connections is 100",
  confidence: 0.5,
  tags: ["database", "postgresql"]
})
```

### High-Confidence Fact

For high confidence (>=0.8), you must provide sources:

```javascript
duro_store_fact({
  claim: "Stripe API rate limit is 100 requests per second",
  confidence: 0.9,
  source_urls: ["https://stripe.com/docs/rate-limits"],
  evidence_type: "quote",
  provenance: "web",
  tags: ["api", "rate-limit", "stripe"]
})
```

### Evidence Types

| Type | Use When |
|------|----------|
| `quote` | Direct quote from source |
| `paraphrase` | Reworded from source |
| `inference` | Derived from evidence |
| `none` | No direct evidence |

## Decisions

Decisions capture choices with rationale. They can be validated later.

### Basic Decision

```javascript
duro_store_decision({
  decision: "Use Redis for session storage",
  rationale: "PostgreSQL sessions causing 200ms latency per request",
  tags: ["architecture", "performance"]
})
```

### Decision with Alternatives

```javascript
duro_store_decision({
  decision: "Use Redis for session storage",
  rationale: "PostgreSQL sessions causing 200ms latency per request",
  alternatives: [
    "Keep PostgreSQL with connection pooling",
    "Use in-memory sessions (loses persistence)",
    "Use JWT tokens (stateless)"
  ],
  context: "Performance optimization sprint",
  reversible: true,
  tags: ["architecture", "performance", "redis"]
})
```

## Quick Learnings

For fast, lightweight notes:

```javascript
duro_save_learning({
  learning: "Always check logs before restarting services",
  category: "Debugging"
})
```

## Session Notes

Save to today's memory log:

```javascript
duro_save_memory({
  content: "Completed Redis migration. Latency now 20ms.",
  section: "Completed Tasks"
})
```

## Incidents

Record root cause analyses:

```javascript
duro_store_incident({
  symptom: "API returning 500 errors after deploy",
  actual_cause: "Config change removed required AUTH_SECRET env var",
  fix: "Added missing AUTH_SECRET to deployment config",
  prevention: "Add startup validation for required env vars",
  repro_steps: [
    "Deploy latest main branch",
    "Call any authenticated endpoint"
  ],
  severity: "high",
  tags: ["config", "deploy", "auth"]
})
```

## Changes

Track structural changes for the 48-hour rule:

```javascript
duro_store_change({
  scope: "auth-service",
  change: "Updated JWT expiry from 24h to 1h",
  why: "Security audit requirement",
  risk_tags: ["auth", "config"],
  quick_checks: [
    "Login still works",
    "Token refresh works"
  ]
})
```

## Best Practices

### Tag Consistently

Use consistent tags across artifacts:

```
api, database, auth, config, deploy
performance, security, testing, ci-cd
rate-limit, caching, logging, monitoring
```

### Set Appropriate Confidence

| Score | When to Use |
|-------|-------------|
| 0.3-0.4 | Uncertain, needs verification |
| 0.5-0.6 | Reasonable confidence |
| 0.7-0.8 | Strong evidence |
| 0.9+ | Multiple confirmations, direct sources |

### Include Context

Future recall works better with context:

```javascript
// Good - includes context
duro_store_decision({
  decision: "Use Redis for session storage",
  rationale: "PostgreSQL sessions causing 200ms latency",
  context: "Performance optimization for checkout flow"
})

// Less good - missing context
duro_store_decision({
  decision: "Use Redis",
  rationale: "Faster"
})
```

## Next Steps

- [Search your knowledge](/guide/searching)
- [Validate decisions](/concepts/verification)
- [Memory tools reference](/reference/memory-tools)
