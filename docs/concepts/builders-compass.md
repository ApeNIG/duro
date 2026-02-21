# Builder's Compass

The four pillars that guide Duro's design.

## The Four Pillars

```
┌─────────────────────────────────────────────────────────┐
│                   BUILDER'S COMPASS                     │
├─────────────┬─────────────┬─────────────┬──────────────┤
│   MEMORY    │ VERIFICATION│ORCHESTRATION│  EXPERTISE   │
│             │             │             │              │
│  Structured │  Validated  │  Controlled │   Growing    │
│  knowledge  │  outcomes   │  autonomy   │   skills     │
│  with       │  not just   │  earned     │   from       │
│  provenance │  stored     │  through    │   experience │
│             │  opinions   │  trust      │              │
└─────────────┴─────────────┴─────────────┴──────────────┘
```

## 1. Memory

> "Every fact has a source and confidence"

Duro stores knowledge as **structured artifacts** with **provenance**:

- **Facts**: Objective claims with sources
- **Decisions**: Choices with rationale
- **Episodes**: Goal → actions → outcome
- **Incidents**: RCA with prevention

### Key Features

- Source attribution (URLs, evidence type)
- Confidence scores (0.0 to 1.0)
- Time-based decay for unreinforced facts
- Semantic search for natural queries

### Why It Matters

Without provenance, you can't trust the knowledge. Duro ensures every fact can be traced to its source.

## 2. Verification

> "Every decision gets validated"

Knowledge isn't static. Duro tracks **outcomes**:

```
Make decision → Track outcome → Evaluate → Update confidence
```

### Decision Lifecycle

| Status | Meaning |
|--------|---------|
| `pending` | Just created, not tested |
| `validated` | Confirmed working |
| `reversed` | Didn't work |
| `superseded` | Replaced by newer |

### Why It Matters

Storing decisions is easy. Knowing if they worked is what matters. Validation closes the feedback loop.

## 3. Orchestration

> "Earn autonomy through trust"

Duro controls what actions the agent can take:

- **Permission checking** before risky operations
- **Reputation tracking** per domain
- **Approval workflows** for high-risk actions
- **Audit logging** for accountability

### Autonomy Levels

| Level | Description |
|-------|-------------|
| `propose` | Can only suggest, never execute |
| `supervised` | Execute with approval |
| `autonomous` | Execute without asking |

### Why It Matters

AI agents need guardrails. Duro provides graduated autonomy based on demonstrated competence.

## 4. Expertise

> "Skills improve through practice"

Duro builds domain expertise over time:

- **Skills** with tracked statistics
- **Episode evaluation** for learning
- **Confidence adjustments** based on outcomes
- **Pattern recognition** from past work

### Expertise Growth

```
Episode 1: Try approach → partial success → learn
Episode 2: Apply learning → success → reinforce
Episode 3: Pattern emerges → skill improves
```

### Why It Matters

Intelligence compounds. Each successful episode builds expertise for the next.

## How They Work Together

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│   MEMORY stores facts ──► VERIFICATION validates them    │
│                                                          │
│   ORCHESTRATION controls actions based on EXPERTISE      │
│                                                          │
│   EXPERTISE grows from verified MEMORY                   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Example Flow

1. **Memory**: Store fact "API rate limit is 100/min"
2. **Verification**: Confirm fact when implementation works
3. **Orchestration**: Grant autonomy for API calls (agent earned trust)
4. **Expertise**: Build skill in API integration

## The Compound Effect

Each pillar reinforces the others:

- More **memory** enables better **decisions**
- Better **decisions** validate faster
- Faster **validation** builds **expertise**
- More **expertise** earns **autonomy**
- More **autonomy** creates more **memory**

This is how AI agents get genuinely smarter over time.

## Next Steps

- [Memory in depth](/concepts/memory)
- [Verification in depth](/concepts/verification)
- [Orchestration in depth](/concepts/orchestration)
- [Architecture overview](/concepts/architecture)
