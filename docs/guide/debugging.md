# Debugging with Duro

Use the 48-hour rule and incident tracking for effective debugging.

## The 48-Hour Rule

When something breaks, the cause is usually in the last 48 hours of changes.

### Step 1: Query Recent Changes

```javascript
duro_query_recent_changes({
  hours: 48
})
```

### Step 2: Filter by Risk Tags

If you suspect a specific area:

```javascript
duro_query_recent_changes({
  hours: 48,
  risk_tags: ["config", "deploy", "auth"]
})
```

### Risk Tag Categories

| Tag | What It Covers |
|-----|---------------|
| `config` | Configuration changes |
| `db` | Database schema/data |
| `paths` | File paths, directories |
| `sync` | Synchronization logic |
| `deploy` | Deployment changes |
| `auth` | Authentication/authorization |
| `caching` | Cache configuration |
| `env` | Environment variables |
| `permissions` | Access controls |
| `network` | Network configuration |
| `state` | State management |
| `api` | API changes |
| `schema` | Data schema changes |

## Debug Gate

The debug gate enforces quality root cause analysis.

### Start a Debug Session

```javascript
duro_debug_gate_start({
  symptom: "API returning 500 errors after deploy",
  tags: ["api", "deploy"]
})
```

### Check What's Missing

```javascript
duro_debug_gate_status({
  incident_id: "incident_xxx"
})
```

### Gate Requirements

The debug gate requires three passes:

| Pass | Requirement |
|------|-------------|
| **1. Repro** | At least 2 reproduction steps |
| **2. Boundary** | First bad boundary identified |
| **3. Causality** | 48-hour change scan completed |

Plus: Prevention must be actionable (not "be more careful").

## Store the Incident

Once you've debugged the issue:

```javascript
duro_store_incident({
  symptom: "API returning 500 errors after deploy",
  actual_cause: "Config change removed required AUTH_SECRET env var",
  fix: "Added missing AUTH_SECRET to deployment config",
  prevention: "Add startup check that validates required env vars exist",
  repro_steps: [
    "Deploy latest main branch",
    "Call /api/auth endpoint",
    "Observe 500 error"
  ],
  first_bad_boundary: "Service startup - env var validation",
  severity: "high",
  tags: ["config", "deploy", "auth"]
})
```

## Log Changes

When you make structural changes, log them:

```javascript
duro_store_change({
  scope: "auth-service",
  change: "Added startup validation for required env vars",
  why: "Prevent missing env var incidents",
  risk_tags: ["config", "auth"],
  quick_checks: [
    "Service starts with all vars",
    "Service fails fast with missing vars"
  ]
})
```

This powers future 48-hour queries.

## Debugging Workflow

```
1. Something broke
         ↓
2. Query 48-hour changes
         ↓
3. Start debug gate session
         ↓
4. Find reproduction steps (Pass 1)
         ↓
5. Identify first bad boundary (Pass 2)
         ↓
6. Link to recent changes (Pass 3)
         ↓
7. Fix the issue
         ↓
8. Store incident with actionable prevention
         ↓
9. Log the fix as a change
```

## Check Past Incidents

Before debugging, check if you've seen this before:

```javascript
duro_semantic_search({
  query: "API 500 errors after deployment",
  artifact_type: "incident"
})
```

Past incidents often reveal patterns.

## Prevention Best Practices

### Good Prevention

- "Add startup check that validates AUTH_SECRET exists"
- "Add smoke test for /api/auth endpoint in deploy pipeline"
- "Assert JWT_SECRET is non-empty before accepting requests"

### Bad Prevention

- "Be more careful when deploying"
- "Remember to check env vars"
- "Double-check configuration"

Prevention must be automated and enforceable.

## Next Steps

- [Validation tools reference](/reference/validation-tools)
- [Debug tools reference](/reference/debug-tools)
- [48-hour rule concept](/concepts/48-hour-rule)
