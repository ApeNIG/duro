# Duro Verification Intelligence

> Trust layer for AI-generated code

## Overview

The Verification Intelligence stack validates AI outputs through:
1. **design_to_code_verifier** - Compare Pencil designs to code, detect drift
2. **code_quality_verifier** - Check code against 12 high-accuracy rules
3. **skill_composer** - Chain verifiers into CI/CD workflows

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    VERIFICATION STACK                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐     ┌──────────────────┐                  │
│  │ design_to_code   │     │ code_quality     │                  │
│  │ _verifier v2.0   │     │ _verifier v1.0   │                  │
│  │                  │     │                  │                  │
│  │ • Tailwind ext.  │     │ • 4 TS rules     │                  │
│  │ • CSS var map    │     │ • 4 React rules  │                  │
│  │ • Drift detect   │     │ • 4 Security     │                  │
│  └────────┬─────────┘     └────────┬─────────┘                  │
│           │                        │                             │
│           └───────────┬────────────┘                             │
│                       ▼                                          │
│             ┌──────────────────┐                                 │
│             │  skill_composer  │                                 │
│             │  v1.0 MVP        │                                 │
│             │                  │                                 │
│             │  • Sequential    │                                 │
│             │  • Context pass  │                                 │
│             │  • Stop/continue │                                 │
│             └──────────────────┘                                 │
│                       │                                          │
│                       ▼                                          │
│             ┌──────────────────┐                                 │
│             │  devkit.config   │                                 │
│             │  (CI/CD hook)    │                                 │
│             └──────────────────┘                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Run Design Verification

```python
from skills.design.design_to_code_verifier import run

result = run(
    args={
        "pen_file": "designs/app.pen",
        "code_dir": "src/components",
        "output_format": "devkit"
    },
    tools={"pencil_batch_get": ..., "read_file": ..., "glob_files": ...},
    context={}
)
```

### Run Code Quality Check

```python
from skills.verification.code_quality_verifier import run

result = run(
    args={
        "code_dir": "src",
        "output_format": "devkit"
    },
    tools={"read_file": ..., "glob_files": ...},
    context={}
)
```

### Run Full Verification Workflow

```python
from skills.meta.skill_composer import run

result = run(
    args={
        "workflow": {
            "name": "full_verification",
            "steps": [
                {"name": "design", "skill": "design_to_code_verifier", "args": {...}},
                {"name": "quality", "skill": "code_quality_verifier", "args": {...}}
            ],
            "on_failure": "continue"
        },
        "initial_context": {"code_dir": "src"}
    },
    tools={"skill_registry": ..., "skill_runner": ...},
    context={}
)
```

## Code Quality Rules

### TypeScript (4 rules)

| Rule ID | Name | Severity | Confidence |
|---------|------|----------|------------|
| `ts_no_any` | No any type | warn | 0.95 |
| `ts_no_as_any` | No as any assertion | error | 0.98 |
| `ts_no_as_unknown_as` | No double assertion | error | 0.99 |
| `ts_no_non_null_assertion` | Avoid non-null ! | info | 0.70 |

### React (4 rules)

| Rule ID | Name | Severity | Confidence |
|---------|------|----------|------------|
| `react_no_conditional_hooks` | No conditional hooks | error | 0.85 |
| `react_effect_missing_deps` | Effect may have stale deps | warn | 0.60 |
| `react_no_inline_component` | No inline components | warn | 0.70 |
| `react_map_missing_key` | Map needs key prop | warn | 0.75 |

### Security (4 rules)

| Rule ID | Name | Severity | Confidence |
|---------|------|----------|------------|
| `sec_no_dangerous_html` | No dangerouslySetInnerHTML | error | 0.99 |
| `sec_no_eval` | No eval() | error | 0.99 |
| `sec_no_inner_html` | No innerHTML assignment | error | 0.95 |
| `sec_no_hardcoded_secrets` | No hardcoded secrets | error | 0.80 |

## Suppressions

### File-level: `.duroignore`

```
# Suppress all checks on test files
**/*.test.tsx

# Suppress specific rule globally
ts_no_any

# Suppress rule for specific path
sec_no_dangerous_html:src/legacy/**
```

### Inline suppression

```tsx
// duro-ignore: ts_no_any
const legacyData: any = fetchLegacy();
```

## Devkit Integration

Add to your project's `devkit.config.json`:

```json
{
  "governance": {
    "blocking": ["typecheck", "lint", "duro-security"],
    "advisory": ["duro-design", "duro-quality"]
  },
  "quality": {
    "visualQA": {
      "ai": {
        "provider": "duro",
        "skill": "design_to_code_verifier"
      }
    },
    "codeQA": {
      "ai": {
        "provider": "duro",
        "skill": "code_quality_verifier"
      }
    }
  }
}
```

## Output Formats

### Standard Format

```json
{
  "success": true,
  "findings": [...],
  "by_severity": {"warn": 2, "error": 0},
  "files_checked": 15
}
```

### Devkit Format

```json
{
  "run_id": "run_abc123",
  "timestamp": "2026-02-15T06:00:00Z",
  "repo": "src",
  "success": true,
  "checks": [{"name": "...", "success": true, "duration_ms": 150}],
  "findings": [...],
  "metrics": {...}
}
```

## Core Infrastructure

### lib/skill_runner.py

The spine for all skill execution:
- Path validation (no traversal attacks)
- Timeout enforcement
- Standardized `SkillResult` output
- Suppression management

### tests/mock_mcp.py

Test harness for skills:
- Fake `read_file`, `glob_files`, `grep`
- Fixture-based testing
- Call tracking for assertions

## Key Files

```
~/.agent/
├── lib/
│   └── skill_runner.py      # Execution spine
├── skills/
│   ├── design/
│   │   └── design_to_code_verifier.py  # v2.0
│   ├── verification/
│   │   └── code_quality_verifier.py    # v1.0
│   └── meta/
│       └── skill_composer.py           # v1.0 MVP
├── tests/
│   ├── mock_mcp.py          # Test harness
│   └── test_skill_runner.py
└── VERIFICATION.md          # This file
```
