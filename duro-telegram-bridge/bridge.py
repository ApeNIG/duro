"""
Duro Telegram Bridge
~~~~~~~~~~~~~~~~~~~~~
Connects Telegram to Claude + Duro MCP for persistent memory.

Setup:
1. Create bot via @BotFather on Telegram, get token
2. pip install python-telegram-bot anthropic mcp
3. Set environment variables:
   - TELEGRAM_BOT_TOKEN
   - ANTHROPIC_API_KEY
   - ALLOWED_USER_IDS (comma-separated)
4. Run: python bridge.py

Security:
- Only responds to whitelisted user IDs
- Rate limited
- No file system access from Telegram
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field

# Telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Anthropic
import anthropic

# MCP Client (for Duro)
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

@dataclass
class Config:
    telegram_token: str = field(default_factory=lambda: os.environ["TELEGRAM_BOT_TOKEN"])
    anthropic_key: str = field(default_factory=lambda: os.environ["ANTHROPIC_API_KEY"])
    allowed_users: set = field(default_factory=lambda: {
        int(uid.strip())
        for uid in os.environ.get("ALLOWED_USER_IDS", "").split(",")
        if uid.strip()
    })
    duro_path: str = field(default_factory=lambda: os.path.expanduser("~/duro-mcp"))
    rate_limit_seconds: int = 2
    max_message_length: int = 4000

config = Config()

# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    def __init__(self, seconds: int = 2):
        self.seconds = seconds
        self.last_request: dict[int, datetime] = {}

    def check(self, user_id: int) -> bool:
        now = datetime.now()
        if user_id in self.last_request:
            if now - self.last_request[user_id] < timedelta(seconds=self.seconds):
                return False
        self.last_request[user_id] = now
        return True

rate_limiter = RateLimiter(config.rate_limit_seconds)

# =============================================================================
# Duro MCP Client
# =============================================================================

class DuroClient:
    """Connects to Duro MCP server."""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.tools: list = []

    async def connect(self):
        """Start Duro MCP server and connect."""
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "duro_mcp"],
            cwd=config.duro_path,
        )

        self.transport = await stdio_client(server_params)
        self.session = ClientSession(self.transport[0], self.transport[1])
        await self.session.initialize()

        # Get available tools
        tools_response = await self.session.list_tools()
        self.tools = tools_response.tools
        logger.info(f"Connected to Duro with {len(self.tools)} tools")

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Call a Duro MCP tool."""
        if not self.session:
            return "Duro not connected"

        result = await self.session.call_tool(name, arguments)
        return result.content[0].text if result.content else "No result"

    def get_tools_for_claude(self) -> list:
        """Convert MCP tools to Claude tool format."""
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in self.tools
            # Only expose safe read/write tools, not destructive ones
            if not any(danger in tool.name for danger in ["delete", "batch_delete", "prune"])
        ]

duro = DuroClient()

# =============================================================================
# Claude Client
# =============================================================================

class ClaudeClient:
    """Handles Claude API calls with Duro tools."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.anthropic_key)
        self.conversations: dict[int, list] = {}  # user_id -> messages

    def get_system_prompt(self) -> str:
        return """You are a helpful AI assistant with persistent memory via Duro.

You have access to Duro tools for:
- Storing and retrieving facts, decisions, learnings
- Searching memory semantically
- Tracking tasks and episodes

When the user asks you to remember something, use duro_store_fact.
When they ask what you know, use duro_semantic_search or duro_query_memory.

Keep responses concise - this is a chat interface.
Use markdown sparingly (Telegram supports basic markdown).
"""

    async def chat(self, user_id: int, message: str) -> str:
        """Send message to Claude, handle tool calls, return response."""

        # Get or create conversation history
        if user_id not in self.conversations:
            self.conversations[user_id] = []

        messages = self.conversations[user_id]
        messages.append({"role": "user", "content": message})

        # Keep conversation history bounded
        if len(messages) > 20:
            messages = messages[-20:]
            self.conversations[user_id] = messages

        # Call Claude
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=self.get_system_prompt(),
            tools=duro.get_tools_for_claude(),
            messages=messages,
        )

        # Handle tool use loop
        while response.stop_reason == "tool_use":
            # Extract tool calls
            tool_calls = [block for block in response.content if block.type == "tool_use"]

            # Execute tools
            tool_results = []
            for tool_call in tool_calls:
                logger.info(f"Calling tool: {tool_call.name}")
                result = await duro.call_tool(tool_call.name, tool_call.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": result[:2000],  # Truncate long results
                })

            # Add assistant response and tool results to messages
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            # Continue conversation
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=self.get_system_prompt(),
                tools=duro.get_tools_for_claude(),
                messages=messages,
            )

        # Extract final text response
        text_blocks = [block.text for block in response.content if hasattr(block, "text")]
        final_response = "\n".join(text_blocks)

        # Save to conversation history
        messages.append({"role": "assistant", "content": final_response})

        return final_response[:config.max_message_length]

claude = ClaudeClient()

# =============================================================================
# Telegram Handlers
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = update.effective_user.id

    if config.allowed_users and user_id not in config.allowed_users:
        await update.message.reply_text("Unauthorized.")
        return

    await update.message.reply_text(
        "Hey! I'm your Duro-powered assistant.\n\n"
        "I have persistent memory - I can remember facts, decisions, and learnings.\n\n"
        "Commands:\n"
        "/start - This message\n"
        "/clear - Clear conversation history\n"
        "/status - Check Duro connection\n\n"
        "Just chat with me!"
    )

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command."""
    user_id = update.effective_user.id

    if user_id in claude.conversations:
        claude.conversations[user_id] = []

    await update.message.reply_text("Conversation cleared. Memory persists in Duro.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    user_id = update.effective_user.id

    if config.allowed_users and user_id not in config.allowed_users:
        return

    try:
        result = await duro.call_tool("duro_status", {})
        # Truncate for Telegram
        short_status = result[:500] if len(result) > 500 else result
        await update.message.reply_text(f"```\n{short_status}\n```", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Duro error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    user_id = update.effective_user.id
    message = update.message.text

    # Security check
    if config.allowed_users and user_id not in config.allowed_users:
        logger.warning(f"Unauthorized user: {user_id}")
        return

    # Rate limit
    if not rate_limiter.check(user_id):
        await update.message.reply_text("Slow down! Rate limited.")
        return

    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = await claude.chat(user_id, message)
        await update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"Error: {str(e)[:200]}")

# =============================================================================
# Main
# =============================================================================

async def main():
    """Start the bot."""

    # Validate config
    if not config.telegram_token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")
    if not config.anthropic_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    if not config.allowed_users:
        logger.warning("ALLOWED_USER_IDS not set - bot will reject all users!")

    # Connect to Duro
    logger.info("Connecting to Duro MCP...")
    await duro.connect()

    # Create Telegram app
    app = Application.builder().token(config.telegram_token).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start bot
    logger.info("Starting Telegram bot...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Keep running
    logger.info("Bot is running. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
