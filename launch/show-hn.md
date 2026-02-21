# Show HN: Duro – Memory layer for AI agents that compounds intelligence

**Title (80 chars max):**
```
Show HN: Duro – Memory layer for AI coding agents with provenance tracking
```

**Alt titles:**
- Show HN: Duro – Your AI agent keeps making the same mistakes. Mine doesn't.
- Show HN: Duro – Persistent memory for Claude Code that validates decisions

---

## Post Body

I built Duro because my AI coding agent kept suggesting a 1000 req/min rate limit. The actual limit was 100/min. We'd learned this the hard way—production incident, 3am debugging session, the works.

A month later? Same mistake. The agent had no memory of what we'd learned.

**The problem:** AI agents are stateless. Every conversation starts from zero. Past mistakes repeat. Lessons disappear. There's no audit trail for what your agent "knows."

**Duro fixes this** by giving AI agents structured memory with provenance:

```
> agent suggests 1000 req/min
$ duro recalls: "we learned it's 100/min"
  source: production incident 2026-02-10
  status: [validated] confidence: 0.95
> agent self-corrects
```

**How it works:**

1. **Store facts with sources** – Not just "the limit is 100" but where you learned it, confidence level, evidence type

2. **Track decisions with rationale** – "We chose Redis for sessions because PostgreSQL was adding 200ms latency"

3. **Validate outcomes** – Did that decision work? Mark it validated or reversed. Confidence adjusts automatically.

4. **48-hour debug rule** – When something breaks, query what changed in the last 48 hours. Usually finds the cause.

**Tech details:**
- MCP server (works with Claude Code, Claude Desktop)
- Local-first: JSON files + SQLite, no cloud required
- Semantic search via embeddings
- MIT licensed

**What I'm NOT building:**
- Another RAG system for docs
- A vector DB wrapper
- Enterprise features nobody asked for

This is for builders who ship things and don't want their AI making the same mistake twice.

GitHub: https://github.com/ApeNIG/duro
Docs: https://apenig.github.io/duro/

Would love feedback from anyone using Claude Code or building AI agents. What memory problems do you run into?

---

## Suggested comments to seed discussion

**Comment 1 (technical depth):**
> For those curious about the architecture: artifacts are stored as JSON files (git-friendly, human-readable), indexed in SQLite with FTS5 for keyword search. Embeddings power semantic search. The "provenance" requirement for high-confidence facts is intentional—it forces you to cite sources, which makes the knowledge actually trustworthy.

**Comment 2 (use case):**
> The "wow moment" for me was when Duro prevented me from making the same API rate limit mistake twice. The agent was about to suggest 1000/min, Duro surfaced a validated decision from a month ago saying it's actually 100/min (learned from a production incident), and the agent self-corrected. That's compound intelligence.

**Comment 3 (roadmap):**
> Current focus is individual developers using Claude Code. Team features (shared memory, permissions) are on the roadmap but I'm deliberately keeping scope small. Trying to nail the core loop first: store → validate → recall → compound.
