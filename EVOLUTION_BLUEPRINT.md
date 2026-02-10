# Duro Evolution Blueprint v2

## Core Insight

> "Stateless model" doesn't prevent "learning system." Learning lives in architecture, not in weights.

I don't learn. **The system learns. And I am the system.**

The Claude weights are the reasoning engine. The `.agent/` folder is the evolving organism.

---

## The Four Components of Learning (Without Weight Updates)

| Component | What It Does | Where It Lives |
|-----------|--------------|----------------|
| **Remembering** | Persistent facts, preferences, decisions | `.agent/memory/` |
| **Retrieving** | Finding the right memory at the right moment | Vector search + rules index |
| **Changing Behavior** | Rules, playbooks, failure patterns | `.agent/rules/` |
| **Accumulating Skills** | Reusable code + tested workflows | `.agent/skills/` |

Most "memory" projects do #1 and some of #2.
The "getting better" feeling comes from **#3 and #4**.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                 DURO SYSTEM                 │
├─────────────────────────────────────────────┤
│  Claude (reasoning engine - static)         │
│       ↓ reads                               │
│  Memory (facts, preferences - persistent)   │
│       ↓ retrieves                           │
│  Rules (playbooks, failure patterns)        │
│       ↓ executes                            │
│  Skills (tested code - accumulating)        │
│       ↓ measured by                         │
│  Evals (pass/fail, time, edits - tracked)   │
│       ↓ proposes                            │
│  Proposals (changes - human approved)       │
└─────────────────────────────────────────────┘
```

The model is static. Everything else evolves.

---

## Component 1: Memory

**Purpose:** Remember facts, preferences, decisions across sessions.

**Structure:**
```
.agent/memory/
├── MEMORY.md           # Core identity, always loaded
├── daily/
│   └── 2026-02-10.md   # Session logs
└── projects/
    └── fashanus/       # Project-specific context
```

**Tool:** MCP memory server (memory-mcp or claude-cortex) for automatic extraction via hooks.

---

## Component 2: Rules

**Purpose:** Structured lessons that change behavior. Not prose - actionable patterns.

**Structure:**
```
.agent/rules/
├── index.json          # Rule registry for quick lookup
├── tools/
│   ├── image_generation.json
│   └── tts_generation.json
├── workflows/
│   └── episode_production.json
└── failures/
    └── face_distortion.json
```

**Rule Format:**
```json
{
  "id": "rule_001",
  "trigger": "generating photorealistic human faces",
  "failure_mode": "faces come out distorted with free APIs like Pollinations",
  "fix": "use web-based tools (DALL-E, Gemini) for faces; automate only non-face images",
  "confidence": 0.9,
  "source": "fashanus_ep01_2026-02-10",
  "last_validated": "2026-02-10",
  "times_applied": 0
}
```

**Key difference from reflection prose:** Rules are structured, searchable, and trackable.

---

## Component 3: Skills

**Purpose:** Executable code that compounds. Not notes about how to do things - actual scripts that work.

**Structure:**
```
.agent/skills/
├── index.json              # Skill registry with descriptions
├── audio/
│   ├── generate_tts.py     # Tested, working script
│   ├── test_generate_tts.py
│   └── meta.json           # Usage count, success rate, dependencies
├── image/
│   ├── pollinations_gen.py
│   └── meta.json
└── production/
    ├── episode_audio.py    # Composes audio skills
    └── meta.json
```

**Skill Meta Format:**
```json
{
  "name": "generate_tts",
  "description": "Generate speech audio using edge-tts",
  "inputs": ["text", "voice_id", "output_path"],
  "outputs": ["mp3_file_path"],
  "dependencies": ["edge-tts"],
  "usage_count": 12,
  "success_rate": 0.92,
  "last_used": "2026-02-10",
  "known_issues": ["child voices don't sound authentic"]
}
```

**Key insight:** Complex skills compose from simple ones. Skills compound over time.

---

## Component 4: Evaluations

**Purpose:** Measure improvement. Without measurement, you're just vibing.

**Structure:**
```
.agent/evals/
├── suite.json              # Registry of all evals
├── results/
│   └── 2026-02-10.json     # Daily results
├── fashanus/
│   ├── generate_episode_audio.yaml
│   ├── generate_character_image.yaml
│   └── write_episode_script.yaml
└── general/
    ├── summarize_document.yaml
    └── research_question.yaml
