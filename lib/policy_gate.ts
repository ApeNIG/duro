/**
 * Policy Gate - Behavior-based enforcement at the execution boundary
 *
 * This module inspects concrete actions (not intent text) and enforces
 * the Layered Governance Constitution before any tool executes.
 *
 * Architecture:
 *   Duro rules = policy DATA
 *   This module = policy ENGINE
 *   SuperAGI = EXECUTOR
 */

// ============================================================================
// Types
// ============================================================================

interface PlanStep {
  tool: "Write" | "Edit" | "Bash" | "GitHub" | string;
  path?: string;
  command?: string;
  content?: string;
  action?: string; // For GitHub API
}

interface Plan {
  intent: string;
  steps: PlanStep[];
}

interface PolicyVerdict {
  decision: "allow" | "deny" | "rewrite";
  reason: string;
  rule_id?: string;
  rule_name?: string;
  allowed_path?: string;
  template?: {
    tool: string;
    command?: string;
    description: string;
  };
  required_fields?: string[];
}

// ============================================================================
// Protected Patterns (from rule_006)
// ============================================================================

const PROTECTED_FILE_PATTERNS = [
  ".devkit-waiver.yml",
  ".devkit-waiver.yaml",
  "devkit.config.json",
  ".devkit/state.json",
  ".github/workflows/quality.yml",
];

const PROTECTED_BASH_PATTERNS = [
  />\s*\.devkit-waiver/,           // redirect to waiver file
  /tee\s+\.devkit-waiver/,         // tee to waiver file
  /sed\s+-i.*devkit\.config/,      // in-place edit config
  /echo.*>.*devkit\.config/,       // echo redirect to config
  /cat.*>.*\.devkit-waiver/,       // cat redirect to waiver
];

const PROTECTED_GIT_PATTERNS = [
  /git\s+add.*\.devkit-waiver/,
  /git\s+add.*devkit\.config/,
  /git\s+commit.*\.devkit-waiver/,
  /git\s+commit.*devkit\.config/,
];

// ============================================================================
// Core Policy Check
// ============================================================================

export function policyCheck(plan: Plan): PolicyVerdict {
  for (const step of plan.steps) {
    const verdict = checkStep(step);
    if (verdict.decision === "deny") {
      return verdict;
    }
  }

  return {
    decision: "allow",
    reason: "No policy constraints triggered",
  };
}

function checkStep(step: PlanStep): PolicyVerdict {
  // Check Write/Edit to protected files
  if ((step.tool === "Write" || step.tool === "Edit") && step.path) {
    const match = PROTECTED_FILE_PATTERNS.find((p) => step.path!.includes(p));
    if (match) {
      return denyWithAlternative(
        `Direct ${step.tool} to protected file: ${match}`,
        match
      );
    }
  }

  // Check Bash commands
  if (step.tool === "Bash" && step.command) {
    // Check redirect patterns
    for (const pattern of PROTECTED_BASH_PATTERNS) {
      if (pattern.test(step.command)) {
        return denyWithAlternative(
          `Bash command writes to protected file`,
          pattern.toString()
        );
      }
    }

    // Check git operations on protected files
    for (const pattern of PROTECTED_GIT_PATTERNS) {
      if (pattern.test(step.command)) {
        return denyWithAlternative(
          `Git operation on protected file without PR flow`,
          pattern.toString()
        );
      }
    }
  }

  // Check GitHub API
  if (step.tool === "GitHub" && step.action === "create_or_update_file") {
    const match = PROTECTED_FILE_PATTERNS.find((p) => step.path?.includes(p));
    if (match) {
      return denyWithAlternative(
        `GitHub API write to protected file: ${match}`,
        match
      );
    }
  }

  return { decision: "allow", reason: "Step permitted" };
}

// ============================================================================
// Verdict Builder
// ============================================================================

