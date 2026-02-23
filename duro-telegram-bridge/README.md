# Duro Telegram Bridge

Connect Telegram to Claude + Duro for persistent AI memory.

```
┌──────────────┐     ┌─────────────────┐     ┌──────────┐
│   Telegram   │ ◄─► │  This Bridge    │ ◄─► │   Duro   │
│   Bot API    │     │  (Claude + MCP) │     │   MCP    │
└──────────────┘     └─────────────────┘     └──────────┘
```

## Quick Start

### 1. Create Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow prompts, save the token

### 2. Get Your Telegram User ID

1. Message [@userinfobot](https://t.me/userinfobot)
2. It will reply with your user ID (a number)

### 3. Install Dependencies

```bash
cd ~/.agent/duro-telegram-bridge
pip install -r requirements.txt
```

### 4. Set Environment Variables

```bash
# Linux/Mac
export TELEGRAM_BOT_TOKEN="your-bot-token"
export ANTHROPIC_API_KEY="your-api-key"
export ALLOWED_USER_IDS="123456789,987654321"  # Your Telegram user ID(s)

# Windows PowerShell
$env:TELEGRAM_BOT_TOKEN="your-bot-token"
$env:ANTHROPIC_API_KEY="your-api-key"
$env:ALLOWED_USER_IDS="123456789"
```

### 5. Run

```bash
python bridge.py
```

### 6. Chat!

Open your bot in Telegram and start chatting. It has access to your Duro memory.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/clear` | Clear conversation (memory persists in Duro) |
| `/status` | Check Duro connection |

## Security Features

- **Whitelist only**: Only responds to `ALLOWED_USER_IDS`
- **Rate limiting**: 2 second cooldown between messages
- **No destructive tools**: delete/prune tools are filtered out
- **Truncated responses**: Long outputs are truncated

## What Claude Can Do

With Duro connected, Claude can:

- `duro_store_fact` - Remember facts with confidence scores
- `duro_store_decision` - Log decisions with rationale
- `duro_save_learning` - Save insights
- `duro_semantic_search` - Search memory by meaning
- `duro_query_memory` - Query structured data
- `duro_get_artifact` - Retrieve specific memories
- `duro_proactive_recall` - Get relevant context

## Example Conversation

```
You: Remember that my favorite color is blue

Bot: I've stored that fact in my memory. I'll remember your
     favorite color is blue.

You: What do you know about my preferences?

Bot: Based on my memory, I know:
     - Your favorite color is blue (stored just now)

     Want me to remember anything else?
```

## Limitations

- No file uploads/downloads (security)
- No shell commands (security)
- Conversation history is per-user, in-memory
- Long responses get truncated for Telegram

## Extending

Want Slack? Discord? The pattern is the same:

1. Receive message from platform API
2. Send to Claude with Duro tools
3. Execute tool calls
4. Return response

The MCP client code (`DuroClient`) is reusable.
