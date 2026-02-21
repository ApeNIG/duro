# Architecture

How Duro is built and how the pieces fit together.

## High-Level Overview

```
┌─────────────────────────────────────────────────────────┐
│                     YOUR AI CLIENT                       │
│              (Claude Code, Claude Desktop)               │
└─────────────────────────┬───────────────────────────────┘
                          │ MCP Protocol
                          ▼
┌─────────────────────────────────────────────────────────┐
│                     DURO MCP SERVER                      │
│  ┌──────────┬──────────┬──────────┬──────────────────┐  │
│  │  Memory  │  Search  │Validation│   Orchestration  │  │
│  │  Layer   │  Layer   │  Layer   │      Layer       │  │
│  └────┬─────┴────┬─────┴────┬─────┴────────┬─────────┘  │
│       │          │          │              │            │
│  ┌────▼──────────▼──────────▼──────────────▼─────────┐  │
│  │                  SQLite Index                      │  │
│  │            (FTS5 + Vector Search)                  │  │
│  └────────────────────────┬──────────────────────────┘  │
└───────────────────────────┼─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                    FILE STORAGE                          │
│  ~/.agent/                                               │
│  ├── memory/           # JSON artifacts                  │
│  ├── skills/           # Skill definitions               │
│  ├── rules/            # Behavioral rules                │
│  ├── soul.md           # Personality config              │
│  └── duro.db           # SQLite index                    │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### MCP Server

The Model Context Protocol server exposes Duro's tools:

```python
# Entry point
python -m duro.mcp_server
```

Handles:
- Tool registration with MCP
- Request routing
- Response formatting
- Error handling

### Memory Layer

Stores and retrieves artifacts:

- **Artifact types**: fact, decision, episode, incident, change
- **Storage format**: JSON files with consistent schema
- **Indexing**: SQLite with FTS5 for full-text search

### Search Layer

Finds relevant knowledge:

- **Semantic search**: Vector embeddings + cosine similarity
- **Keyword search**: FTS5 full-text search
- **Hybrid search**: Combines both with score fusion
- **Proactive recall**: Automatic context-based retrieval

### Validation Layer

Tracks outcomes:

- **Decision lifecycle**: pending → validated/reversed/superseded
- **Confidence decay**: Time-based degradation for unreinforced facts
- **Reinforcement**: Reset decay on confirmation
- **Validation history**: Full audit trail

### Orchestration Layer

Controls autonomy:

- **Permission checking**: Pre-action gates
- **Reputation tracking**: Per-domain trust scores
- **Approval workflow**: One-shot tokens for risky actions
- **Audit logging**: All decisions recorded

## Storage Format

### Artifact JSON

All artifacts follow a common envelope:

```json
{
  "id": "fact_20260210_123456_abc123",
  "type": "fact",
  "created_at": "2026-02-10T12:34:56Z",
  "updated_at": "2026-02-10T12:34:56Z",
  "sensitivity": "internal",
  "tags": ["api", "rate-limit"],
  "workflow": "manual",
  "content": {
    "claim": "API rate limit is 100 requests per minute",
    "confidence": 0.9,
    "source_urls": ["https://example.com/docs"],
    "evidence_type": "quote"
  }
}
```

### Directory Structure

```
~/.agent/
├── duro/                   # Core server code
│   ├── mcp_server.py       # MCP entry point
│   ├── memory/             # Memory layer
│   ├── search/             # Search layer
│   ├── validation/         # Validation layer
│   └── orchestration/      # Orchestration layer
├── memory/                 # Artifact storage
│   ├── facts/              # fact_*.json
│   ├── decisions/          # decision_*.json
│   ├── episodes/           # episode_*.json
│   ├── incidents/          # incident_*.json
│   └── changes/            # change_*.json
├── skills/                 # Skill definitions
├── rules/                  # Behavioral rules
├── soul.md                 # Personality config
└── duro.db                 # SQLite index
```

## SQLite Index

The SQLite database provides fast queries:

### Tables

| Table | Purpose |
|-------|---------|
| `artifacts` | Core artifact metadata |
| `artifact_fts` | FTS5 full-text search |
| `embeddings` | Vector embeddings |
| `audit_log` | Security audit trail |
| `reputation` | Per-domain trust scores |

### Sync

The index syncs with JSON files:

- Artifacts are source of truth (JSON)
- Index is derived (SQLite)
- `duro_reindex` rebuilds from files

## Search Architecture

### Semantic Search

```
Query → Embed → Vector Search → Rank → Results
```

Uses embeddings for semantic similarity.

### Keyword Search

```
Query → Tokenize → FTS5 Search → Rank → Results
```

Uses SQLite FTS5 for exact matches.

### Hybrid Search

```
Query → [Semantic + Keyword] → Score Fusion → Results
```

Combines both for best results.

## Security Model

### Layers

1. **Workspace constraints**: Path validation
2. **Permission gates**: Action approval
3. **Reputation system**: Earned autonomy
4. **Audit logging**: Full accountability

### Sensitive Data

- Artifacts can be marked `sensitive`
- Sensitive artifacts require force flag to delete
- All deletions logged with reason

## Local-First Design

Duro runs entirely on your machine:

- **No cloud required**: All data local
- **No API keys needed**: Uses local embeddings
- **Git-friendly**: JSON files version well
- **Portable**: Copy ~/.agent to move

## Extensibility

### Skills

Custom skills in `~/.agent/skills/`:

```json
{
  "name": "my-skill",
  "description": "What it does",
  "triggers": ["keyword"],
  "actions": [...]
}
```

### Rules

Behavioral rules in `~/.agent/rules/`:

```json
{
  "name": "my-rule",
  "when": "condition",
  "then": "action"
}
```

### Soul

Personality config in `~/.agent/soul.md`:

```markdown
# Soul Configuration

## Personality
- Direct and technical
- Focused on outcomes

## Preferences
- Prefer simple solutions
- Test before deploy
```

## Next Steps

- [Memory concepts](/concepts/memory)
- [Verification concepts](/concepts/verification)
- [Installation guide](/guide/installation)
