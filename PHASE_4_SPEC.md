# Phase 4.0: Compounding & Intelligence

**Status:** Draft
**Depends On:** Phase 3.0 Complete
**Target Start:** Immediately after Phase 3.4
**Last Updated:** 2026-02-15

---

## Guiding Principle

> "Learning lives in architecture, not in weights. The system learns, and I am the system."

Phase 4.0 shifts from **capability building** (Phase 3) to **intelligence compounding**. We have 20+ skills—now we need:
1. Smart retrieval that surfaces the right skill/rule at the right moment
2. Measurement that proves improvement over time
3. Real-world validation with end-to-end production

---

## North Star Metrics

| Metric | Current | Phase 4 Target |
|--------|---------|----------------|
| Tested Skills | 20+ | 30+ |
| Validated Rules | 7 | 50+ |
| Eval Suite Coverage | 0% | 80%+ |
| End-to-end Productions | 0 | 3+ |
| Context Load Time | N/A | <500ms |

---

## Pre-Phase Audit (Required)

Before starting Phase 4.1, verify existing infrastructure:

| Component | Expected Path | Status |
|-----------|---------------|--------|
| `lib/` directory | `.agent/lib/` | [ ] Exists |
| Constitution loader stub | `lib/constitution_loader.py` | [ ] Exists or create |
| Skill loader stub | `lib/skill_loader.py` | [ ] Exists or create |
| Context assembler stub | `lib/context_assembler.py` | [ ] Exists or create |
| Rules index | `rules/index.json` | [ ] Exists with 7+ rules |
| Skills index | `skills/index.json` | [ ] Exists with 20+ skills |

**Audit Actions:**
1. Run `ls -la .agent/lib/` to verify directory structure
2. Check each file exists or create stubs with `pass` implementations
3. Verify rules/index.json has current rule count
4. Verify skills/index.json has all Phase 3 skills

**Entry Gate:** All audit items checked before proceeding to 4.1.

---

## Workstreams

### 4.1 Cartridge Memory System (Foundation)

Implement the context management layer that intelligently loads skills and project rules.

| Component | Description | File Path |
|-----------|-------------|-----------|
| `constitution_loader` | Load/render project constitutions | `lib/constitution_loader.py` |
| `skill_loader` | Load skills with token-aware rendering | `lib/skill_loader.py` |
| `context_assembler` | Assemble optimal context for tasks | `lib/context_assembler.py` |
| `promotion_compactor` | Graduate decisions → rules/patterns | `lib/promotion_compactor.py` |

**MCP Tools to Add:**
- `duro_load_constitution(project_id, mode)` - Load project constitution
- `duro_assemble_context(task, project_id, budget)` - Smart context assembly
- `duro_promotion_report()` - Show promotion candidates

**Token Budgets:**
- Minimal: ~200 tokens (north star + hard laws)
- Compact: ~800 tokens (laws + constraints + top patterns)
- Full: ~2000 tokens (everything)

**Success Metric:** Context load <500ms, token usage within budget ±10%.

---

### 4.2 Eval Suite (Measurement)

Build the measurement system that proves improvement over time.

| Component | Description | File Path |
|-----------|-------------|-----------|
| Eval definitions | YAML-based eval specifications | `evals/definitions/` |
| Eval runner | Execute evals and record results | `evals/runner.py` |
| Results tracker | Track scores over time | `evals/results/` |
| Scoreboard | Visual improvement dashboard | `evals/SCOREBOARD.md` |

**Eval Categories:**
- **Skill Evals:** Test each skill in isolation
- **Workflow Evals:** Test skill composition
- **Production Evals:** End-to-end task completion

**Flaky Skill Handling:**
Skills with external dependencies (APIs, network) can be marked as flaky:
```yaml
flaky: true           # Mark skill as potentially flaky
mock_mode: true       # Run with mocked external calls
retry_count: 3        # Retry on transient failures
```

Flaky evals are tracked separately and don't fail CI, but trends are monitored.

**Eval Format:**
```yaml
id: eval_episode_produce
name: Full Episode Production
description: Produce video from script using all skills
inputs:
  script_path: test_fixtures/sample_script.md
  output_dir: /tmp/eval_output/
expected_outputs:
  - video_file_exists: true
  - audio_files_count: ">0"
  - image_files_count: ">0"
metrics:
  - pass_fail: boolean
  - duration_seconds: integer
  - errors_count: integer
baseline:
  duration_seconds: 300
  errors_count: 0
```

