"""
Health check endpoint.

Rich status including index, embeddings, storage.
No secrets leaked. No auth required.
"""

import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends

# Import state getter
import sys
DURO_SRC = Path.home() / ".agent" / "src"
if str(DURO_SRC) not in sys.path:
    sys.path.insert(0, str(DURO_SRC))

router = APIRouter()

# Reference to main state (will be set after import)
def get_state():
    from main import state
    return state


@router.get("/health")
async def health_check():
    """
    Rich health check.

    Returns status of index, embeddings, storage, and basic metrics.
    No authentication required. Does not leak secrets.
    """
    state = get_state()
    now = time.time()

    # Base response
    response = {
        "status": "healthy",
        "version": state.version,
        "git_commit": state.git_commit,
        "uptime_seconds": round(now - state.start_time, 2) if state.start_time else 0,
    }

    # Index status
    index_status = {
        "loaded": False,
        "artifact_count": 0,
        "last_updated": None,
    }

    if state.index:
        try:
            count = state.index.count()
            index_status["loaded"] = True
            index_status["artifact_count"] = count

            # Get last updated from most recent artifact
            try:
                recent = state.index.query(limit=1)
                if recent:
                    index_status["last_updated"] = recent[0].get("created_at")
            except Exception:
                pass
        except Exception as e:
            index_status["error"] = str(e)
            response["status"] = "degraded"
    else:
        response["status"] = "degraded"

    response["index"] = index_status

    # Embeddings status
    embeddings_status = {
        "available": False,
        "model": None,
        "vector_count": 0,
    }

    try:
        from embeddings import EMBEDDING_CONFIG
        embeddings_status["model"] = EMBEDDING_CONFIG.get("model_name", "unknown")

        # Check if vectors table exists and has data
        if state.index:
            try:
                stats = state.index.get_embedding_stats()
                embeddings_status["available"] = stats.get("embedded_count", 0) > 0
                embeddings_status["vector_count"] = stats.get("embedded_count", 0)
            except Exception:
                # Vector table might not exist
                embeddings_status["available"] = False
    except Exception as e:
        embeddings_status["error"] = str(e)

    response["embeddings"] = embeddings_status

    # Storage status
    storage_path = Path.home() / ".agent" / "memory"
    storage_status = {
        "path": str(storage_path) if not os.getenv("DURO_PROD_MODE") else "[redacted]",
        "writable": False,
        "exists": storage_path.exists(),
    }

    if storage_path.exists():
        try:
            # Test write permission
            test_file = storage_path / ".health_check"
            test_file.write_text("ok")
            test_file.unlink()
            storage_status["writable"] = True
        except Exception:
            storage_status["writable"] = False
            response["status"] = "degraded"
    else:
        response["status"] = "unhealthy"

    response["storage"] = storage_status

    # Mode info (safe to expose)
    response["mode"] = "prod" if os.getenv("DURO_PROD_MODE") else "dev" if os.getenv("DURO_DEV_MODE") else "standard"

    return response
