# Introduction

Duro is a memory layer for AI agents that compounds intelligence over time.

## The Problem

Your AI forgets everything. Every conversation starts from zero. Past mistakes get repeated. Lessons learned disappear. There's no audit trail for what your agent "knows."

**Without memory:**
- Agent suggests 1000 req/min → ships broken code → production incident
- Same mistake happens again next month
- No one knows why decisions were made

## The Solution

Duro gives your AI agents **structured memory with provenance**. Every fact has a source. Every decision can be validated. Intelligence compounds instead of resetting.

**With Duro:**
- Agent suggests 1000 req/min → Duro surfaces: "We learned it's 100/min after a production incident"
- Agent self-corrects with receipts
- Decision is auditable forever

## The Builder's Compass

Duro is built on four pillars:

### Memory
> "Every fact has a source and confidence"

Store facts, decisions, and episodes with full provenance. Know where knowledge came from and how confident you should be.

### Verification
> "Every decision gets validated"

Track outcomes. Validate what worked. Reverse what didn't. Build institutional memory that's actually correct.

### Orchestration
> "Every action is permissioned"

Reputation-based autonomy. Agents earn trust through successful outcomes. High-risk actions require approval.

### Domain Expertise
> "Patterns become reusable skills"

Codify knowledge into skills and rules. What works once becomes repeatable. Expertise compounds.

## Key Features

| Feature | What It Does |
|---------|--------------|
| **Facts with Provenance** | Store claims with source URLs, confidence scores, evidence type |
| **Decision Validation** | Track outcomes: validated, reversed, or superseded |
| **Episode Tracking** | Record goal → plan → actions → result → evaluation |
| **Confidence Decay** | Unreinforced facts lose confidence over time |
| **48-Hour Debug Gate** | Surface recent changes when debugging incidents |
| **Semantic Search** | Find relevant memories using natural language |
| **Local-First** | All data stored locally as JSON + SQLite |

## Who It's For

**Builders who care about correctness.** Teams that want learning to compound. Those who don't want to ship nonsense.

- AI developers using Claude Code daily
- Teams building AI-powered products
- Anyone who wants to audit what their AI "knows"

## Architecture

```
~/.agent/
├── memory/
│   ├── facts/           # Stored facts with provenance
│   ├── decisions/       # Decisions with validation status
│   ├── episodes/        # Goal-tracking records
│   └── docs/            # Documentation
├── skills/              # Reusable skill definitions
├── rules/               # Behavioral rules
├── soul.md              # Agent personality config
└── duro.db              # SQLite index + embeddings
```

All artifacts are JSON files. Human-readable. Git-friendly. No cloud required.

## Next Steps

- [Get started in 10 minutes](/guide/getting-started)
- [Understand the concepts](/concepts/memory)
- [Explore the MCP tools](/reference/tools)
