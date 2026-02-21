# Cheat Sheet

Quick reference for all Duro commands and tools.

## Store

| What | Natural Language | Tool |
|------|------------------|------|
| Fact | "store a fact: X" | `duro_store_fact` |
| Decision | "store a decision: X because Y" | `duro_store_decision` |
| Learning | "save a learning: X" | `duro_save_learning` |
| Incident | "log an incident: symptom, cause, fix" | `duro_store_incident` |
| Change | "record a change: X in scope Y" | `duro_store_change` |

## Search

| What | Natural Language | Tool |
|------|------------------|------|
| Semantic | "search duro for X" | `duro_semantic_search` |
| By tags | "query memories tagged: X" | `duro_query_memory` |
| Recent | "show recent decisions" | `duro_list_artifacts` |
| Proactive | (automatic on context) | `duro_proactive_recall` |

## Validate

| What | Natural Language | Tool |
|------|------------------|------|
| Confirm | "validate decision X - it worked" | `duro_validate_decision` |
| Reverse | "reverse decision X - it failed" | `duro_validate_decision` |
| Supersede | "X replaces decision Y" | `duro_supersede_fact` |
| Reinforce | "reinforce fact X" | `duro_reinforce_fact` |

## Debug

| What | Natural Language | Tool |
|------|------------------|------|
| Recent changes | "what changed in last 48h?" | `duro_query_recent_changes` |
| Start debug | "start debugging: symptom X" | `duro_debug_gate_start` |
| Check gate | "what's missing for incident X?" | `duro_debug_gate_status` |

## System

| What | Natural Language | Tool |
|------|------------------|------|
| Status | "duro status" | `duro_status` |
| Health | "check duro health" | `duro_health_check` |
| Load context | (auto at session start) | `duro_load_context` |
| Maintenance | "run maintenance report" | `duro_maintenance_report` |

## Artifact Types

| Type | What It Stores |
|------|----------------|
| `fact` | Objective claims with sources |
| `decision` | Choices with rationale |
| `episode` | Goal → actions → outcome |
| `incident` | RCA with prevention |
| `recent_change` | What changed when |

## Decision Statuses

| Status | Meaning |
|--------|---------|
| `pending` | Not yet validated |
| `validated` | Confirmed working |
| `reversed` | Didn't work |
| `superseded` | Replaced by newer |

## Confidence Scores

| Score | Meaning |
|-------|---------|
| 0.0 - 0.3 | Low confidence |
| 0.4 - 0.6 | Medium confidence |
| 0.7 - 0.8 | High confidence |
| 0.9 - 1.0 | Very high |

## Common Tags

```
api, database, auth, config, deploy
performance, security, testing, ci-cd
rate-limit, caching, logging, monitoring
```

## File Locations

```
~/.agent/
├── memory/
│   ├── facts/           # fact_*.json
│   ├── decisions/       # decision_*.json
│   ├── episodes/        # episode_*.json
│   └── incidents/       # incident_*.json
├── skills/              # skill definitions
├── rules/               # behavioral rules
├── soul.md              # personality config
└── duro.db              # SQLite index
```

## MCP Config

::: code-group

```json [macOS/Linux]
{
  "mcpServers": {
    "duro": {
      "command": "python",
      "args": ["-m", "duro.mcp_server"],
      "cwd": "/Users/yourname/.agent"
    }
  }
}
```

```json [Windows]
{
  "mcpServers": {
    "duro": {
      "command": "python",
      "args": ["-m", "duro.mcp_server"],
      "cwd": "C:\\Users\\yourname\\.agent"
    }
  }
}
```

:::

## Quick Patterns

### Store and Validate

```
1. store a decision: "Use X because Y"
2. (use it in practice)
3. validate the decision - confirmed working
```

### Debug with 48-Hour Rule

```
1. something broke
2. what changed in last 48 hours?
3. link change to incident
4. store incident with prevention
```

### Compound Learning

```
1. store fact with source
2. make decision based on fact
3. track outcome in episode
4. validate/reverse decision
5. update skill confidence
```
