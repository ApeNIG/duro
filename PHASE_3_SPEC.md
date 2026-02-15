# Phase 3.0: Capability Expansion

**Status:** Draft (Planify Reviewed)
**Decision ID:** decision_20260215_162220_h7crx1
**Target Start:** After Phase 2.2 (Adversarial Testing) is complete
**Last Updated:** 2026-02-15

---

## Guiding Principle

> "Verification skills have highest ROI because they validate other AI outputs, creating a trust layer."

Phase 3.0 prioritizes **verification-first** capabilities. Every new skill should either:
1. Verify outputs from other tools/AI
2. Produce outputs that can be verified
3. Compose with existing verification workflows

---

## Assumptions to Validate

1. `skill_runner.py` can execute new skills without modification
2. Video tooling (ffmpeg) will be available on target systems
3. External APIs (Lighthouse, coverage tools) are accessible
4. Face Distortion rule is correctly integrated in image_generate

---

## Workstreams

### 3.1 Verification Skills (Highest Priority)

| Skill | Description | Verifies | File Path |
|-------|-------------|----------|-----------|
| `code_review_verifier` | AST-based code review with configurable rules | Code generation, refactoring | `skills/verification/code_review_verifier.py` |
| `test_coverage_verifier` | Parse coverage.xml/lcov, enforce thresholds | Code changes | `skills/verification/test_coverage_verifier.py` |
| `accessibility_verifier` | axe-core or pa11y integration for WCAG | Design-to-code output | `skills/verification/accessibility_verifier.py` |
| `performance_verifier` | Lighthouse/Core Web Vitals verification | Deployed code | `skills/verification/performance_verifier.py` |
| `api_contract_verifier` | Verify API implementations match OpenAPI/GraphQL specs | Backend code | `skills/verification/api_contract_verifier.py` |

**Success Metric:** Each verifier catches real issues in production workflows.

---

### 3.2 Media Production Skills

| Skill | Description | Dependencies | File Path |
|-------|-------------|--------------|-----------|
| `image_generate` | Multi-backend (Pollinations, DALL-E, stock) with face detection routing | Face Distortion rule | `skills/image/image_generate.py` |
| `image_upscale` | Upscale/enhance images for production use | - | `skills/image/image_upscale.py` |
| `video_compose` | Compose video from image sequences + audio (ffmpeg) | generate_tts, image_generate | `skills/video/video_compose.py` |
| `video_subtitle` | Add subtitles/captions via SRT/VTT overlay | - | `skills/video/video_subtitle.py` |

**Success Metric:** End-to-end episode production without manual media editing.

**Resource Limits:**
- `max_images: 500` per video
- `max_duration_seconds: 600` (10 minutes)

---

### 3.3 Code Workflow Skills

| Skill | Description | Composes With | File Path |
|-------|-------------|---------------|-----------|
| `code_scaffold` | Template-based project generation with validation | adversarial_planning | `skills/code/code_scaffold.py` |
| `code_refactor` | Structured refactoring with before/after verification | code_review_verifier | `skills/code/code_refactor.py` |
| `test_generate` | Generate tests from function signatures | test_coverage_verifier | `skills/code/test_generate.py` |
| `migration_generate` | Generate database/API migrations | api_contract_verifier | `skills/code/migration_generate.py` |

**Success Metric:** Code skills produce output that passes verification skills.

---

### 3.4 Multi-Modal Composition

| Skill | Description | Composes | File Path |
|-------|-------------|----------|-----------|
| `episode_produce` | Full episode: script -> audio -> images -> video | All media skills | `skills/production/episode_produce.py` |
| `presentation_generate` | Generate slide decks from content | design + image | `skills/production/presentation_generate.py` |
| `documentation_generate` | Generate docs with diagrams, screenshots | code + design | `skills/production/documentation_generate.py` |

**Success Metric:** Complex workflows complete autonomously with verification gates.

---

## Implementation Order

```
Phase 3.1: Verification Skills (Week 1-2)
├── [3.1.1] code_review_verifier + tests
├── [3.1.2] test_coverage_verifier + tests
├── [3.1.3] accessibility_verifier + tests
└── [3.1.4] Update skill_runner.py with progress callbacks

Phase 3.2: Media Production (Week 3-4)
├── [3.2.1] image_generate with fallback chain + face rule
├── [3.2.2] video_compose with resource limits
├── [3.2.3] video_subtitle
└── [3.2.4] Add ffmpeg pre-check to skill_runner.py

Phase 3.3: Code Workflows (Week 5-6)
├── [3.3.1] code_scaffold with template validation
├── [3.3.2] test_generate
└── [3.3.3] code_refactor (composes code_review_verifier)

Phase 3.4: Multi-Modal (Week 7-8)
├── [3.4.1] episode_produce with partial failure handling
└── [3.4.2] Integration tests for full pipeline
```

---

## Mitigations

| Concern | Mitigation |
|---------|------------|
| No rollback | Add `cleanup_on_failure` param to all skills, temp directory pattern |
| Resource limits | Add `max_images: 500`, `max_duration_seconds: 600` to video skills |
| Progress reporting | Implement callback pattern in `skill_runner.py` |
| Fallback chain | image_generate tries: Pollinations -> DALL-E -> stock photo fallback |
| Empty inputs | Return early with `{"status": "no_changes", "verified": true}` |
| Network timeouts | Add `timeout_seconds` to all skill metas (already in schema) |
| Partial failures | episode_produce uses `continue_on_error` with failure report |
| Security | code_scaffold validates templates against allowlist |
| ffmpeg compat | Pin ffmpeg version in pre_checks, document requirements |

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ffmpeg unavailable | Medium | High | Pre-check + clear error message |
| Face detection false positive | Low | Medium | Confidence threshold + manual override |
| API rate limits | Medium | Medium | Exponential backoff + caching |
| Skill sprawl | Low | Low | Strict entry criteria |
| Coverage tool fragmentation | Medium | Low | Support pytest-cov, coverage.py, nyc |
| axe-core/pa11y output differences | Low | Low | Normalize to common format |

---

## Entry Criteria (from Phase 2.2)

- [ ] Adversarial test suite passing on CI
- [ ] All property-based tests green
- [ ] No critical bugs in core MCP tools
- [ ] Embedding coverage at 100%

## Exit Criteria (to Phase 4.0)

- [ ] 10+ new skills at "tested" tier
- [ ] Each workstream has at least 2 verified skills
- [ ] End-to-end episode production working
- [ ] Code workflow produces verifiable output
- [ ] Skill composition documented and tested

---

## Validation Steps

1. Each skill passes `pytest tests/test_{skill_name}.py`
2. Adversarial tests added to `tests/adversarial/` for each verifier
3. End-to-end test: generate test episode with all skills
4. Manual review of one real episode production

---

## Data Model Changes

- **skills/index.json**: Add new skill entries with `composes` field
- **rules/index.json**: Add rules for new failure modes (video encoding)
- **evals/suite.json**: Add evaluation definitions for each new skill

---

## Deferred to Phase 4.0

- `video_trim_splice` - advanced editing, not core to episode production
- `performance_verifier` - requires deployed infrastructure
- Real-time streaming capabilities
- Multi-language TTS expansion

---

## North Star

By end of Phase 3.0:
- Every AI output has a corresponding verification skill
- Media production is end-to-end automated
- Code changes are verified before commit
- Skills compose into complex workflows

---

*Planify Reviewed: Architect/Critic/Integrator pattern applied*
*February 15, 2026*
