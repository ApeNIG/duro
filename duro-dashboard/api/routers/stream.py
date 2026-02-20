"""Server-Sent Events (SSE) streaming endpoints."""

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

DURO_DB_PATH = Path.home() / ".agent" / "memory" / "index.db"

# Thread pool for database operations
executor = ThreadPoolExecutor(max_workers=2)


def _get_artifact_count() -> int:
    """Get artifact count (sync, runs in thread)."""
    conn = sqlite3.connect(f"file:{DURO_DB_PATH}?mode=ro", uri=True)
    cursor = conn.execute("SELECT COUNT(*) FROM artifacts")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def _get_new_artifacts(since: str) -> list[dict]:
    """Get new artifacts since timestamp (sync, runs in thread)."""
    conn = sqlite3.connect(f"file:{DURO_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT id, type, created_at, title, sensitivity
        FROM artifacts
        WHERE created_at > ?
        ORDER BY created_at DESC
        LIMIT 10
    """, (since,))
    artifacts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return artifacts


def format_sse(event: str, data: str) -> str:
    """Format an SSE message."""
    return f"event: {event}\ndata: {data}\n\n"


async def heartbeat_generator() -> AsyncGenerator[str, None]:
    """Generate heartbeat events every 5 seconds."""
    loop = asyncio.get_event_loop()

    while True:
        start = time.perf_counter()

        try:
            count = await loop.run_in_executor(executor, _get_artifact_count)
            latency_ms = (time.perf_counter() - start) * 1000

            yield format_sse("heartbeat", json.dumps({
                "status": "healthy",
                "latency_ms": round(latency_ms, 2),
                "artifact_count": count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))
        except Exception as e:
            yield format_sse("heartbeat", json.dumps({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))

        await asyncio.sleep(5)


async def activity_generator() -> AsyncGenerator[str, None]:
    """Generate activity events when new artifacts are created."""
    loop = asyncio.get_event_loop()
    last_check = datetime.now(timezone.utc).isoformat()

    # Send initial connected event immediately
    yield format_sse("connected", json.dumps({"status": "connected", "timestamp": last_check}))

    while True:
        try:
            new_artifacts = await loop.run_in_executor(executor, _get_new_artifacts, last_check)

            if new_artifacts:
                last_check = new_artifacts[0]["created_at"]

                for artifact in reversed(new_artifacts):
                    yield format_sse("artifact", json.dumps(artifact))

        except Exception as e:
            yield format_sse("error", json.dumps({"error": str(e)}))

        await asyncio.sleep(2)


@router.get("/heartbeat")
async def heartbeat_stream():
    """SSE endpoint for health heartbeat."""
    return StreamingResponse(
        heartbeat_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/activity")
async def activity_stream():
    """SSE endpoint for real-time artifact activity."""
    return StreamingResponse(
        activity_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
