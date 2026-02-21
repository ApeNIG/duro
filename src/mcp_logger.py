"""
MCP-safe file-based logging for Duro.

CRITICAL: MCP servers communicate over stdio. Writing to stdout/stderr
can cause backpressure deadlocks, especially on Windows.

This module provides file-based logging that:
- Never writes to stdout/stderr
- Rotates logs to prevent disk bloat
- Is thread-safe for concurrent access
- Includes timestamps and levels
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Log location - same directory as memory
DURO_DIR = Path.home() / ".duro"
LOG_DIR = DURO_DIR / "logs"
LOG_FILE = LOG_DIR / "mcp_server.log"

# Module-level logger
_logger: Optional[logging.Logger] = None
_initialized = False


def _ensure_log_dir():
    """Ensure log directory exists."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_logger() -> logging.Logger:
    """
    Get the MCP-safe file logger.

    Lazy-initializes on first call. Thread-safe.
    """
    global _logger, _initialized

    if _initialized and _logger is not None:
        return _logger

    _ensure_log_dir()

    # Create logger
    _logger = logging.getLogger("duro_mcp")
    _logger.setLevel(logging.DEBUG)

    # Remove any existing handlers (prevents duplicates on reload)
    _logger.handlers.clear()

    # File handler with rotation (5MB max, keep 3 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)

    # Format: timestamp - level - message
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)

    _logger.addHandler(file_handler)
    _initialized = True

    return _logger


def log_info(msg: str):
    """Log info message to file."""
    get_logger().info(msg)


def log_warn(msg: str):
    """Log warning message to file."""
    get_logger().warning(msg)


def log_error(msg: str):
    """Log error message to file."""
    get_logger().error(msg)


def log_debug(msg: str):
    """Log debug message to file."""
    get_logger().debug(msg)


# Compatibility shim: redirect print-style calls to file logging
# Use these instead of print(..., file=sys.stderr)
def mcp_print(msg: str, level: str = "INFO"):
    """
    MCP-safe print replacement.

    Use instead of: print(msg, file=sys.stderr)
    """
    level = level.upper()
    if level == "INFO":
        log_info(msg)
    elif level == "WARN" or level == "WARNING":
        log_warn(msg)
    elif level == "ERROR":
        log_error(msg)
    else:
        log_debug(msg)


# On import, initialize the logger
_ensure_log_dir()
