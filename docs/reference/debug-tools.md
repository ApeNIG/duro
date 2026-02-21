# Debug Tools

Tools for debugging with the 48-hour rule.

## duro_query_recent_changes

Query changes within a time window.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `hours` | number | No | Look back this many hours (default: 48) |
| `risk_tags` | string[] | No | Filter by risk tags |
| `scope` | string | No | Filter by scope |
| `limit` | number | No | Max results (default: 20) |

### Example

```javascript
duro_query_recent_changes({
  hours: 48,
  risk_tags: ["config", "deploy", "auth"]
})
```

### Risk Tags

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

---

## duro_debug_gate_start

Start a debug session with gate prompts.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symptom` | string | Yes | What was observed failing |
| `tags` | string[] | No | Initial tags for risk inference |

### Example

```javascript
duro_debug_gate_start({
  symptom: "API returning 500 errors after deploy",
  tags: ["api", "deploy"]
})
```

### Returns

- Draft incident ID
- Prompts for each debug gate pass
- Inferred risk tags for 48-hour scan

---

## duro_debug_gate_status

Check what's missing to pass the debug gate.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `incident_id` | string | Yes | The incident ID to check |

### Example

```javascript
duro_debug_gate_status({
  incident_id: "incident_20260210_xxx"
})
```

### Gate Requirements

| Pass | Requirement |
|------|-------------|
| **Pass 1 (Repro)** | At least 2 reproduction steps |
| **Pass 2 (Boundary)** | First bad boundary identified |
| **Pass 3 (Causality)** | 48-hour change scan with links or cleared reason |

Plus: Prevention must be actionable.

---

## duro_store_incident

Store an incident RCA. (See [Memory Tools](/reference/memory-tools) for full docs)

### Debug Gate Enforced

The incident must pass all gate requirements:

```javascript
duro_store_incident({
  symptom: "API returning 500 errors",
  actual_cause: "Config removed AUTH_SECRET",
  fix: "Added AUTH_SECRET to deployment",
  prevention: "Add startup check for required env vars",
  repro_steps: [
    "Deploy latest main",
    "Call /api/auth endpoint"
  ],
  first_bad_boundary: "Service startup - env var validation",
  severity: "high",
  tags: ["config", "deploy", "auth"]
})
```

### Override (Use with Caution)

For emergencies, bypass the gate:

```javascript
duro_store_incident({
  symptom: "Production down",
  actual_cause: "Unknown - mitigated first",
  fix: "Rolled back deployment",
  override: true,
  override_reason: "Production down, mitigated first"
})
```

Creates a waiver trail for audit.

---

## duro_store_change

Log a change to the change ledger.

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
  ],
  commit_hash: "abc123"
})
```

### Best Practices

Log changes when you:
- Modify configuration
- Change database schema
- Update environment variables
- Deploy new code
- Change authentication settings
- Modify caching behavior

This powers the 48-hour rule for future debugging.

---

## Debug Workflow

```
1. Something broke
         ↓
2. duro_query_recent_changes({hours: 48})
         ↓
3. duro_debug_gate_start({symptom: "..."})
         ↓
4. Find repro steps (Pass 1)
         ↓
5. Identify first bad boundary (Pass 2)
         ↓
6. Link to recent changes (Pass 3)
         ↓
7. Fix the issue
         ↓
8. duro_store_incident({...})
         ↓
9. duro_store_change({...}) for the fix
```