**Success Metric:** Eval scores improve week-over-week.

---

### 4.3 Rules Expansion (Intelligence)

Scale from 7 rules to 50+ validated rules with auto-retrieval.

| Component | Description | File Path |
|-----------|-------------|-----------|
| Rule templates | Templates for common rule types | `rules/templates/` |
| Auto-extractor | Extract rules from failures/successes | `skills/meta/rule_extractor.py` |
| Rule retriever | Match rules to current task | `lib/rule_retriever.py` |
| Rule validator | Validate rules still apply | `lib/rule_validator.py` |

**Rule Categories to Build:**
- **Tool Rules:** When to use which tool (10+ rules)
- **Workflow Rules:** Step ordering, checkpoints (10+ rules)
- **Failure Rules:** Known failure patterns (15+ rules)
- **Quality Rules:** Output quality standards (10+ rules)
- **Safety Rules:** Guardrails and constraints (5+ rules)

**MCP Tools to Add:**
- `duro_check_rules(task)` - Find applicable rules (already exists, enhance)
- `duro_extract_rule(episode_id)` - Extract rule from episode
- `duro_validate_rules()` - Check which rules are stale

**Quality Gates for Rule Promotion:**
Rules must meet quality thresholds before being added to the active ruleset:

| Gate | Threshold | Description |
|------|-----------|-------------|
| Confidence | ≥0.7 | Rule must have confidence score of 0.7+ |
| Validations | ≥2 | Rule must be validated in 2+ distinct episodes |
| No Conflicts | 0 | Rule must not conflict with existing rules |
| Specificity | Medium+ | Rule must not be too generic (avoid "always check errors") |

Rules below threshold remain in `rules/candidates/` until promoted.

**Success Metric:** 50+ rules, >80% retrieval precision.

---

### 4.4 Production Testing (Validation)

Validate everything works end-to-end with real productions.

| Production | Description | Skills Used |
|------------|-------------|-------------|
| Synthetic Test Episode | 2 scenes, 4 dialogue lines, controlled fixtures | episode_produce (validation) |
| Fashanus Ep01a | Full episode with all scenes | episode_produce, all media skills |
| Test Episode | Minimal test script | episode_produce (sanity check) |
| Code Project | Scaffold → tests → refactor | code_scaffold, test_generate, code_refactor |

**Synthetic Test Episode:**
Before attempting Fashanus, create a synthetic test episode with:
- 2 scenes with known image prompts
- 4 dialogue lines (2 per scene)
- Pre-generated audio/image fixtures for comparison
- Expected output duration: ~30 seconds
- Purpose: Validate pipeline without external API failures

This catches integration issues before investing in full production.

**Validation Checklist:**
- [ ] Synthetic test episode passes with mocked externals
- [ ] Synthetic test episode passes with real APIs
- [ ] episode_produce generates working video from Fashanus script
- [ ] Audio files generated for all dialogue
- [ ] Images generated for all scenes
- [ ] Subtitles embedded correctly
- [ ] code_scaffold → test_generate → code_refactor pipeline works
- [ ] All verification skills catch real issues

**Success Metric:** 3+ end-to-end productions without manual intervention.

---

### 4.5 Deferred Features (Expansion)

Complete features deferred from Phase 3.

| Feature | Description | Priority |
|---------|-------------|----------|
| `video_trim_splice` | Advanced video editing | Medium |
| `performance_verifier` | Lighthouse/Web Vitals | Low |
| Multi-language TTS | Support 5+ languages | Medium |
| `migration_generate` | Database/API migrations | Low |

**Success Metric:** At least 2 deferred features implemented.

---

## Implementation Order

