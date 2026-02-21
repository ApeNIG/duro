# Confidence & Decay

How Duro models knowledge certainty over time.

## Confidence Scores

Every artifact has a confidence score (0.0 to 1.0):

| Score | Meaning | When to Use |
|-------|---------|-------------|
| 0.0 - 0.3 | Low confidence | Uncertain, needs verification |
| 0.4 - 0.6 | Medium confidence | Reasonable, some evidence |
| 0.7 - 0.8 | High confidence | Strong evidence, tested |
| 0.9 - 1.0 | Very high | Multiple confirmations |

## Setting Confidence

### Facts

```javascript
// Low confidence - heard it somewhere
duro_store_fact({
  claim: "API might support pagination",
  confidence: 0.3
})

// High confidence - verified from docs
duro_store_fact({
  claim: "API rate limit is 100 requests per minute",
  confidence: 0.9,
  source_urls: ["https://api.example.com/docs"],
  evidence_type: "quote"
})
```

### Decisions

Decisions start at 0.5 and adjust based on validation:

```javascript
// Created: confidence = 0.5
duro_store_decision({
  decision: "Use Redis for sessions",
  rationale: "Faster than PostgreSQL"
})

// After validation: confidence increases
duro_validate_decision({
  decision_id: "decision_xxx",
  status: "validated",
  result: "success"
})
```

## High-Confidence Requirements

Facts with confidence >= 0.8 must have:
- `source_urls` - Where the information came from
- `evidence_type` - How the evidence supports the claim

```javascript
// This will warn or fail without sources
duro_store_fact({
  claim: "Critical production fact",
  confidence: 0.9
  // Missing: source_urls, evidence_type
})

// Correct high-confidence fact
duro_store_fact({
  claim: "Production database max connections is 500",
  confidence: 0.9,
  source_urls: ["pg_settings query result"],
  evidence_type: "quote",
  provenance: "tool_output"
})
```

## Decay Over Time

Unreinforced facts lose confidence gradually.

### Why Decay?

- Knowledge becomes stale
- Outdated facts shouldn't persist forever
- Forces periodic review of important facts

### Decay Formula

```
new_confidence = old_confidence - (days_since_reinforce * decay_rate)
```

### Preventing Decay

1. **Reinforce facts**:
```javascript
duro_reinforce_fact({ fact_id: "fact_xxx" })
```

2. **Pin important facts**:
Critical facts can be pinned to prevent decay entirely.

3. **Use facts**:
Proactive recall and search resets the decay clock.

## Applying Decay

### Preview Decay

```javascript
duro_apply_decay({
  dry_run: true,
  include_stale_report: true
})
```

### Apply Decay

```javascript
duro_apply_decay({
  dry_run: false,
  min_importance: 0.5  // Only decay less important facts
})
```

## Stale Facts

Facts that haven't been reinforced become stale:

### Check Stale Facts

```javascript
duro_maintenance_report({
  include_stale_list: true,
  top_n_stale: 10
})
```

### Review and Reinforce

1. Check if fact is still accurate
2. If yes: `duro_reinforce_fact`
3. If no: `duro_supersede_fact` with correct information

## Confidence Adjustments

### From Validation

| Validation Result | Confidence Change |
|-------------------|-------------------|
| `validated` + `success` | +0.1 to +0.2 |
| `validated` + `partial` | +0.05 to +0.1 |
| `reversed` + `failed` | -0.2 to -0.3 |

### From Episodes

| Episode Grade | Confidence Change |
|---------------|-------------------|
| A+ / A | +0.02 |
| B+ / B | +0.01 |
| C | 0 |
| D | -0.01 |
| F | -0.02 |

### Caps

Adjustments are capped:
- Max delta: +/- 0.02 per episode
- Min confidence: 0.05
- Max confidence: 0.99

## Best Practices

### Start Conservative

When uncertain, use lower confidence:
- 0.5 for reasonable assumptions
- 0.3 for uncertain claims
- Only use 0.9+ with solid evidence

### Include Sources

For important facts, always include:
- Source URL
- Evidence type
- Provenance

### Periodic Maintenance

Weekly habit:
```javascript
// Check memory health
duro_maintenance_report()

// Review stale high-importance facts
// Reinforce or supersede as needed
```

### Trust the Scores

When searching, confidence indicates reliability:
- High confidence = trust more
- Low confidence = verify before using
- Decayed confidence = might be stale

## Next Steps

- [Provenance tracking](/concepts/provenance)
- [Memory concepts](/concepts/memory)
- [Validation tools](/reference/validation-tools)
