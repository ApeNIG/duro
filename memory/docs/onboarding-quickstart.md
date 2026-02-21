# Duro Quick Start

**Time to value: 10 minutes**

Go from zero to "holy sh*t, it remembers with receipts" in under 10 minutes.

---

## What You'll Do

| Step | Time | What Happens |
|------|------|--------------|
| 1. Install | 2 min | Clone repo, verify structure |
| 2. Configure | 2 min | Add Duro to Claude Code MCP |
| 3. Store | 3 min | Create your first decision |
| 4. Recall | 2 min | Watch Duro surface it |
| 5. Validate | 1 min | Mark it as validated |

**End result:** A validated decision that surfaces automatically when relevant.

---

## Step 1: Install (2 minutes)

### Clone Duro

```bash
git clone https://github.com/ApeNIG/duro.git ~/.agent
```

### Verify Structure

```bash
ls ~/.agent
```

You should see:
```
memory/       # Facts, decisions, episodes
skills/       # Reusable skill definitions
rules/        # Behavioral rules
soul.md       # Agent personality config
duro.db       # SQLite index
```

**Checkpoint:** You have the Duro directory at `~/.agent`

---

## Step 2: Configure MCP (2 minutes)

### Add to Claude Code

Open your Claude Code MCP configuration and add:

**macOS/Linux:** `~/.config/claude-code/mcp.json`
**Windows:** `%APPDATA%\claude-code\mcp.json`

```json
{
  "mcpServers": {
    "duro": {
      "command": "python",
      "args": ["-m", "duro.mcp_server"],
      "cwd": "/path/to/your/.agent"
    }
  }
}
```

### Restart Claude Code

Close and reopen Claude Code to load the MCP server.

### Verify Connection

In Claude Code, ask:
```
> duro status
```

You should see Duro's system status with memory stats.

**Checkpoint:** Claude Code can talk to Duro

---

## Step 3: Store Your First Decision (3 minutes)

### The Scenario

You've learned something important that you don't want to forget. Let's store it.

### Store a Decision

In Claude Code, say:
```
> Store a decision: "Always use environment variables for API keys, never hardcode them. Learned this after accidentally committing a key to GitHub."
```

Claude will call `duro_store_decision` and create:
```
decision_[timestamp]_[id]
├── decision: "Always use environment variables for API keys..."
├── rationale: "Accidentally committed a key to GitHub"
├── status: pending
└── confidence: 0.5
```

### View Your Decision

```
> Show me my recent decisions
```

**Checkpoint:** You have a decision stored in Duro

---

## Step 4: See the Recall (2 minutes)

### The Magic Moment

Now pretend you forgot. Ask Claude about API keys:

```
> I'm setting up a new API integration. Should I put the API key in the config file?
```

### What Happens

1. Claude searches Duro for relevant memories
2. Duro finds your decision about API keys
3. Claude responds with your past learning:

```
Actually, I found a relevant decision in Duro:

Decision: Always use environment variables for API keys,
never hardcode them.

Rationale: Learned after accidentally committing a key to GitHub.

For your new integration, use environment variables instead
of putting the key in a config file.
```

**Checkpoint:** Duro surfaced your past decision automatically

---

## Step 5: Validate the Decision (1 minute)

### Mark It as Validated

Once you've confirmed this decision works in practice:

```
> Validate my API keys decision - it's been working well, zero leaks
```

Claude will call `duro_validate_decision`:
```
decision_[id]
├── status: validated ✓
├── confidence: 0.8 (increased)
└── verified_at: [timestamp]
```

### Why This Matters

- **Validated decisions** surface with higher priority
- **Confidence scores** help Duro know what to trust
- **Provenance** shows exactly where knowledge came from

**Checkpoint:** You have a validated decision with provenance

---

## You Just Did This

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   1. Stored a decision                                      │
│              ↓                                              │
│   2. Asked a related question                               │
│              ↓                                              │
│   3. Duro surfaced the decision automatically               │
│              ↓                                              │
│   4. Validated it based on real outcomes                    │
│              ↓                                              │
│   [INTELLIGENCE COMPOUNDS]                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

This is the core loop. Every decision you store and validate makes your AI smarter.

---

## What's Next

### Store More Knowledge

| Type | Command | Use When |
|------|---------|----------|
| **Fact** | `store a fact: "..."` | Something objectively true |
| **Decision** | `store a decision: "..."` | A choice you made and why |
| **Learning** | `save a learning: "..."` | An insight from experience |

### Explore Duro Tools

| Tool | What It Does |
|------|--------------|
| `duro_semantic_search` | Find memories by meaning |
| `duro_query_memory` | Search by tags, type, date |
| `duro_proactive_recall` | Surface relevant memories for context |
| `duro_validate_decision` | Mark decisions as validated/reversed |
| `duro_store_incident` | Record debugging RCAs |

### Try the Wow Demo

Ask Claude:
```
> I need to implement a batch API caller. What's our rate limit
  for the external API? I remember seeing 1000 requests per
  minute somewhere.
```

Duro has a pre-seeded decision showing the rate limit is actually 100/min. Watch it self-correct with full provenance.

---

## Troubleshooting

### "Duro tools not found"

1. Check MCP config path is correct
2. Verify Python can run `duro.mcp_server`
3. Restart Claude Code

### "No memories found"

1. Verify you stored the decision (check `~/.agent/memory/decisions/`)
2. Try exact tag search: `search memories tagged: api`
3. Use semantic search with different phrasing

### "Decision not surfacing"

1. Check the decision exists: `show my recent decisions`
2. Proactive recall has relevance thresholds
3. Try direct search: `search duro for API keys`

---

## The Builder's Compass

You just experienced the first pillar: **Memory**.

| Pillar | What You'll Learn |
|--------|-------------------|
| **Memory** | Facts and decisions with provenance ✓ |
| **Verification** | Validation loops and outcome tracking |
| **Orchestration** | Permission controls and autonomy |
| **Expertise** | Skills and rules that compound |

Each pillar builds on the last. Start with Memory, add Verification when you have enough decisions to validate.

---

## Quick Reference

### Store Things

```
store a fact: "PostgreSQL max connections default is 100"
store a decision: "Use Redis for session storage because..."
save a learning: "Always check logs before restarting"
log an incident: "Service crashed due to memory leak..."
```

### Find Things

```
search duro for rate limits
show my recent decisions
what do we know about authentication?
query memories tagged: database
```

### Validate Things

```
validate the rate limit decision - confirmed working
reverse the caching decision - caused more problems
```

---

## Time Check

| Step | Target | Actual |
|------|--------|--------|
| Install | 2 min | |
| Configure | 2 min | |
| Store | 3 min | |
| Recall | 2 min | |
| Validate | 1 min | |
| **Total** | **10 min** | |

If you're under 10 minutes, you're doing great. If not, let us know what slowed you down.

---

*Built by builders who don't want to ship nonsense.*
