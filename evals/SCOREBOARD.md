# Duro Scoreboard

**Last updated:** 2026-02-10
**Period:** Week of 2026-02-10

---

## Overall Health

| Metric | Value | Trend |
|--------|-------|-------|
| Eval pass rate | 75% (3/4) | - |
| Rules in library | 4 | New |
| Skills in library | 2 | New |
| Proposals pending | 0 | - |
| Proposals in trial | 0 | - |

---

## Eval Performance

| Eval | Pass Rate | Avg Time | Avg Tool Calls | Trend |
|------|-----------|----------|----------------|-------|
| Generate Episode Audio | 100% | 105s | 6 | - |
| Generate Episode Script | 100% | 180s | - | - |
| Generate Character Image | 50% | 150s | - | ⚠️ |
| Research Question | - | - | - | No data |
| Code Skill Creation | 100% | 300s | - | - |

---

## Top 3 Recurring Failure Tags

1. **face_distortion** - 2 occurrences
   - Rule created: rule_001
   - Status: Addressed

2. **child_voice_quality** - 1 occurrence
   - Rule created: rule_002 (known limitation)
   - Status: Accepted limitation

3. *(none)* - System is new

---

## Skill Usage

| Skill | Usage Count | Success Rate | Last Used |
|-------|-------------|--------------|-----------|
| generate_tts | 12 | 92% | 2026-02-10 |
| generate_episode_audio | 2 | 100% | 2026-02-10 |

---

## Rule Effectiveness

| Rule | Times Applied | Success Rate | Notes |
|------|---------------|--------------|-------|
| rule_001 (Face Distortion) | 0 | - | Just created |
| rule_002 (TTS Selection) | 2 | 100% | Working well |
| rule_003 (Tool Selection) | 0 | - | Just created |
| rule_004 (Stop Conditions) | 0 | - | Just created |

---

## Weekly Comparison

| Week | Pass Rate | Rules | Skills | Key Event |
|------|-----------|-------|--------|-----------|
| 2026-02-10 | 75% | 4 | 2 | System initialized |

---

## Action Items

1. [ ] Run image generation eval with rule_001 applied
2. [ ] Track tool_selection rule effectiveness
3. [ ] Add more general-purpose skills

---

*Auto-generated from eval results. Update weekly.*
