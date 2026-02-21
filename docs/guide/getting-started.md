# Quick Start

Get from zero to "holy sh*t, it remembers with receipts" in under 10 minutes.

## What You'll Do

| Step | Time | What Happens |
|------|------|--------------|
| 1. Install | 2 min | Clone repo, verify structure |
| 2. Configure | 2 min | Add Duro to Claude Code MCP |
| 3. Store | 3 min | Create your first decision |
| 4. Recall | 2 min | Watch Duro surface it |
| 5. Validate | 1 min | Mark it as validated |

## Step 1: Install

```bash
git clone https://github.com/ApeNIG/duro.git ~/.agent
```

Verify the structure:

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

## Step 2: Configure MCP

Add to your Claude Code MCP settings:

::: code-group

```json [macOS/Linux]
// ~/.config/claude-code/mcp.json
{
  "mcpServers": {
    "duro": {
      "command": "python",
      "args": ["-m", "duro.mcp_server"],
      "cwd": "/Users/yourname/.agent"
    }
  }
}
```

```json [Windows]
// %APPDATA%\claude-code\mcp.json
{
  "mcpServers": {
    "duro": {
      "command": "python",
      "args": ["-m", "duro.mcp_server"],
      "cwd": "C:\\Users\\yourname\\.agent"
    }
  }
}
```

:::

Restart Claude Code to load the MCP server.

## Step 3: Store Your First Decision

In Claude Code, say:

```
Store a decision: "Always use environment variables for API keys,
never hardcode them. Learned this after accidentally committing
a key to GitHub."
```

Claude will call `duro_store_decision` and create a decision artifact with your rationale.

## Step 4: See the Recall

Now ask about API keys:

```
I'm setting up a new API integration. Should I put the
API key in the config file?
```

**What happens:**
1. Claude searches Duro for relevant memories
2. Duro finds your decision about API keys
3. Claude responds with your past learning

```
Actually, I found a relevant decision in Duro:

Decision: Always use environment variables for API keys,
never hardcode them.

Rationale: Learned after accidentally committing a key to GitHub.

For your new integration, use environment variables instead.
```

## Step 5: Validate the Decision

Once you've confirmed this decision works:

```
Validate my API keys decision - it's been working well, zero leaks
```

The decision is now marked as **validated** with increased confidence.

## You Just Did This

```
1. Stored a decision
        ↓
2. Asked a related question
        ↓
3. Duro surfaced the decision automatically
        ↓
4. Validated it based on real outcomes
        ↓
[INTELLIGENCE COMPOUNDS]
```

This is the core loop. Every decision you store and validate makes your AI smarter.

## Next Steps

- [Store different types of knowledge](/guide/storing-knowledge)
- [Learn about validation](/guide/validation)
- [Explore all MCP tools](/reference/tools)
- [Understand the concepts](/concepts/memory)
