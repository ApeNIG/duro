"""
Duro REST API
HTTP interface for the Duro memory system.

Enables use with any LLM or integration, not just MCP clients.
"""

import os
import sys
import time
import json
import hashlib
from pathlib import Path
from contextlib import asynccontextmanager
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add Duro src to path
DURO_SRC = Path.home() / ".agent" / "src"
if str(DURO_SRC) not in sys.path:
    sys.path.insert(0, str(DURO_SRC))

# Import Duro modules (after path setup)
from artifacts import ArtifactStore
from index import ArtifactIndex

# Duro paths
MEMORY_DIR = Path.home() / ".agent" / "memory"
DB_PATH = MEMORY_DIR / "index.db"

# =============================================================================
# Configuration
# =============================================================================

API_KEYS_FILE = Path.home() / ".agent" / "config" / "api_keys.json"
DEV_MODE = os.getenv("DURO_DEV_MODE", "").lower() in ("1", "true", "yes")
PROD_MODE = os.getenv("DURO_PROD_MODE", "").lower() in ("1", "true", "yes")

# Rate limiting config
RATE_LIMIT_PER_KEY = int(os.getenv("DURO_RATE_LIMIT", "100"))  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds


# =============================================================================
# API Key Authentication
# =============================================================================

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def load_api_keys() -> set[str]:
    """
    Load valid API keys.
    Priority: env var > config file
    """
    # 1. Check env var first
    env_keys = os.getenv("DURO_API_KEYS", "")
    if env_keys:
        return set(k.strip() for k in env_keys.split(",") if k.strip())

    # 2. Check config file
    if API_KEYS_FILE.exists():
        try:
            with open(API_KEYS_FILE) as f:
                data = json.load(f)
                return set(data.get("keys", []))
        except Exception:
            pass

    return set()


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Verify API key is valid.

    Auth behavior:
    - If keys configured: require valid key
    - If no keys + DURO_DEV_MODE=1: allow (dev mode)
    - If no keys + no dev mode: deny (safe default)
    """
    valid_keys = load_api_keys()

    # Keys configured: require valid key
    if valid_keys:
        if api_key is None:
            raise HTTPException(status_code=401, detail="Missing API key")
        if api_key not in valid_keys:
            raise HTTPException(status_code=403, detail="Invalid API key")
        return api_key

    # No keys configured
    if DEV_MODE:
        return "dev-mode"

    # Safe default: deny
    raise HTTPException(
        status_code=401,
        detail="No API keys configured. Set DURO_API_KEYS env var or create ~/.agent/config/api_keys.json, or set DURO_DEV_MODE=1 for development."
    )


# =============================================================================
# Rate Limiting (per-key + per-IP fallback)
# =============================================================================

class RateLimiter:
    """Simple in-memory rate limiter with per-key and per-IP tracking."""

    def __init__(self, limit: int = 100, window: int = 60):
        self.limit = limit
        self.window = window
        self.requests: dict[str, list[float]] = defaultdict(list)

    def _clean_old(self, key: str, now: float):
        """Remove requests outside the window."""
        cutoff = now - self.window
        self.requests[key] = [t for t in self.requests[key] if t > cutoff]

    def check(self, key: str) -> tuple[bool, int, int]:
        """
        Check if request is allowed.
        Returns: (allowed, remaining, retry_after)
        """
        now = time.time()
        self._clean_old(key, now)

        count = len(self.requests[key])
        if count >= self.limit:
            # Calculate retry_after
            oldest = min(self.requests[key]) if self.requests[key] else now
            retry_after = int(oldest + self.window - now) + 1
            return False, 0, retry_after

        self.requests[key].append(now)
        remaining = self.limit - count - 1
        return True, remaining, 0


rate_limiter = RateLimiter(limit=RATE_LIMIT_PER_KEY, window=RATE_LIMIT_WINDOW)


async def check_rate_limit(request: Request, api_key: str = Depends(verify_api_key)):
    """Rate limit middleware - per key, with IP fallback."""
    # Use API key if available, else IP
    if api_key and api_key != "dev-mode":
        limit_key = f"key:{api_key[:16]}"  # Hash prefix for privacy
    else:
        limit_key = f"ip:{request.client.host}"

    allowed, remaining, retry_after = rate_limiter.check(limit_key)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(RATE_LIMIT_PER_KEY),
                "X-RateLimit-Remaining": "0",
            }
        )

    # Add headers to response (handled in middleware)
    request.state.rate_limit_remaining = remaining
    return api_key


# =============================================================================
# Shared State
# =============================================================================

class DuroState:
    """Shared application state."""
    artifact_store: ArtifactStore = None
    index: ArtifactIndex = None
    start_time: float = None
    version: str = "1.0.0"
    git_commit: str = None


state = DuroState()


def get_state() -> DuroState:
    """Dependency to get shared Duro state."""
    return state


# =============================================================================
# Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Duro components on startup."""
    print("Duro REST API starting...")
    state.start_time = time.time()

    # Try to get git commit
    try:
        git_head = Path.home() / ".agent" / ".git" / "HEAD"
        if git_head.exists():
            ref = git_head.read_text().strip()
            if ref.startswith("ref:"):
                ref_path = Path.home() / ".agent" / ".git" / ref.split(": ")[1]
                if ref_path.exists():
                    state.git_commit = ref_path.read_text().strip()[:8]
            else:
                state.git_commit = ref[:8]
    except Exception:
        pass

    # Initialize artifact store and index
    try:
        state.index = ArtifactIndex(DB_PATH)
        state.artifact_store = ArtifactStore(MEMORY_DIR, DB_PATH)
        print(f"Artifact store loaded: {state.index.count()} artifacts")
    except Exception as e:
        print(f"Warning: Could not initialize artifact store: {e}")

    # Preload embedding model
    try:
        from embeddings import preload_embedding_model
        preload_embedding_model()
        print("Embedding model loaded")
    except Exception as e:
        print(f"Warning: Could not load embedding model: {e}")

    mode = "DEV" if DEV_MODE else ("PROD" if PROD_MODE else "STANDARD")
    print(f"Duro REST API ready (mode={mode})")

    yield

    print("Duro REST API shutting down...")


