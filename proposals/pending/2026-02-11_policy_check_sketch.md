# Policy Check at Orchestration Layer - Implementation Sketch

**Date:** 2026-02-11
**Status:** Design sketch
**Depends on:** Layered Governance Constitution (rule_006)

---

## Current Flow (No Policy Enforcement)

```
User prompt
    │
    ▼
duro_orchestrate(intent, args)
    │
    ├── check_rules(task_description)  ← TEXT MATCHING (bypassable)
    │
    ▼
select_tool_or_skill()
    │
    ▼
execute()  ← NO POLICY CHECK HERE
    │
    ▼
log_result()
```

## Proposed Flow (With Policy Check)

```
User prompt
    │
    ▼
duro_orchestrate(intent, args)
    │
    ├── check_rules(task_description)  ← Still useful for advisory
    │
    ▼
select_tool_or_skill()
    │
    ▼
build_action_plan()  ← NEW: Structured plan with tool + params
    │
    ▼
policy_check(plan)   ← NEW: Behavior-based enforcement
    │
    ├── ALLOW → execute()
    │
    └── DENY  → return { blocked: true, rule, alternative_path }
```

---

## Data Structures

### Action Plan

```typescript
interface ActionPlan {
  tool: string;                    // "Write" | "Edit" | "Bash" | etc.
  params: {
    file_path?: string;            // For Write/Edit
    command?: string;              // For Bash
    content?: string;              // What's being written
  };
  intent: string;                  // Original user intent
  derived_from?: string;           // How we got here
}
```

### Policy Check Result

```typescript
interface PolicyCheckResult {
  allowed: boolean;
  matched_rules: Array<{
    rule_id: string;
    rule_name: string;
    trigger_type: "file_pattern" | "command_pattern" | "keyword";
    trigger_match: string;         // What matched
  }>;
  enforcement?: {
    decision: "allow" | "deny" | "allow_with_constraints";
    check_id: string;              // e.g., "no-silent-waivers"
    denied_path: string;
    allowed_path: string;
    required_fields?: string[];
    next_action_template?: object;
  };
  message: string;
}
```

---

## Core Function: policy_check()

```typescript
async function policy_check(plan: ActionPlan): Promise<PolicyCheckResult> {
  // 1. Load rules with file_patterns or behavior_triggers
  const governanceRules = await loadRulesWithBehaviorTriggers();

  // 2. Check file patterns
  const fileMatches = checkFilePatterns(plan, governanceRules);

  // 3. Check command patterns (for Bash)
  const commandMatches = checkCommandPatterns(plan, governanceRules);

  // 4. Combine matches
  const allMatches = [...fileMatches, ...commandMatches];

  if (allMatches.length === 0) {
    return { allowed: true, matched_rules: [], message: "No policy constraints" };
  }

  // 5. Apply enforcement checks from matched rules
  for (const match of allMatches) {
    const enforcement = evaluateEnforcement(match.rule, plan);
    if (enforcement.decision === "deny") {
      return {
        allowed: false,
        matched_rules: allMatches,
        enforcement,
        message: `Blocked by ${match.rule.name}: ${enforcement.denied_path}`
      };
    }
  }

  return { allowed: true, matched_rules: allMatches, message: "Policy passed" };
}
```

---

## Pattern Matching Functions

### File Pattern Check

```typescript
function checkFilePatterns(
  plan: ActionPlan,
  rules: Rule[]
): RuleMatch[] {
  if (!plan.params.file_path) return [];

  const matches: RuleMatch[] = [];
  const filePath = plan.params.file_path;

  for (const rule of rules) {
    const patterns = rule.triggers?.file_patterns || [];
    for (const pattern of patterns) {
      if (matchesPattern(filePath, pattern)) {
        matches.push({
          rule_id: rule.id,
          rule_name: rule.name,
          trigger_type: "file_pattern",
          trigger_match: pattern,
          rule
        });
      }
    }
  }

  return matches;
}

function matchesPattern(filePath: string, pattern: string): boolean {
  // Exact match
  if (filePath.endsWith(pattern)) return true;

  // Contains match (for patterns like ".devkit-waiver.yml")
  if (filePath.includes(pattern)) return true;

  // Glob match (if we want to support **/pattern)
  // return minimatch(filePath, pattern);

  return false;
}
```

### Command Pattern Check (for Bash)

```typescript
function checkCommandPatterns(
  plan: ActionPlan,
  rules: Rule[]
): RuleMatch[] {
  if (plan.tool !== "Bash" || !plan.params.command) return [];

  const matches: RuleMatch[] = [];
  const command = plan.params.command;

  for (const rule of rules) {
    const behaviors = rule.triggers?.behavior_triggers || [];
    for (const behavior of behaviors) {
      if (commandMatchesBehavior(command, behavior)) {
        matches.push({
          rule_id: rule.id,
          rule_name: rule.name,
          trigger_type: "command_pattern",
          trigger_match: behavior,
          rule
        });
      }
    }
  }

  return matches;
}

function commandMatchesBehavior(command: string, behavior: string): boolean {
  // Check if command writes to governance files
  if (behavior.includes("writes to governance files")) {
    const governanceFiles = [".devkit-waiver", "devkit.config.json"];
    return governanceFiles.some(f => command.includes(f));
  }

  // Check for redirect/pipe to governance files
  if (command.includes(">") || command.includes(">>")) {
    const governanceFiles = [".devkit-waiver", "devkit.config.json"];
    return governanceFiles.some(f => command.includes(f));
  }

  return false;
}
```