```
Pre-Phase Audit (Day 1)
├── [4.0.1] Verify lib/ directory structure
├── [4.0.2] Create stubs for missing lib/ files
├── [4.0.3] Verify rules/index.json baseline
└── [4.0.4] Verify skills/index.json completeness

Phase 4.1: Cartridge Memory (Week 1-2)
├── [4.1.1] constitution_loader.py + MCP tool
├── [4.1.2] skill_loader.py with token rendering
├── [4.1.3] context_assembler.py + MCP tool
├── [4.1.4] Create 2 project constitutions (MSJ, Fashanus)
└── [4.1.5] Integration tests

Phase 4.2: Eval Suite (Week 3-4)
├── [4.2.1] Eval runner + definition schema
├── [4.2.2] Write evals for 10 core skills (with flaky flags)
├── [4.2.3] Results tracking + scoreboard
└── [4.2.4] Weekly eval automation + mock mode support

Phase 4.3: Rules Expansion (Week 5-6)
├── [4.3.1] Rule extractor skill
├── [4.3.2] Enhanced rule retriever
├── [4.3.3] Extract 20+ rules from memory/episodes
├── [4.3.4] Quality gates implementation
├── [4.3.5] Create 20+ new rules from patterns (meeting quality gates)
└── [4.3.6] Rule validation system

Phase 4.4: Production Testing (Week 7-8)
├── [4.4.1] Create synthetic test episode fixtures
├── [4.4.2] Run synthetic episode (mocked + real)
├── [4.4.3] Fashanus Ep01a full production
├── [4.4.4] Code project pipeline test
├── [4.4.5] Fix issues found in production
└── [4.4.6] Document production workflows

Phase 4.5: Deferred Features (Week 9-10)
├── [4.5.1] video_trim_splice skill
├── [4.5.2] Multi-language TTS support
└── [4.5.3] Update skills index
```

---

## Mitigations

| Concern | Mitigation |
|---------|------------|
| Context budget exceeded | Hard cap + truncation + logging |
| Stale rules applied | Rule validation with last_validated timestamps |
| Eval flakiness | Deterministic fixtures, retry logic |
| Production failures | continue_on_error mode, detailed error reports |
| Rule explosion | Quality threshold for rule creation |
| Token costs | Precompiled renderings, mode selection |

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Constitution format churn | Medium | Medium | Lock schema after v1.0 |
| Eval maintenance burden | Medium | Low | Auto-generate from skill signatures |
| Rule conflicts | Low | Medium | Priority system + conflict detection |
| Production dependency chains | Medium | High | Graceful degradation + mocks |
| Memory/context overflow | Low | High | Token counting + budget enforcement |
| Existing lib/ incomplete | High | Medium | Pre-phase audit with stub creation |
| Eval flakiness from APIs | High | Medium | Flaky flags + mock mode + retry logic |
| Rule quantity over quality | Medium | High | Quality gates (confidence ≥0.7, 2+ validations) |
| Fashanus blocks on pipeline bugs | High | High | Synthetic test episode first |

---

## Entry Criteria (from Phase 3.0)

- [x] 10+ new skills at "tested" tier
- [x] Each workstream has at least 2 verified skills
- [x] End-to-end episode production working
- [x] Code workflow produces verifiable output
- [x] Skill composition documented and tested

## Exit Criteria (to Phase 5.0)

- [ ] Cartridge Memory System operational
- [ ] Eval suite covering 80%+ of skills
- [ ] 50+ validated rules with auto-retrieval
- [ ] 3+ successful end-to-end productions
- [ ] Measurable improvement curves documented
- [ ] At least 2 deferred features complete

---

## Validation Steps

1. Constitution loads in <500ms, renders correctly at all 3 modes
2. Context assembler stays within token budget
3. Eval runner executes and records results
4. Rule retriever matches rules with >80% precision
5. Fashanus episode produces without manual intervention
6. Code workflow pipeline completes scaffold → test → refactor

---

## Data Model Changes

- **constitutions/**: Add project constitution YAML files
- **evals/definitions/**: Add eval YAML definitions
- **evals/results/**: Add daily result JSON files
- **rules/index.json**: Expand to 50+ rules
- **skills/stats.json**: Add telemetry tracking

---

## Dependencies

| External | Purpose | Risk |
|----------|---------|------|
| edge-tts | TTS generation | Low (stable) |
| ffmpeg | Video composition | Low (stable) |
| Pollinations API | Image generation | Medium (rate limits) |
| Claude API | LLM for evals | Low (core dependency) |

---

## Post-Phase 4 Vision

After Phase 4, Duro should:
- **Know what it knows:** Skills indexed, rules retrieved, context optimized
- **Prove improvement:** Eval scores tracked, baselines established
- **Produce autonomously:** End-to-end workflows without hand-holding
- **Compound learning:** Failures → rules → better behavior

This sets the foundation for Phase 5: **Autonomy & Scale**.

---

*Draft v2 - February 15, 2026 (Post-Planify Review)*
