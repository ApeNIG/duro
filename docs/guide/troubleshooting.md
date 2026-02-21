# Troubleshooting

Common issues and how to fix them.

## Connection Issues

### "Duro tools not available"

**Symptom**: Claude doesn't recognize Duro tools.

**Solution**:
1. Check MCP configuration in your client
2. Verify path to `.agent` directory is correct
3. Restart your client

```json
{
  "mcpServers": {
    "duro": {
      "command": "python",
      "args": ["-m", "duro.mcp_server"],
      "cwd": "/correct/path/to/.agent"
    }
  }
}
```

### "MCP server not responding"

**Symptom**: Tools timeout or don't respond.

**Solution**:
```javascript
// Test server responsiveness
duro_heartbeat({ echo: "test" })

// Check health
duro_health_check({ verbose: true })
```

If heartbeat fails, check:
- Python is in PATH
- Dependencies are installed (`pip install -e .`)
- No other process using the port

## Search Issues

### "No results found"

**Symptom**: Semantic search returns empty results.

**Solutions**:

1. **Check embeddings exist**:
```javascript
duro_health_check()
// Look for "embedding coverage" in output
```

2. **Reembed if missing**:
```javascript
duro_reembed({ missing_only: true })
```

3. **Try keyword search**:
```javascript
duro_query_memory({
  search_text: "your keywords"
})
```

### "Search results not relevant"

**Symptom**: Results don't match query intent.

**Solutions**:

1. **Use more specific queries**:
```javascript
// Instead of
duro_semantic_search({ query: "rate limit" })

// Try
duro_semantic_search({
  query: "external API rate limiting configuration"
})
```

2. **Filter by type**:
```javascript
duro_semantic_search({
  query: "rate limit",
  artifact_type: "fact"
})
```

3. **Use tags**:
```javascript
duro_query_memory({
  tags: ["api", "rate-limit"]
})
```

## Index Issues

### "Stale search results"

**Symptom**: Search returns old or deleted artifacts.

**Solution**:
```javascript
// Rebuild index from files
duro_reindex()
```

### "Index out of sync"

**Symptom**: Health check shows sync issues.

**Solution**:
```javascript
// Check status
duro_health_check({ verbose: true })

// Rebuild
duro_reindex()

// Regenerate embeddings
duro_reembed({ all: true, limit: 100 })
```

## Memory Issues

### "Facts decaying too fast"

**Symptom**: Important facts losing confidence.

**Solutions**:

1. **Reinforce important facts**:
```javascript
duro_reinforce_fact({ fact_id: "fact_xxx" })
```

2. **Pin critical facts**:
Store with high importance, they won't decay.

3. **Check decay settings**:
```javascript
duro_apply_decay({ dry_run: true })
```

### "Too many stale facts"

**Symptom**: Maintenance report shows high stale percentage.

**Solution**:
```javascript
// Review stale facts
duro_maintenance_report({
  include_stale_list: true,
  top_n_stale: 20
})

// Reinforce valid ones
duro_reinforce_fact({ fact_id: "fact_xxx" })

// Or let them decay naturally
```

## Permission Issues

### "Action blocked by policy gate"

**Symptom**: Tool call denied.

**Solutions**:

1. **Check why it's blocked**:
```javascript
duro_classify_action({ action: "delete_file" })
```

2. **Grant approval**:
```javascript
duro_grant_approval({
  action_id: "tool_name:args_hash",
  reason: "Cleanup operation"
})
```

3. **Check reputation**:
```javascript
duro_get_reputation()
```

### "Workspace path not allowed"

**Symptom**: File operations blocked outside workspace.

**Solutions**:

1. **Check current workspaces**:
```javascript
duro_workspace_status()
```

2. **Add workspace**:
```javascript
duro_workspace_add({ path: "/path/to/project" })
```

3. **Validate specific path**:
```javascript
duro_workspace_validate({ path: "/some/path" })
```

## Debug Gate Issues

### "Incident rejected by debug gate"

**Symptom**: Can't store incident, gate requirements not met.

**Solution**:
```javascript
// Check what's missing
duro_debug_gate_status({ incident_id: "incident_xxx" })
```

Requirements:
- **Pass 1**: At least 2 repro steps
- **Pass 2**: First bad boundary identified
- **Pass 3**: 48-hour change scan completed

### "Prevention not actionable"

**Symptom**: Gate rejects prevention like "be more careful".

**Solution**:
Use actionable prevention:

```javascript
// Bad
prevention: "Remember to check config"

// Good
prevention: "Add startup assertion that AUTH_SECRET exists"
```

## Performance Issues

### "Context loading slow"

**Symptom**: `duro_load_context` takes too long.

**Solutions**:

1. **Use lean mode**:
```javascript
duro_load_context({ mode: "lean" })  // ~3K tokens
```

2. **Compress old logs**:
```javascript
duro_compress_logs()
```

### "Too many artifacts"

**Symptom**: Queries slow, large database.

**Solutions**:

1. **Clean up test artifacts**:
```javascript
duro_batch_delete({
  artifact_ids: ["test_xxx", "test_yyy"],
  reason: "Cleaning test data"
})
```

2. **Prune orphan embeddings**:
```javascript
duro_prune_orphans({ dry_run: false })
```

## Getting Help

### Check System Status

```javascript
duro_status()
duro_health_check({ verbose: true })
```

### Review Audit Log

```javascript
duro_gate_audit({ limit: 20 })
```

### GitHub Issues

Report bugs at: https://github.com/ApeNIG/duro/issues

Include:
- Duro version
- Error message
- Steps to reproduce
- Health check output