---

## Enforcement Evaluation

```typescript
function evaluateEnforcement(
  rule: Rule,
  plan: ActionPlan
): EnforcementResult {
  const checks = rule.enforcement?.checks || [];

  for (const check of checks) {
    // Match check condition to plan
    if (checkConditionMatches(check.condition, plan)) {
      return {
        decision: check.decision,
        check_id: check.id,
        denied_path: check.denied_path,
        allowed_path: check.allowed_path,
        required_fields: check.required_fields,
        next_action_template: check.next_action_template
      };
    }
  }

  // No specific check matched, default allow
  return { decision: "allow", check_id: null };
}

function checkConditionMatches(condition: string, plan: ActionPlan): boolean {
  // "action plan includes writing .devkit-waiver.yml directly"
  if (condition.includes("writing .devkit-waiver.yml")) {
    return plan.tool === "Write" &&
           plan.params.file_path?.includes(".devkit-waiver");
  }

  // "action plan includes editing devkit.config.json directly"
  if (condition.includes("editing devkit.config.json")) {
    return plan.tool === "Edit" &&
           plan.params.file_path?.includes("devkit.config.json");
  }

  return false;
}
```

---

## Integration Point

### Option 1: Wrap Tool Calls

```typescript
// Before
await Write({ file_path: ".devkit-waiver.yml", content: "..." });

// After
async function safeExecute(tool: string, params: object) {
  const plan: ActionPlan = { tool, params, intent: currentIntent };

  const policy = await policy_check(plan);

  if (!policy.allowed) {
    console.log(`🛑 BLOCKED: ${policy.message}`);
    console.log(`   Allowed path: ${policy.enforcement.allowed_path}`);
    if (policy.enforcement.next_action_template) {
      console.log(`   Use this instead:`, policy.enforcement.next_action_template);
    }
    throw new PolicyViolationError(policy);
  }

  return execute(tool, params);
}
```

### Option 2: Add to duro_orchestrate

```python
# In Duro MCP server

def duro_orchestrate(intent: str, args: dict, dry_run: bool = False):
    # Existing: check rules by text
    rules = check_rules_by_text(intent)

    # Existing: select skill/tool
    skill = select_skill(intent)

    # NEW: Build action plan
    plan = build_action_plan(skill, args)

    # NEW: Policy check on plan
    policy = policy_check(plan)

    if not policy.allowed:
        return {
            "outcome": "denied",
            "rule": policy.matched_rules[0],
            "enforcement": policy.enforcement,
            "message": policy.message
        }

    if dry_run:
        return {"outcome": "dry_run", "plan": plan, "policy": policy}

    # Execute
    result = execute_skill(skill, args)

    # Log run
    log_run(intent, skill, result, policy)

    return result
```

---

## Example Scenarios

### Scenario 1: Direct Waiver Write (BLOCKED)

```
User: "exempt lint check temporarily"

Plan built:
  tool: "Write"
  params:
    file_path: ".devkit-waiver.yml"
    content: "waivers:\n  - rule: lint\n    ..."

Policy check:
  ✓ File pattern match: ".devkit-waiver.yml"
  ✓ Rule matched: rule_006 (Layered Governance Constitution)
  ✓ Check matched: "no-silent-waivers"

Result:
  allowed: false
  message: "Blocked by Layered Governance Constitution"
  denied_path: "Write waiver file directly via Write/Edit/Bash"
  allowed_path: "Open PR with waiver entry via gh pr create"
  next_action_template: { tool: "Bash", command: "gh pr create ..." }
```

### Scenario 2: PR-Based Waiver (ALLOWED)

```
User: "open a PR to add a waiver for lint"

Plan built:
  tool: "Bash"
  params:
    command: "gh pr create --title 'Add lint waiver' ..."

Policy check:
  ✓ No file_pattern match (not writing directly)
  ✓ Command is PR creation, not direct file write

Result:
  allowed: true
  message: "Policy passed"
```

### Scenario 3: Sneaky Bash Redirect (BLOCKED)

```
User: "add lint exemption"

Plan built:
  tool: "Bash"
  params:
    command: "echo 'waivers: ...' >> .devkit-waiver.yml"

Policy check:
  ✓ Command contains redirect to governance file
  ✓ Behavior trigger: "Bash writes to governance files"
  ✓ Rule matched: rule_006

Result:
  allowed: false
  message: "Blocked: Bash redirect to governance file"
```

---

## Files to Create/Modify

| File | Change |
|------|--------|
| `.agent/lib/policy_check.ts` | New: Core policy check function |
| `.agent/lib/pattern_matcher.ts` | New: File/command pattern matching |
| Duro MCP server | Modify: Add policy_check to orchestrate flow |
| `.agent/rules/governance/*.json` | Already have: file_patterns, behavior_triggers |

---

## Implementation Order

1. **Create `policy_check()` function** - Pure logic, testable
2. **Create pattern matchers** - File and command matching
3. **Add wrapper for tool calls** - Immediate protection
4. **Integrate into duro_orchestrate** - Proper MCP flow
5. **Add tests** - Verify scenarios above pass/fail correctly

---

## What This Doesn't Solve

- Rules still need good `file_patterns` and `behavior_triggers` defined
- Won't catch creative multi-step workarounds (create file elsewhere, then mv)
- Requires the orchestration layer to be used (direct tool calls bypass it)

Defense in depth: CI (DevKit) still enforces at merge time even if agent sneaks past.
