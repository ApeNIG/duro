# System Tools

Tools for Duro system management and maintenance.

## duro_status

Get system status and statistics.

### Parameters

None required.

### Example

```javascript
duro_status()
```

### Returns

- Total artifacts by type
- Database size
- Last index time
- Active sessions
- Memory usage

---

## duro_health_check

Run health diagnostics.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `verbose` | boolean | No | Include detailed check information |

### Example

```javascript
duro_health_check({
  verbose: true
})
```

### Checks Performed

- SQLite integrity
- Index sync status
- Audit chain validity
- Disk space
- Embedding queue status

---

## duro_load_context

Load context at session start.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `mode` | enum | No | `full`, `lean`, `minimal` (default: full) |
| `recent_days` | number | No | Days of recent memory to load (default: 3) |
| `include_soul` | boolean | No | Include soul.md config (default: true) |

### Example

```javascript
// Recommended: lean mode for faster loading
duro_load_context({
  mode: "lean"
})

// Full context when needed
duro_load_context({
  mode: "full",
  recent_days: 7
})
```

### Mode Comparison

| Mode | Tokens | Includes |
|------|--------|----------|
| `minimal` | ~500 | Soul + core only |
| `lean` | ~3K | Soul, core, today's tasks, active decisions |
| `full` | ~10K | Everything including full session history |

---

## duro_maintenance_report

Generate memory health report.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `include_stale_list` | boolean | No | Include stale facts list (default: true) |
| `top_n_stale` | number | No | Number of stale facts to list (default: 10) |

### Example

```javascript
duro_maintenance_report({
  include_stale_list: true,
  top_n_stale: 10
})
```

### Report Includes

- Total facts and % pinned
- % stale (need reinforcement)
- Top stale high-importance facts
- Embedding coverage
- FTS coverage

---

## duro_reindex

Rebuild SQLite index from artifact files.

### Parameters

None required.

### Example

```javascript
duro_reindex()
```

### When to Use

- After manual file edits
- If search returns stale results
- After recovery from backup

---

## duro_reembed

Re-queue artifacts for embedding.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `artifact_ids` | string[] | No | Specific IDs to re-embed |
| `artifact_type` | string | No | Re-embed all of this type |
| `missing_only` | boolean | No | Only embed missing (default: false) |
| `all` | boolean | No | Re-embed ALL artifacts |
| `limit` | number | No | Max artifacts to process (default: 100) |
| `timeout_seconds` | number | No | Max seconds before stopping (default: 120) |

### Example

```javascript
// Re-embed missing embeddings
duro_reembed({
  missing_only: true,
  limit: 50
})

// Re-embed all facts
duro_reembed({
  artifact_type: "fact"
})
```

---

## duro_prune_orphans

Delete orphan embeddings.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dry_run` | boolean | No | Count without deleting (default: false) |
| `max_delete` | number | No | Max orphans to delete |

### Example

```javascript
// Check orphan count
duro_prune_orphans({
  dry_run: true
})

// Delete orphans
duro_prune_orphans({
  dry_run: false,
  max_delete: 100
})
```

---

## duro_compress_logs

Compress old memory logs into summaries.

### Parameters

None required.

### Example

```javascript
duro_compress_logs()
```

### Effect

- Archives raw logs
- Creates compact summaries
- Faster context loading

---

## duro_heartbeat

Test MCP server responsiveness.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `echo` | string | No | String to echo back |

### Example

```javascript
duro_heartbeat({
  echo: "test"
})
```

### Returns

- Timestamp
- Latency metrics
- Echo string (if provided)

---

## duro_run_migration

Run database migrations.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `action` | enum | No | `up` or `status` (default: status) |
| `migration_id` | string | No | Specific migration to run |

### Example

```javascript
// Check migration status
duro_run_migration({
  action: "status"
})

// Apply migrations
duro_run_migration({
  action: "up"
})
```

---

## Maintenance Workflow

### Daily

```javascript
// Check system health
duro_health_check()
```

### Weekly

```javascript
// Generate maintenance report
duro_maintenance_report()

// Compress old logs
duro_compress_logs()
```

### As Needed

```javascript
// After manual edits
duro_reindex()

// After model upgrade
duro_reembed({ all: true })

// Clean up orphans
duro_prune_orphans({ dry_run: false })
```
