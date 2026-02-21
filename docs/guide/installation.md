# Installation

Get Duro running in under 5 minutes.

## Prerequisites

- Python 3.10+
- An MCP-compatible client (Claude Code, Claude Desktop, etc.)

## Install Duro

```bash
# Clone the repository
git clone https://github.com/ApeNIG/duro.git ~/.agent

# Install dependencies
cd ~/.agent
pip install -e .
```

## Verify Installation

```bash
# Test the MCP server starts
python -m duro.mcp_server --help
```

You should see the help output with available options.

## Configure Your Client

### Claude Code

Add to your MCP settings:

::: code-group

```json [macOS/Linux]
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

### Claude Desktop

Add to `claude_desktop_config.json`:

::: code-group

```json [macOS]
// ~/Library/Application Support/Claude/claude_desktop_config.json
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
// %APPDATA%\Claude\claude_desktop_config.json
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

## Test the Connection

Start a new conversation and ask Claude to check Duro status:

```
Check duro status
```

You should see system statistics confirming Duro is connected.

## Directory Structure

After installation, your `~/.agent` directory looks like:

```
~/.agent/
├── duro/               # Core MCP server code
├── memory/             # Your knowledge artifacts
│   ├── facts/          # Stored facts
│   ├── decisions/      # Stored decisions
│   ├── episodes/       # Work episodes
│   └── incidents/      # Incident RCAs
├── skills/             # Skill definitions
├── rules/              # Behavioral rules
├── soul.md             # Personality config
└── duro.db             # SQLite index
```

## Next Steps

- [Store your first fact](/guide/storing-knowledge)
- [Understand memory concepts](/concepts/memory)
- [Browse all tools](/reference/tools)
