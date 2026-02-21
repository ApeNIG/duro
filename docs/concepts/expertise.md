# Expertise

> "Skills improve through practice"

Expertise is how Duro builds domain knowledge over time through tracked outcomes.

## The Growth Model

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   Episode 1: Try → Partial Success → Learn              │
│              ↓                                          │
│   Episode 2: Apply Learning → Success → Reinforce       │
│              ↓                                          │
│   Episode 3: Pattern Emerges → Skill Improves           │
│              ↓                                          │
│   [COMPOUND EXPERTISE]                                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Episodes

Episodes track goal-level work:

```javascript
// Start an episode
duro_create_episode({
  goal: "Fix authentication bug in login flow",
  plan: [
    "Investigate error logs",
    "Reproduce the issue",
    "Find root cause",
    "Implement fix",
    "Test fix"
  ],
  tags: ["debugging", "auth"]
})
```

### Episode Structure

| Field | Description |
|-------|-------------|
| `goal` | What you're trying to achieve |
| `plan` | Steps to get there |
| `actions` | What actually happened |
| `result` | success, partial, failed |
| `links` | Facts/decisions created or used |

## Tracking Actions

Log what happens during the episode:

```javascript
duro_add_episode_action({
  episode_id: "episode_xxx",
  summary: "Found JWT validation failing on malformed tokens",
  tool: "grep"
})
```

## Closing Episodes

When work is complete:

```javascript
duro_close_episode({
  episode_id: "episode_xxx",
  result: "success",
  result_summary: "Fixed JWT validation, added test coverage",
  links: {
    decisions_used: ["decision_abc"],
    facts_created: ["fact_xyz"]
  }
})
```

## Evaluation

Grade the episode:

```javascript
duro_evaluate_episode({
  episode_id: "episode_xxx",
  grade: "A",
  rubric: {
    outcome_quality: { score: 5, notes: "Bug fully fixed, no regressions" },
    correctness_risk: { score: 1, notes: "Low risk change" },
    reusability: { score: 4, notes: "Pattern applies to similar JWT issues" },
    reproducibility: { score: 5, notes: "Well documented" },
    cost: {
      tokens_bucket: "M",
      tools_used: 8,
      duration_mins: 25
    }
  },
  next_change: "Add JWT validation to integration tests"
})
```

### Rubric Dimensions

| Dimension | What It Measures |
|-----------|------------------|
| `outcome_quality` | Did it achieve the goal? |
| `correctness_risk` | How risky was the approach? |
| `reusability` | Can patterns be reused? |
| `reproducibility` | Can it be reproduced? |
| `cost` | Time, tokens, tools used |

### Grades

| Grade | Meaning |
|-------|---------|
| A+ / A | Excellent outcome |
| B+ / B | Good outcome |
| C | Acceptable |
| D | Below expectations |
| F | Failed |

## Applying Evaluations

Update memory based on outcomes:

```javascript
duro_apply_evaluation({
  evaluation_id: "evaluation_xxx"
})
```

This:
- Reinforces facts used in successful episodes
- Adjusts skill confidence
- Updates reputation in relevant domains

## Skills

Skills are tracked patterns:

### Skill Statistics

```json
{
  "skill": "jwt-debugging",
  "episodes": 5,
  "success_rate": 0.8,
  "avg_duration_mins": 30,
  "confidence": 0.75,
  "last_used": "2026-02-10"
}
```

### Confidence Adjustment

- Successful episode: confidence increases
- Partial success: slight increase
- Failed episode: confidence decreases
- Deltas capped at +/- 0.02 per episode

## Suggesting Episodes

Check if current work should be an episode:

```javascript
duro_suggest_episode({
  goal_summary: "Investigating performance issue",
  tools_used: true,
  duration_mins: 15,
  artifacts_produced: true
})
```

### Triggers

Create an episode when:
- Duration > 3 minutes
- Tools are used
- Artifacts are produced
- Complex multi-step work

## Learning Extraction

Auto-extract learnings from work:

```javascript
duro_extract_learnings({
  text: "Today I learned that JWT tokens must be validated...",
  auto_save: true
})
```

## Best Practices

### Create Episodes for Significant Work

Not every task needs an episode. Use for:
- Debugging sessions
- Feature implementations
- Architecture decisions
- Complex investigations

### Evaluate Honestly

Accurate grades improve the system:
- Don't inflate grades
- Capture what actually happened
- Note what could be better

### Link Artifacts

Connect episodes to facts and decisions:
- What knowledge was used?
- What knowledge was created?
- What decisions were validated?

### Close the Loop

Every episode should close:
1. Close with result
2. Evaluate with rubric
3. Apply evaluation
4. Document learnings

## The Compound Effect

Each episode:
1. Creates knowledge (facts, decisions)
2. Validates existing knowledge
3. Adjusts skill confidence
4. Builds reputation

Over time, expertise compounds:
- Better pattern recognition
- Faster problem solving
- Higher autonomy earned

## Next Steps

- [Memory concepts](/concepts/memory)
- [Verification concepts](/concepts/verification)
- [Orchestration concepts](/concepts/orchestration)
