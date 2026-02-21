# Configuration

Customize Duro for your workflow.

## MCP Server Configuration

The MCP server can be configured via your client's settings.

### Claude Code

Add to your MCP settings file:

```json
{
  "mcpServers": {
    "duro": {
      "command": "python",
      "args": ["-m", "duro.mcp_server"],
      "cwd": "/path/to/.agent"
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DURO_HOME` | Base directory | `~/.agent` |
| `DURO_DB` | SQLite database path | `$DURO_HOME/duro.db` |
| `DURO_LOG_LEVEL` | Logging level | `INFO` |

## Soul Configuration

The `soul.md` file defines agent personality:

```markdown
# Soul Configuration

## Personality
- Direct and technical
- Focus on outcomes over process
- Prefer simple solutions

## Working Style
- Test before deploying
- Log important changes
- Validate decisions when outcomes are known

## Preferences
- Use semantic search over keyword search
- Store facts with sources when possible
- Keep confidence scores conservative
```

## Workspace Configuration

Control where Duro can access files:

```javascript
// View current workspace settings
duro_workspace_status()

// Add a workspace
duro_workspace_add({
  path: "/home/user/projects"
})
```

### Strict Mode

When enabled, file operations outside workspaces are blocked:

- Default: strict mode enabled
- Paths outside home require approval

## Context Loading

Configure how much context loads at session start:

```javascript
// Minimal (~500 tokens)
duro_load_context({ mode: "minimal" })

// Lean (~3K tokens) - recommended
duro_load_context({ mode: "lean" })

// Full (~10K tokens)
duro_load_context({ mode: "full" })
```

### Mode Comparison

| Mode | Includes | Use When |
|------|----------|----------|
| `minimal` | Soul + core memory | Quick tasks |
| `lean` | + today's tasks, active decisions | Normal sessions |
| `full` | + full history | Deep dives |

## Rules Configuration

Add behavioral rules in `~/.agent/rules/`:

```json
{
  "id": "require-source-for-facts",
  "name": "Require sources for high-confidence facts",
  "trigger": "store_fact with confidence >= 0.8",
  "condition": "source_urls is empty",
  "action": "warn",
  "message": "High-confidence facts should have source URLs"
}
```

## Skills Configuration

Define custom skills in `~/.agent/skills/`:

```json
{
  "id": "weekly-review",
  "name": "Weekly Review",
  "description": "Review unvalidated decisions",
  "trigger": "weekly-review",
  "actions": [
    {
      "tool": "duro_list_unreviewed_decisions",
      "args": { "older_than_days": 7 }
    }
  ]
}
```

## Decay Configuration

Configure confidence decay behavior:

```javascript
// Preview decay effects
duro_apply_decay({ dry_run: true })

// Configure minimum importance threshold
duro_apply_decay({
  dry_run: false,
  min_importance: 0.5  // Only decay less important facts
})
```

### Pinning Facts

Prevent decay on critical facts:

```javascript
// Facts can be pinned to prevent decay
duro_store_fact({
  claim: "Production database password is in 1Password",
  confidence: 1.0,
  // Pinned facts don't decay
})
```

## Database Maintenance

### Reindex

Rebuild the index from artifact files:

```javascript
duro_reindex()
```

### Reembed

Regenerate embeddings:

```javascript
duro_reembed({
  missing_only: true  // Only embed new artifacts
})
```

### Compress Logs

Archive old memory logs:

```javascript
duro_compress_logs()
```

## Recommended Setup

### Session Start

Add to your `CLAUDE.md`:

```markdown
## Session Startup
At the START of every session, call:
duro_load_context(mode="lean")
```

### Session End

```markdown
## Session End
When ending a session:
1. Save learnings with duro_save_learning
2. Log tasks with duro_log_task
```

## Next Steps

- [Store your first fact](/guide/storing-knowledge)
- [System tools reference](/reference/system-tools)
- [Architecture overview](/concepts/architecture)
