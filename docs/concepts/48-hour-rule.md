# The 48-Hour Rule

> "When something breaks, the cause is usually recent"

The 48-hour rule is a debugging principle: most production issues are caused by changes made in the last 48 hours.

## The Principle

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   SOMETHING BROKE                                       │
│           ↓                                             │
│   What changed in the last 48 hours?                    │
│           ↓                                             │
│   [Usually finds the cause]                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Why 48 Hours?

- **Most deploys are recent**: Production changes happen daily
- **Memory is fresh**: People remember what they changed
- **Scope is manageable**: 48 hours is searchable
- **Correlation is high**: Most issues are caused by recent changes

## Using the 48-Hour Rule

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
  risk_tags: ["config", "auth", "deploy"]
})
```

### Step 3: Correlate with Symptoms

Look for changes that could cause the observed symptoms.

## Change Logging

For the 48-hour rule to work, you need to log changes:

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

### What to Log

| Change Type | Example |
|-------------|---------|
| Config changes | Environment variables, settings |
| Schema changes | Database migrations |
| Deploy changes | New versions, rollbacks |
| Auth changes | Permissions, tokens |
| Infra changes | Scaling, networking |

### Risk Tags

Tag changes by risk category:

| Tag | What It Covers |
|-----|---------------|
| `config` | Configuration files, settings |
| `db` | Database schema, migrations |
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

## Integration with Debug Gate

The debug gate requires 48-hour scan:

```javascript
duro_store_incident({
  symptom: "API returning 500 errors",
  actual_cause: "Config removed AUTH_SECRET",
  fix: "Added AUTH_SECRET",
  recent_change_scan: {
    hours: 48,
    risk_tags: ["config", "deploy"],
    results: ["change_xyz"],
    linked: ["change_xyz"]
  }
})
```

### Gate Requirement

Pass 3 of the debug gate requires:
- 48-hour change scan completed
- Changes linked to incident, OR
- `cleared_reason` explaining why no changes are related

```javascript
recent_change_scan: {
  hours: 48,
  results: [],
  cleared_reason: "No infra changes; issue was malformed user input"
}
```

## Best Practices

### Log Changes When You Make Them

Don't wait until something breaks:

```javascript
// When making a change
duro_store_change({
  scope: "auth-service",
  change: "Added rate limiting to /api/login",
  risk_tags: ["api", "auth"]
})
```

### Include Quick Checks

Help future debugging:

```javascript
duro_store_change({
  ...
  quick_checks: [
    "Login works with valid credentials",
    "Rate limit triggers after 5 attempts",
    "Error message is user-friendly"
  ]
})
```

### Use Specific Scopes

```javascript
// Good - specific
scope: "auth-service/jwt-validation"

// Less good - vague
scope: "backend"
```

### Tag Accurately

More tags = better correlation:

```javascript
// Good - multiple relevant tags
risk_tags: ["auth", "config", "env"]

// Less good - single vague tag
risk_tags: ["change"]
```

## Debugging Workflow

```
1. Observe symptom
         ↓
2. duro_query_recent_changes({hours: 48})
         ↓
3. Filter by likely risk_tags
         ↓
4. Review changes that could cause symptom
         ↓
5. Verify correlation
         ↓
6. Fix issue
         ↓
7. duro_store_incident with linked changes
         ↓
8. duro_store_change for the fix
```

## Example

### The Incident

API returning 500 errors after deploy.

### Query Changes

```javascript
duro_query_recent_changes({
  hours: 48,
  risk_tags: ["deploy", "config"]
})
```

### Results

```
change_abc: "Deployed v2.3.1" (2h ago)
change_xyz: "Updated env vars" (4h ago)
```

### Correlate

Check `change_xyz` - found it removed AUTH_SECRET.

### Document

```javascript
duro_store_incident({
  symptom: "API 500 errors after deploy",
  actual_cause: "change_xyz removed AUTH_SECRET env var",
  fix: "Added AUTH_SECRET back",
  prevention: "Add startup check for required env vars",
  recent_change_scan: {
    hours: 48,
    linked: ["change_xyz"]
  }
})
```

## Next Steps

- [Debug tools reference](/reference/debug-tools)
- [Debugging guide](/guide/debugging)
- [Incident storage](/reference/memory-tools#duro_store_incident)
