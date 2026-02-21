# Duro

**Memory layer for AI agents that compounds intelligence over time.**

> Your AI forgets everything. Duro fixes that—and shows you exactly where every decision came from.

---

## The Problem

Every conversation with your AI agent starts from zero. Past mistakes get repeated. Lessons learned disappear. There's no audit trail for what your agent "knows."

**Without memory:**
- Agent suggests 1000 req/min → ships broken code → production incident
- Same mistake happens again next month
- No one knows why decisions were made

## The Solution

Duro gives your AI agents **structured memory with provenance**. Every fact has a source. Every decision can be validated. Intelligence compounds instead of resetting.

**With Duro:**
- Agent suggests 1000 req/min → Duro surfaces: *"We learned it's 100/min after a production incident"*
- Agent self-corrects with receipts
- Decision is auditable forever

---

## The Builder's Compass

Duro is built on four pillars:

### Memory
> "Every fact has a source and confidence"

Store facts, decisions, and episodes with full provenance. Know where knowledge came from and how confident you should be.

```
Fact: External API rate limit is 100 requests per minute
Confidence: 0.95
Source: API docs + incident report
```

### Verification
> "Every decision gets validated"

Track outcomes. Validate what worked. Reverse what didn't. Build institutional memory that's actually correct.

```
Decision: Use 100/min rate limit (not 1000)
Status: VALIDATED
Evidence: Zero rate limit errors in 2 weeks
```

### Orchestration
> "Every action is permissioned"

Reputation-based autonomy. Agents earn trust through successful outcomes. High-risk actions require approval.

```
Domain: code_changes
Reputation: 0.85
Autonomy Level: supervised
```

### Domain Expertise
> "Patterns become reusable skills"

Codify knowledge into skills and rules. What works once becomes repeatable. Expertise compounds.

```
Skill: debug_rate_limit
Success Rate: 94%
Times Used: 47
```

---

## Quick Start

### Installation

Duro runs as an MCP server with Claude Code:

```bash
# Clone the repo
git clone https://github.com/ApeNIG/duro.git ~/.agent

# Add to Claude Code MCP config
# (See MCP configuration below)
```

### MCP Configuration

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "duro": {
      "command": "python",
      "args": ["-m", "duro.mcp_server"],
      "cwd": "~/.agent"
    }
  }
}
```

### First Use

In Claude Code, Duro tools are automatically available:

```
You: "What do we know about API rate limits?"

Claude: [Searches Duro memory]
        "Found a validated decision: Rate limit is 100/min,
         not 1000. Source: Production incident 2026-02-10."
```

---

## The Wow Moment

Here's what Duro actually does:

**You say:**
> "I need to implement a batch API caller. What's our rate limit? I remember seeing 1000 requests per minute somewhere."

**Without Duro:** Claude guesses. You ship broken code. Production incident.

**With Duro:**
> "Actually, I found a validated decision. The rate limit is **100 requests per minute**, not 1000. This was confirmed after a production incident on February 10th where the service crashed due to rate limiting."

**The feeling:** *"Holy sh*t, it remembers with receipts."*

---

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

---

## Who It's For

**Builders who care about correctness.** Teams that want learning to compound. Those who don't want to ship nonsense.

- AI developers using Claude Code daily
- Teams building AI-powered products
- Anyone who wants to audit what their AI "knows"

---

## Architecture

```
~/.agent/
├── memory/
│   ├── facts/           # Stored facts with provenance
│   ├── decisions/       # Decisions with validation status
│   ├── episodes/        # Goal-tracking records
│   └── docs/            # Documentation and scripts
├── skills/              # Reusable skill definitions
├── rules/               # Behavioral rules
├── soul.md              # Agent personality config
└── duro.db              # SQLite index + embeddings
```

All artifacts are JSON files. Human-readable. Git-friendly. No cloud required.

---

## MCP Tools

Duro exposes 50+ MCP tools. Key ones:

| Tool | Purpose |
|------|---------|
| `duro_store_fact` | Store a fact with source attribution |
| `duro_store_decision` | Record a decision with rationale |
| `duro_validate_decision` | Mark decision as validated/reversed |
| `duro_semantic_search` | Find relevant memories |
| `duro_proactive_recall` | Surface memories for current context |
| `duro_query_recent_changes` | 48-hour debug gate |

---

## Roadmap

- [x] Core memory system (facts, decisions, episodes)
- [x] Decision validation loops
- [x] Semantic search with embeddings
- [x] MCP server integration
- [ ] Memory inspector UI
- [ ] Provenance visualization
- [ ] Team namespaces
- [ ] GitHub integration

---

## Philosophy

Duro implements the **Builder's Compass**:

| Scarce Resource | What Duro Provides |
|-----------------|-------------------|
| **Truth** | Facts with provenance, validated decisions |
| **Taste** | Rules and skills that encode what works |
| **Continuity** | Memory that persists and compounds |

In the AI age, generation is cheap. Verification, taste, and continuity are scarce. Duro focuses on the scarce stuff.

---

## License

MIT

---

## Links

- [Competitive Analysis](memory/docs/duro-competitive-analysis-2026-02.md)
- [Business Model](memory/docs/duro-business-model-2026-02.md)
- [Builder's Compass Synthesis](memory/docs/duro-builders-compass-synthesis.md)

---

*Built by builders who don't want to ship nonsense.*
