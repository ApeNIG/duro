# Memory Tools

Tools for storing knowledge in Duro.

## duro_store_fact

Store a fact with source attribution.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `claim` | string | Yes | The factual claim being recorded |
| `confidence` | number | No | Confidence score 0-1 (default: 0.5) |
| `source_urls` | string[] | No | URLs supporting this fact |
| `evidence_type` | enum | No | `quote`, `paraphrase`, `inference`, `none` |
| `provenance` | enum | No | `web`, `local_file`, `user`, `tool_output`, `unknown` |
| `snippet` | string | No | Relevant excerpt or context |
| `tags` | string[] | No | Searchable tags |
| `sensitivity` | enum | No | `public`, `internal`, `sensitive` |

### Example

```javascript
duro_store_fact({
  claim: "PostgreSQL max connections default is 100",
  confidence: 0.9,
  source_urls: ["https://postgresql.org/docs/current/runtime-config-connection.html"],
  evidence_type: "quote",
  provenance: "web",
  tags: ["database", "postgresql", "config"]
})
```

### Notes

- High confidence (>=0.8) requires `source_urls` and `evidence_type`
- Facts decay over time unless reinforced
- Use `duro_reinforce_fact` to reset decay clock

---

## duro_store_decision

Record a decision with rationale.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `decision` | string | Yes | The decision made |
| `rationale` | string | Yes | Why this decision was made |
| `alternatives` | string[] | No | Other options considered |
| `context` | string | No | Situation context |
| `reversible` | boolean | No | Whether decision can be undone (default: true) |
| `tags` | string[] | No | Searchable tags |
| `sensitivity` | enum | No | `public`, `internal`, `sensitive` |

### Example

```javascript
duro_store_decision({
  decision: "Use Redis for session storage instead of PostgreSQL",
  rationale: "PostgreSQL sessions causing 200ms latency on every request",
  alternatives: [
    "Keep PostgreSQL with connection pooling",
    "Use in-memory sessions (loses persistence)"
  ],
  context: "Performance optimization sprint",
  tags: ["architecture", "performance", "redis"]
})
```

### Decision Lifecycle

1. **Created** → status: `pending`, confidence: 0.5
2. **Validated** → status: `validated`, confidence increases
3. **Reversed** → status: `reversed`, alternative chosen
4. **Superseded** → status: `superseded`, replaced by new decision

---

## duro_save_learning

Save a quick learning or insight.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `learning` | string | Yes | The learning or insight |
| `category` | string | No | Category (default: "General") |

### Example

```javascript
duro_save_learning({
  learning: "Always check logs before restarting services",
  category: "Debugging"
})
```

### Notes

- Lighter weight than `store_fact` or `store_decision`
- Good for quick session notes
- Stored in daily memory log

---

## duro_save_memory

Save content to today's memory log.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | Yes | The content to save |
| `section` | string | No | Section header (default: "Session Log") |

### Example

```javascript
duro_save_memory({
  content: "Completed migration to Redis. Latency now 20ms.",
  section: "Completed Tasks"
})
```

---

## duro_store_incident

Store an incident RCA (Root Cause Analysis).

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symptom` | string | Yes | What was observed failing |
| `actual_cause` | string | Yes | The real root cause |
| `fix` | string | Yes | What was done to fix it |
| `prevention` | string | No | How to prevent recurrence |
| `repro_steps` | string[] | No | Steps to reproduce |
| `first_bad_boundary` | string | No | First place output becomes wrong |
| `severity` | enum | No | `low`, `medium`, `high`, `critical` |
| `tags` | string[] | No | Searchable tags |

### Example

```javascript
duro_store_incident({
  symptom: "API returning 500 errors after deploy",
  actual_cause: "Config change removed required env var",
  fix: "Added missing AUTH_SECRET env var",
  prevention: "Add startup check for required env vars",
  repro_steps: [
    "Deploy latest main",
    "Call /api/auth endpoint"
  ],
  severity: "high",
  tags: ["config", "deploy", "auth"]
})
```

### Debug Gate

The debug gate enforces quality RCAs:
- **Pass 1**: At least 2 repro steps
- **Pass 2**: First bad boundary identified
- **Pass 3**: 48-hour change scan completed

---

## duro_store_change

Store a recent change to the change ledger.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scope` | string | Yes | What was changed (repo/service/module) |
| `change` | string | Yes | One sentence describing the change |
| `why` | string | No | Reason for the change |
| `risk_tags` | string[] | No | Risk categories touched |
| `quick_checks` | string[] | No | Fast ways to verify it works |
| `commit_hash` | string | No | Git commit hash if applicable |

### Example

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

### Notes

- Powers the 48-hour rule for debugging
- Query with `duro_query_recent_changes`
- Risk tags help correlate changes to incidents