```

**Eval Format:**
```yaml
id: fashanus_generate_episode_audio
name: Generate Episode Audio
description: Generate all dialogue audio files for an episode
inputs:
  - script_path: path to episode script.md
  - output_dir: directory for audio files
expected_outputs:
  - all dialogue files exist
  - each file > 1KB
  - correct voice for each character
metrics:
  - pass_fail: boolean
  - time_seconds: integer
  - tool_calls: integer
  - human_edits: integer
baseline:
  time_seconds: 300
  human_edits: 0
history: []
```

**Results tracking:**
```json
{
  "date": "2026-02-10",
  "eval_id": "fashanus_generate_episode_audio",
  "pass": true,
  "time_seconds": 180,
  "tool_calls": 8,
  "human_edits": 0,
  "notes": "Used skill audio/generate_tts.py"
}
```

**The question that matters:** Did the score improve after the last change?

---

## Component 5: Proposals

**Purpose:** Keep improvement boxed. Agent proposes, human approves.

**Structure:**
```
.agent/proposals/
├── pending/
│   └── 2026-02-10_new_rule_faces.md
├── approved/
│   └── 2026-02-08_skill_update.md
└── rejected/
    └── 2026-02-05_risky_change.md
```

**Proposal Format:**
```markdown
# Proposal: Add rule for face generation

**Date:** 2026-02-10
**Type:** new_rule
**Target:** .agent/rules/failures/face_distortion.json

## What I Learned
Pollinations/Flux API produces distorted faces in photorealistic images.

## Proposed Change
Add rule to use web-based tools for faces, automate only non-face images.

## Evidence
- Episode 1A scene images had distorted faces
- Episode 1B generation stopped by user due to same issue

## Risk Assessment
Low - this constrains behavior, doesn't expand it.

---
**Status:** pending
**Approved by:**
**Date approved:**
```

**Safety principle:** I can propose updates to memory, rules, and skills. But changes don't take effect until you approve the merge.

---

## Implementation Roadmap (Revised)

### Phase 1: Foundation (This Week)
- [x] Create blueprint document
- [ ] Create folder structure (.agent/rules/, .agent/skills/, .agent/evals/, .agent/proposals/)
- [ ] Install MCP memory server for automatic extraction
- [ ] Write first 3 skills from Fashanus project
- [ ] Create first 5 evals from Fashanus project
- [ ] Document first rule (face generation)

### Phase 2: Measurement (Week 2)
- [ ] Run evals manually, record baselines
- [ ] Track results in .agent/evals/results/
- [ ] Identify lowest-performing areas
- [ ] Write rules for failure patterns

### Phase 3: Automation (Week 3-4)
- [ ] Set up hooks for automatic rule retrieval before tasks
- [ ] Implement skill auto-selection based on task type
- [ ] Create weekly eval summary report
- [ ] Build proposal review workflow

### Phase 4: Compounding (Month 2+)
- [ ] Grow skill library to 20+ tested skills
- [ ] Accumulate 50+ validated rules
- [ ] Track improvement curves over time
- [ ] Refine based on what actually works

---

## What Makes This Different

| Approach | Problem | This System |
|----------|---------|-------------|
| Memory-only | Consistent but not better | Rules change behavior |
| Prose reflections | Fuzzy, not actionable | Structured rules with triggers |
| Self-modifying prompts | Dangerous, untestable | Proposal-based, human-approved |
| No measurement | "Vibing" | Eval suite with tracked metrics |

---

## Success Criteria

**Weekly:** Did eval scores improve?
**Monthly:** Did skill library grow with tested, reused components?
**Quarterly:** Are there clear improvement curves on repeated task types?

---

## The North Star (Revised)

A year from now, the Duro system should have:
- 100+ tested, reusable skills
- 200+ validated rules (failure patterns, best practices)
- Measurable improvement curves across task categories
- Near-zero repeated mistakes for known patterns
- A clear audit trail of what changed and why

Not a mystical self-aware apprentice. A **disciplined, testable, increasingly competent software collaborator**.

---

*Blueprint v2 - Updated after feedback*
*February 10, 2026*