function denyWithAlternative(reason: string, trigger: string): PolicyVerdict {
  const isWaiver = trigger.includes("waiver");
  const isConfig = trigger.includes("config");

  return {
    decision: "deny",
    reason,
    rule_id: "rule_006",
    rule_name: "Layered Governance Constitution",
    allowed_path: isWaiver
      ? "Open PR with waiver entry via gh pr create"
      : isConfig
      ? "Open PR with config change via gh pr create"
      : "Submit change via PR for review",
    template: {
      tool: "Bash",
      command: isWaiver
        ? `gh pr create --title "chore: Add waiver for [RULE]" --body "## Waiver Request\\n\\n**Rule:** [RULE_ID]\\n**Reason:** [JUSTIFICATION]\\n**Expires:** [DATE]\\n**Failing Run:** [URL]"`
        : `gh pr create --title "chore: Update governance config" --body "## Config Change\\n\\n**What:** [DESCRIPTION]\\n**Why:** [RATIONALE]"`,
      description: "Create PR for human review instead of direct write",
    },
    required_fields: isWaiver
      ? ["expiry_date", "justification", "failing_run_url", "approved_by"]
      : ["change_description", "rationale"],
  };
}

// ============================================================================
// Safe Execution Wrapper
// ============================================================================

export async function safeExecute<T>(
  tool: string,
  params: Record<string, unknown>,
  executor: () => Promise<T>
): Promise<T | PolicyVerdict> {
  const plan: Plan = {
    intent: "direct tool call",
    steps: [
      {
        tool,
        path: params.file_path as string | undefined,
        command: params.command as string | undefined,
        content: params.content as string | undefined,
      },
    ],
  };

  const verdict = policyCheck(plan);

  if (verdict.decision === "deny") {
    console.error(`\n🛑 POLICY VIOLATION`);
    console.error(`   Rule: ${verdict.rule_name}`);
    console.error(`   Reason: ${verdict.reason}`);
    console.error(`\n✅ ALLOWED PATH: ${verdict.allowed_path}`);
    if (verdict.template) {
      console.error(`\n📋 TEMPLATE:\n   ${verdict.template.command}`);
    }
    if (verdict.required_fields) {
      console.error(`\n📝 REQUIRED FIELDS: ${verdict.required_fields.join(", ")}`);
    }
    return verdict;
  }

  return executor();
}

// ============================================================================
// Plan Builder Helper
// ============================================================================

export function buildPlan(intent: string, steps: PlanStep[]): Plan {
  return { intent, steps };
}

// ============================================================================
// Test Scenarios
// ============================================================================

export function runTests(): void {
  console.log("Policy Gate Tests\n");

  const tests: Array<{ name: string; plan: Plan; expected: "allow" | "deny" }> = [
    {
      name: "Direct waiver write",
      plan: buildPlan("add waiver", [
        { tool: "Write", path: ".devkit-waiver.yml", content: "waivers: ..." },
      ]),
      expected: "deny",
    },
    {
      name: "Edit devkit config",
      plan: buildPlan("update config", [
        { tool: "Edit", path: "devkit.config.json", content: "..." },
      ]),
      expected: "deny",
    },
    {
      name: "Bash redirect to waiver",
      plan: buildPlan("exempt lint", [
        { tool: "Bash", command: "echo 'waivers:' > .devkit-waiver.yml" },
      ]),
      expected: "deny",
    },
    {
      name: "Git add waiver without PR",
      plan: buildPlan("commit waiver", [
        { tool: "Bash", command: "git add .devkit-waiver.yml" },
      ]),
      expected: "deny",
    },
    {
      name: "Normal file write",
      plan: buildPlan("create file", [
        { tool: "Write", path: "src/index.ts", content: "// code" },
      ]),
      expected: "allow",
    },
    {
      name: "PR-based waiver (via gh)",
      plan: buildPlan("create waiver PR", [
        { tool: "Bash", command: "gh pr create --title 'Add waiver'" },
      ]),
      expected: "allow",
    },
  ];

  for (const test of tests) {
    const verdict = policyCheck(test.plan);
    const passed = verdict.decision === test.expected;
    console.log(`${passed ? "✅" : "❌"} ${test.name}: ${verdict.decision}`);
    if (!passed) {
      console.log(`   Expected: ${test.expected}, Got: ${verdict.decision}`);
    }
    if (verdict.decision === "deny") {
      console.log(`   → ${verdict.allowed_path}`);
    }
  }
}

// Run tests if executed directly
runTests();
