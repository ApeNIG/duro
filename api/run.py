#!/usr/bin/env python3
"""
Duro REST API entry point.

Usage:
    python run.py                    # Default port 8002
    DURO_API_PORT=9000 python run.py # Custom port
    DURO_DEV_MODE=1 python run.py    # Dev mode (no auth required)
"""

import os
import sys
import uvicorn

# Default configuration
DEFAULT_PORT = 8002
DEFAULT_HOST = "127.0.0.1"


def main():
    port = int(os.getenv("DURO_API_PORT", DEFAULT_PORT))
    host = os.getenv("DURO_API_HOST", DEFAULT_HOST)
    reload = os.getenv("DURO_DEV_MODE", "").lower() in ("1", "true", "yes")

    print(f"Starting Duro REST API on {host}:{port}")
    if reload:
        print("Development mode: auto-reload enabled, auth disabled")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
