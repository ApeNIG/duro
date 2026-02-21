# Orchestration

> "Earn autonomy through trust"

Orchestration is how Duro controls what actions the agent can take, with graduated autonomy based on demonstrated competence.

## The Trust Model

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   NEW AGENT ──────────────────────────► TRUSTED AGENT   │
│                                                         │
│   Propose only → Supervised → Semi-auto → Autonomous    │
│                                                         │
│   [Low trust]                            [High trust]   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Autonomy Levels

| Level | Description | Example |
|-------|-------------|---------|
| `propose` | Can only suggest, never execute | "I recommend deleting this file" |
| `supervised` | Execute with explicit approval | "Delete file? [Y/n]" |
| `semi-auto` | Execute unless objected | "Deleting file in 5s..." |
| `autonomous` | Execute without asking | (file deleted) |

## Permission Checking

Before risky operations, check permission:

```javascript
duro_check_permission({
  action: "delete_file",
  context: {
    is_destructive: true,
    affects_production: false,
    is_reversible: false
  }
})
```

### Response

```json
{
  "allowed": false,
  "reason": "Destructive action requires approval",
  "required_level": "supervised",
  "current_level": "propose"
}
```

## Quick Pre-Check

For per-tool-call gates:

```javascript
duro_can_execute({
  tool_name: "duro_delete_artifact",
  args_hint: "delete fact_xxx"
})
```

Returns machine-readable JSON:

```json
{
  "can_execute": false,
  "action_needed": "approve",
  "reason": "Destructive operation requires approval"
}
```

## Reputation System

Reputation is tracked per domain:

### Domains

| Domain | What It Covers |
|--------|---------------|
| `code_changes` | File edits, code modifications |
| `incident_rca` | Debugging, incident analysis |
| `decisions` | Architectural choices |
| `deployments` | Production changes |

### Check Reputation

```javascript
duro_get_reputation({
  domain: "code_changes"
})
```

### Build Reputation

```javascript
duro_record_outcome({
  action: "edit_file",
  success: true,
  confidence: 0.8
})
```

Successful outcomes increase reputation. Failures and reverts decrease it.

## Approval Workflow

For high-risk actions, grant one-shot approval:

```javascript
duro_grant_approval({
  action_id: "duro_delete_artifact:a1b2c3d4",
  reason: "Cleaning up test artifacts",
  duration_seconds: 300  // 5 minute window
})
```

### Approval Properties

- **One-shot**: Token consumed on first use
- **Scoped**: Exact action + args, not just tool
- **Time-limited**: Expires after duration
- **Audited**: Recorded for accountability

## Audit Trail

All permission decisions are logged:

```javascript
duro_gate_audit({
  decision: "DENY",
  limit: 20
})
```

### Query Options

| Filter | Description |
|--------|-------------|
| `decision` | `ALLOW`, `DENY`, `NEED_APPROVAL` |
| `tool` | Specific tool name |
| `since` | ISO timestamp |

## Workspace Constraints

Duro enforces workspace boundaries:

```javascript
// Check workspace status
duro_workspace_status()

// Validate a path
duro_workspace_validate({
  path: "/etc/passwd"
})
```

### Adding Workspaces

```javascript
duro_workspace_add({
  path: "/home/user/projects"
})
```

Paths outside home directory require approval.

## Classifying Actions

Debug tool to understand why actions are blocked:

```javascript
duro_classify_action({
  action: "deploy_production",
  context: {
    affects_production: true,
    is_reversible: false
  }
})
```

### Returns

```json
{
  "domain": "deployments",
  "risk_level": "high",
  "required_autonomy": "supervised",
  "reason": "Production deployment is high-risk"
}
```

## Autonomy Status

Get overall autonomy status:

```javascript
duro_autonomy_status()
```

### Shows

- Overall reputation
- Per-domain scores
- Active approvals
- Current constraints

## Best Practices

### Start Restricted

New agents should start at `propose` level. Build trust through successful outcomes.

### Grant Specific Approvals

Don't grant broad permissions. Use scoped approvals for specific actions.

### Review Audit Logs

Periodically review denied actions to understand patterns.

### Build Reputation Gradually

Small successes compound into autonomy for larger actions.

## Next Steps

- [Expertise: Skill building](/concepts/expertise)
- [Memory: Knowledge storage](/concepts/memory)
- [System tools reference](/reference/system-tools)
