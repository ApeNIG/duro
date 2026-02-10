# Duro - Safety Guardrails

## Core Principle
**Capability through composition, safety through constraints.**

---

## Permission Tiers

### Tier 1: SAFE (Auto-execute)
No approval needed:
- Read any file in registered projects
- Search codebases (grep, glob)
- Web search (no auth)
- Read public web pages
- List directories
- Run read-only git commands (status, log, diff)

### Tier 2: CAUTION (Log + Proceed)
Log action, proceed unless user has blocked:
- Write files within project workspace
- Create new files within project workspace
- Run tests
- Install dependencies (pip, npm)
- Git add, commit (local only)

### Tier 3: DANGER (Require Approval)
Must ask user before executing:
- Delete any file
- Git push to remote
- Run arbitrary shell commands
- Access files outside registered projects
- Modify system settings
- Send emails or external requests
- Access credentials or secrets
- Execute code that wasn't written by agent

### Tier 4: FORBIDDEN (Never Execute)
Hard-blocked, no exceptions:
- `rm -rf` or recursive delete
- Format/wipe commands
- Modify system files (hosts, registry, etc.)
- Access ~/.ssh, credentials, tokens
- Run downloaded scripts (`curl | sh`, etc.)
- Disable security features
- Access other users' directories
- Network scanning or exploitation

---

## Shell Command Allowlist

### Allowed Commands
```
python, python3, pip, pip3
node, npm, npx, yarn, pnpm
git (read operations + local commits)
pytest, jest, vitest, cargo test
rg, grep, find, ls, cat, head, tail
ffmpeg, imagemagick (media processing)
playwright (browser automation)
```

### Blocked Patterns
```
rm -rf, del /s /q, format
shutdown, reboot, halt
curl | sh, wget | bash
Set-ExecutionPolicy, Invoke-WebRequest | iex
sudo, runas, chmod 777
DROP TABLE, DELETE FROM (without WHERE)
eval(), exec() on untrusted input
```

---

## Workspace Sandboxing

### Allowed Paths
Only these directories are accessible:
- Registered project directories (from projects/registry.md)
- Agent workspace (~/.agent)
- Temp directories for processing

### Forbidden Paths
Never access:
- `~/.ssh/`
- `~/.aws/`
- `~/.config/` (except agent config)
- Environment files with secrets
- System directories
- Other users' home directories

---

## Approval Checkpoints

Before these actions, ALWAYS show the user:
1. Exact command/code to be executed
2. Files that will be modified
3. Expected outcome
4. Risk level
5. Rollback plan

Wait for explicit "yes" or "proceed" before executing.

---

## Sub-Agent Constraints

| Agent | Can Read | Can Write | Can Execute | Can Push |
|-------|----------|-----------|-------------|----------|
| Researcher | Yes | No | No | No |
| Coder | Yes | Project only | Tests only | No |
| Critic | Yes | No | No | No |
| Deployer | Yes | With approval | With approval | With approval |

---

## Emergency Stop

If anything goes wrong:
1. User can say "stop" or "abort" at any time
2. All running sub-agents terminate
3. Last 5 actions are logged for review
4. Rollback instructions provided
