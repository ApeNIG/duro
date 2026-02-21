# Waiver Protocol Spec

**Status:** Draft
**Author:** Claude + Human
**Date:** 2026-02-15

## Problem

Hard enforcement blocks legitimate operations. Without a controlled override mechanism, humans will:
1. Disable the entire hook
2. Remove patterns that are "annoying"
3. Work around the system entirely

This defeats the purpose of having enforcement.

## Solution

A **waiver protocol** that allows controlled overrides with paperwork:
- Explicit rule targeting (no blanket waivers)
- Mandatory reason (audit trail)
- Logged to telemetry (observable)
- CI threshold (prevents waiver abuse)

---

## Design

### 1. Waiver Format

**Environment variable approach:**
```bash
DURO_WAIVE="rule_id:Your reason here"
```

**Examples:**
```bash
# Waive destructive command block for test cleanup
DURO_WAIVE="destructive_bash_commands:Cleaning test fixtures in CI"

# Waive force push for branch rename
DURO_WAIVE="destructive_bash_commands:Renaming feature branch, coordinated with team"
```

**Constraints:**
- Rule ID must match an existing enforcement rule
- Reason must be ≥10 characters (no empty/trivial reasons)
- One waiver per invocation (no stacking)
- Waiver applies only to the current command

### 2. Unwaivable Rules

Some rules are **never waivable** — the risk is too high:

| Rule ID | Why Unwaivable |
|---------|----------------|
| `secrets_in_git` | Secrets in git are unrecoverable once pushed |
| `bootstrap_failure` | System integrity must be fixed, not bypassed |

These are hardcoded in the hook. No env var can override them.

### 3. Waiver Validation

The hook validates waivers before allowing override:

```python
def validate_waiver(waiver_str: str, rule_id: str) -> Tuple[bool, str]:
    """Validate a waiver string.

    Returns (valid, error_message).
    """
    if not waiver_str:
        return False, "No waiver provided"

    if ':' not in waiver_str:
        return False, "Waiver must be 'rule_id:reason'"

    waiver_rule, reason = waiver_str.split(':', 1)

    if waiver_rule != rule_id:
        return False, f"Waiver is for '{waiver_rule}', not '{rule_id}'"

    if rule_id in UNWAIVABLE_RULES:
        return False, f"Rule '{rule_id}' cannot be waived"

    if len(reason.strip()) < 10:
        return False, "Waiver reason must be ≥10 characters"

    return True, reason
```

### 4. Telemetry Logging

Waived operations are logged with decision `"waived"`:

```json
{
  "ts": "2026-02-15T20:30:00.000000",
  "tool": "Bash",
  "summary": "rm -rf ./test-fixtures",
  "decision": "waived",
  "rule": "destructive_bash_commands",
  "waiver_reason": "Cleaning test fixtures in CI"
}
```

### 5. Scoreboard Metrics

New file: `~/.agent/metrics/waiver_scoreboard.json`

```json
{
  "updated": "2026-02-15T20:30:00Z",
  "period": "weekly",
  "total_waivers": 3,
  "by_rule": {
    "destructive_bash_commands": 2,
    "path_sandbox": 1
  },
  "by_day": {
    "2026-02-15": 3
  },
  "recent": [
    {
      "ts": "2026-02-15T20:30:00Z",
      "rule": "destructive_bash_commands",
      "reason": "Cleaning test fixtures in CI",
      "command_preview": "rm -rf ./test-fixtures"
    }
  ]
}
```

### 6. CI Threshold

GitHub Actions workflow checks waiver count:

```yaml
- name: Check waiver threshold
  run: |
    WAIVER_COUNT=$(jq '.total_waivers' ~/.agent/metrics/waiver_scoreboard.json)
    THRESHOLD=10
    if [ "$WAIVER_COUNT" -gt "$THRESHOLD" ]; then
      echo "::error::Waiver count ($WAIVER_COUNT) exceeds threshold ($THRESHOLD)"
      exit 1
    fi
```

**Default thresholds:**
- Warning: >5 waivers/week
- Failure: >10 waivers/week

Thresholds are configurable in `enforcement_patterns.json`:

```json
{
  "waiver_policy": {
    "warn_threshold": 5,
    "fail_threshold": 10,
    "period": "weekly"
  }
}
```

---

## Hook Integration

### Modified Flow

```
PreToolUse hook triggered
    │
    ├─ Bootstrap check (fail closed, unwaivable)
    │
    ├─ MCP tools? → fast-path allow
    │
    ├─ Read tool? → record in ledger → allow
    │
    ├─ Check enforcement patterns
    │       │
    │       ├─ No match → allow
    │       │
    │       └─ Match found
    │               │
    │               ├─ Rule unwaivable? → BLOCK (no override)
    │               │
    │               ├─ Valid waiver? → LOG + ALLOW (waived)
    │               │
    │               └─ No waiver → BLOCK/WARN per rule action
    │
    └─ Hookify rules (fallback)
```

### Code Changes

Add to `pretooluse.py`:

```python
# Unwaivable rules - too dangerous to override
UNWAIVABLE_RULES = {'secrets_in_git', 'bootstrap_failure'}

# Waiver scoreboard location
WAIVER_SCOREBOARD = AGENT_DIR / 'metrics' / 'waiver_scoreboard.json'


def check_waiver(rule_id: str) -> Tuple[bool, Optional[str]]:
    """Check if a valid waiver exists for this rule.

    Returns (has_valid_waiver, reason).
    """
    waiver_str = os.environ.get('DURO_WAIVE', '')

    if not waiver_str:
        return False, None

    valid, result = validate_waiver(waiver_str, rule_id)

    if valid:
        return True, result  # result is the reason
    else:
        debug_log(f"Invalid waiver: {result}")
        return False, None


def record_waiver(rule_id: str, reason: str, command_preview: str) -> None:
    """Record waiver use to scoreboard."""
    try:
        WAIVER_SCOREBOARD.parent.mkdir(parents=True, exist_ok=True)

        # Load or initialize scoreboard
        if WAIVER_SCOREBOARD.exists():
            scoreboard = json.loads(WAIVER_SCOREBOARD.read_text())
        else:
            scoreboard = {
                "updated": None,
                "period": "weekly",
                "total_waivers": 0,
                "by_rule": {},
                "by_day": {},
                "recent": []
            }

        # Update counts
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')

        scoreboard["updated"] = now.isoformat() + "Z"
        scoreboard["total_waivers"] += 1
        scoreboard["by_rule"][rule_id] = scoreboard["by_rule"].get(rule_id, 0) + 1
        scoreboard["by_day"][today] = scoreboard["by_day"].get(today, 0) + 1

        # Add to recent (keep last 50)
        scoreboard["recent"].insert(0, {
            "ts": now.isoformat() + "Z",
            "rule": rule_id,
            "reason": reason,
            "command_preview": command_preview[:100]
        })
        scoreboard["recent"] = scoreboard["recent"][:50]

        # Prune old days (keep 30 days)
        cutoff = (now - timedelta(days=30)).strftime('%Y-%m-%d')
        scoreboard["by_day"] = {
            k: v for k, v in scoreboard["by_day"].items() if k >= cutoff
        }

        WAIVER_SCOREBOARD.write_text(json.dumps(scoreboard, indent=2))

    except Exception as e:
        debug_log(f"Error recording waiver: {e}")
```

---

## Usage Examples

### Legitimate Use: Test Cleanup

```bash
# In CI script
export DURO_WAIVE="destructive_bash_commands:Removing test fixtures after integration tests"
rm -rf ./test-output
unset DURO_WAIVE
```

### Legitimate Use: Force Push to Feature Branch

```bash
# After rebasing a feature branch (not main!)
export DURO_WAIVE="destructive_bash_commands:Force pushing rebased feature branch feature/new-ui"
git push --force origin feature/new-ui
unset DURO_WAIVE
```

### Rejected: Missing Reason

```bash
export DURO_WAIVE="destructive_bash_commands"
rm -rf ./test-output
# BLOCKED: Waiver must be 'rule_id:reason'
```

### Rejected: Trivial Reason

```bash
export DURO_WAIVE="destructive_bash_commands:ok"
rm -rf ./test-output
# BLOCKED: Waiver reason must be ≥10 characters
```

### Rejected: Wrong Rule

```bash
export DURO_WAIVE="path_sandbox:Cleaning test fixtures"
git push --force origin main
# BLOCKED: Waiver is for 'path_sandbox', not 'destructive_bash_commands'
```

### Rejected: Unwaivable Rule

```bash
export DURO_WAIVE="secrets_in_git:I really need to commit this .env"
git add .env
# BLOCKED: Rule 'secrets_in_git' cannot be waived
```

---

## Security Considerations

1. **No wildcard waivers** — Each waiver targets one rule
2. **Unwaivable rules** — Some risks are never acceptable
3. **Audit trail** — All waivers logged with reason and timestamp
4. **CI enforcement** — Excessive waivers fail the build
5. **Single-use** — Waiver applies to current command only, not persisted
6. **Reason quality** — Minimum length prevents trivial overrides

---

## Metrics to Track

| Metric | Good | Concerning | Action |
|--------|------|------------|--------|
| Waivers/week | 0-3 | >5 | Review waiver reasons |
| Same rule waived repeatedly | 0 | >3/week | Consider allowlist or safer primitive |
| Trivial reasons | 0 | Any | Tighten reason validation |
| Waivers on main branch | 0 | Any | Investigate immediately |

---

## Rollout Plan

1. **Phase 1:** Implement waiver check in hook (allow override, log to telemetry)
2. **Phase 2:** Add scoreboard tracking
3. **Phase 3:** Add CI threshold check
4. **Phase 4:** Add dashboard visualization (optional)

---

## Open Questions

1. **Multi-rule waivers?** — Current design is one rule per waiver. Stack with multiple env vars?
2. **Time-limited waivers?** — Should waivers expire after N seconds?
3. **Waiver approval workflow?** — For high-risk operations, require pre-approval?

---

## Appendix: Waiver Policy Config

Add to `enforcement_patterns.json`:

```json
{
  "waiver_policy": {
    "enabled": true,
    "unwaivable_rules": ["secrets_in_git"],
    "min_reason_length": 10,
    "thresholds": {
      "warn": 5,
      "fail": 10,
      "period": "weekly"
    }
  }
}
```
