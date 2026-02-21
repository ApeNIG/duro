# Memory

> "Every fact has a source and confidence"

Memory is the foundation of Duro. It's how your AI agent accumulates knowledge over time instead of starting from zero every conversation.

## The Problem with AI Memory

Most AI interactions are stateless. Each conversation:
- Starts fresh with no context
- Can't reference past decisions
- Repeats mistakes already made
- Has no audit trail

## Duro's Approach

Duro stores knowledge as **structured artifacts** with **provenance**:

```
┌─────────────────────────────────────────────────────┐
│ FACT                                                │
├─────────────────────────────────────────────────────┤
│ Claim: "API rate limit is 100 requests per minute" │
│ Confidence: 0.95                                    │
│ Source: API docs + incident report                  │
│ Evidence: quote                                     │
│ Created: 2026-02-10                                 │
│ Tags: [api, rate-limit]                            │
└─────────────────────────────────────────────────────┘
```

## Artifact Types

| Type | Purpose | Example |
|------|---------|---------|
| **Fact** | Objective claims with sources | "PostgreSQL max connections is 100" |
| **Decision** | Choices with rationale | "Use Redis because X" |
| **Episode** | Goal → actions → outcome | Debugging session |
| **Incident** | RCA with prevention | Production crash analysis |
| **Learning** | Quick insights | "Always check logs first" |

## Provenance

Every artifact tracks where it came from:

| Field | Description |
|-------|-------------|
| `source_urls` | Links to evidence |
| `evidence_type` | `quote`, `paraphrase`, `inference` |
| `provenance` | `web`, `local_file`, `user`, `tool_output` |
| `confidence` | 0.0 to 1.0 |

High-confidence facts (>=0.8) require source URLs and evidence type.

## Confidence & Decay

Knowledge isn't static. Duro models this with:

### Confidence Scores

| Score | Meaning |
|-------|---------|
| 0.0 - 0.3 | Low confidence, needs verification |
| 0.4 - 0.6 | Medium confidence |
| 0.7 - 0.8 | High confidence, has evidence |
| 0.9 - 1.0 | Very high, multiple confirmations |

### Decay Over Time

Unreinforced facts lose confidence gradually:
- Facts not accessed or reinforced decay
- Pinned facts never decay
- `duro_reinforce_fact` resets the decay clock

This ensures outdated knowledge doesn't persist indefinitely.

## Semantic Search

Find knowledge by meaning, not just keywords:

```javascript
duro_semantic_search({
  query: "how to handle rate limiting",
  limit: 5
})
```

Returns ranked results based on semantic similarity.

## Proactive Recall

Duro can automatically surface relevant memories:

```javascript
duro_proactive_recall({
  context: "implementing batch API caller for external service"
})
```

When the context mentions rate limits, Duro surfaces the fact that the limit is 100/min, not 1000.

## Storage

All artifacts are stored as JSON files:

```
~/.agent/memory/
├── facts/
│   └── fact_20260210_123456_abc123.json
├── decisions/
│   └── decision_20260210_234567_def456.json
├── episodes/
│   └── episode_20260210_345678_ghi789.json
└── incidents/
    └── incident_20260210_456789_jkl012.json
```

Benefits:
- Human-readable
- Git-friendly
- No cloud required
- Easy to backup

## Next Steps

- [Verification: Track outcomes](/concepts/verification)
- [Store your first fact](/guide/storing-knowledge)
- [Memory tools reference](/reference/memory-tools)