# =============================================================================
# App
# =============================================================================

app = FastAPI(
    title="Duro API",
    description="""
REST API for the Duro memory system.

**Store facts with provenance, track decisions, and search your AI's memory.**

## Authentication

Include your API key in the `X-API-Key` header:
```
curl -H "X-API-Key: your-key-here" https://your-duro-instance/api/v1/artifacts
```

## Rate Limiting

- 100 requests per minute per API key
- `X-RateLimit-Remaining` header shows remaining requests
- `Retry-After` header indicates wait time when limited
    """,
    version=state.version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# =============================================================================
# CORS
# =============================================================================

# In prod, configure allowed origins via env var
CORS_ORIGINS = os.getenv("DURO_CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Rate Limit Response Headers Middleware
# =============================================================================

@app.middleware("http")
async def add_rate_limit_headers(request: Request, call_next):
    """Add rate limit headers to responses."""
    response = await call_next(request)

    # Add rate limit headers if we tracked them
    if hasattr(request.state, "rate_limit_remaining"):
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_PER_KEY)
        response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)

    return response


# =============================================================================
# Routes
# =============================================================================

@app.get("/")
async def root():
    """API root - basic info."""
    return {
        "name": "Duro API",
        "version": state.version,
        "docs": "/docs",
        "description": "Memory layer for AI agents that compounds intelligence over time.",
    }


# Import and include routers
from routers import health, artifacts, search

app.include_router(health.router, tags=["health"])

app.include_router(
    artifacts.router,
    prefix="/api/v1",
    tags=["artifacts"],
    dependencies=[Depends(check_rate_limit)],
)

app.include_router(
    search.router,
    prefix="/api/v1",
    tags=["search"],
    dependencies=[Depends(check_rate_limit)],
)
