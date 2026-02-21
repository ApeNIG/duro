# MCP Tools Overview

Duro exposes 50+ MCP tools through the Model Context Protocol. Here's a categorized overview.

## Tool Categories

| Category | Purpose | Key Tools |
|----------|---------|-----------|
| [Memory](/reference/memory-tools) | Store knowledge | `store_fact`, `store_decision`, `store_incident` |
| [Search](/reference/search-tools) | Find knowledge | `semantic_search`, `query_memory`, `proactive_recall` |
| [Validation](/reference/validation-tools) | Track outcomes | `validate_decision`, `supersede_fact`, `reinforce_fact` |
| [Debug](/reference/debug-tools) | 48-hour rule | `query_recent_changes`, `debug_gate_start` |
| [System](/reference/system-tools) | Maintenance | `status`, `health_check`, `maintenance_report` |

## Quick Reference

### Store Things

```
duro_store_fact          # Store a fact with provenance
duro_store_decision      # Record a decision with rationale
duro_save_learning       # Save a quick learning
duro_save_memory         # Save to daily log
duro_store_incident      # Record an RCA
duro_store_change        # Log a recent change
```

### Find Things

```
duro_semantic_search     # Search by meaning
duro_query_memory        # Search by tags, type, date
duro_proactive_recall    # Auto-surface relevant memories
duro_get_artifact        # Get full artifact by ID
duro_list_artifacts      # List recent artifacts
```

### Validate Things

```
duro_validate_decision   # Mark validated/reversed/superseded
duro_supersede_fact      # Replace old fact with new
duro_reinforce_fact      # Reset decay, confirm still valid
duro_apply_decay         # Apply time-based confidence decay
```

### Debug Things

```
duro_query_recent_changes  # 48-hour change ledger
duro_debug_gate_start      # Start debugging session
duro_debug_gate_status     # Check what's missing for RCA
duro_store_incident        # Record incident with prevention
```

### System Things

```
duro_status              # System status and stats
duro_health_check        # Run diagnostics
duro_maintenance_report  # Memory health report
duro_load_context        # Load context at session start
duro_reindex             # Rebuild SQLite index
```

## Common Patterns

### Store and Validate Flow

```javascript
// 1. Store a decision
duro_store_decision({
  decision: "Use Redis for session storage",
  rationale: "PostgreSQL sessions causing latency",
  tags: ["architecture", "performance"]
})

// 2. Later, validate based on outcome
duro_validate_decision({
  decision_id: "decision_xxx",
  status: "validated",
  actual_outcome: "Latency reduced by 60%"
})
```

### Debug with 48-Hour Rule

```javascript
// 1. Something broke - check recent changes
duro_query_recent_changes({
  hours: 48,
  risk_tags: ["config", "deploy"]
})

// 2. Start debug session
duro_debug_gate_start({
  symptom: "API returning 500 errors"
})

// 3. Store incident with prevention
duro_store_incident({
  symptom: "API 500 errors",
  actual_cause: "Config change broke auth",
  fix: "Reverted config",
  prevention: "Add auth smoke test to deploy"
})
```

### Proactive Recall

```javascript
// Automatically called when context matches
duro_proactive_recall({
  context: "implementing rate limiting for external API"
})

// Returns relevant facts and decisions
// e.g., "Rate limit is 100/min, not 1000"
```

## Tool Parameters

Most tools accept these common parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `tags` | string[] | Searchable tags |
| `sensitivity` | enum | `public`, `internal`, `sensitive` |
| `confidence` | number | 0.0 to 1.0 |
| `limit` | number | Max results to return |

## Next Steps

- [Memory Tools Reference](/reference/memory-tools)
- [Search Tools Reference](/reference/search-tools)
- [Validation Tools Reference](/reference/validation-tools)
