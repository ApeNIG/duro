"""Semantic search endpoint."""

import sqlite3
import time
import json
from typing import Optional

from fastapi import APIRouter, Query

from .stats import get_db_connection

router = APIRouter()


@router.get("/search")
async def search_artifacts(
    query: str = Query(..., min_length=1, description="Search query"),
    type: Optional[str] = Query(None, description="Filter by artifact type"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """
    Semantic search across artifacts.
    Uses hybrid search (vector + keyword) when available.
    """
    start_time = time.time()

    try:
        conn = get_db_connection()

        # Try FTS search first
        hits = []
        mode = "keyword"

        # Build search query - use FTS if available
        try:
            # Check if FTS table exists
            fts_check = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts_fts'"
            ).fetchone()

            if fts_check:
                # Use FTS search
                fts_query = f"""
                    SELECT a.id, a.type, a.title, a.created_at, a.tags, a.sensitivity, a.file_path,
                           bm25(artifacts_fts) as keyword_score
                    FROM artifacts_fts
                    JOIN artifacts a ON artifacts_fts.id = a.id
                    WHERE artifacts_fts MATCH ?
                    {'AND a.type = ?' if type else ''}
                    ORDER BY keyword_score
                    LIMIT ?
                """

                # Escape FTS special characters and create query
                fts_term = query.replace('"', '').replace("'", "")
                params = [f'"{fts_term}"']
                if type:
                    params.append(type)
                params.append(limit)

                cursor = conn.execute(fts_query, params)
                mode = "fts"
            else:
                # Fallback to LIKE search
                like_query = f"""
                    SELECT id, type, title, created_at, tags, sensitivity, file_path,
                           0.5 as keyword_score
                    FROM artifacts
                    WHERE (title LIKE ? OR id LIKE ?)
                    {'AND type = ?' if type else ''}
                    ORDER BY created_at DESC
                    LIMIT ?
                """

                like_term = f"%{query}%"
                params = [like_term, like_term]
                if type:
                    params.append(type)
                params.append(limit)

                cursor = conn.execute(like_query, params)
                mode = "like"

        except sqlite3.OperationalError:
            # Fallback to simple LIKE search
            like_query = f"""
                SELECT id, type, title, created_at, tags, sensitivity, file_path,
                       0.5 as keyword_score
                FROM artifacts
                WHERE (title LIKE ? OR id LIKE ?)
                {'AND type = ?' if type else ''}
                ORDER BY created_at DESC
                LIMIT ?
            """

            like_term = f"%{query}%"
            params = [like_term, like_term]
            if type:
                params.append(type)
            params.append(limit)

            cursor = conn.execute(like_query, params)
            mode = "like"

        for row in cursor.fetchall():
            hit = {
                "id": row["id"],
                "type": row["type"],
                "title": row["title"],
                "created_at": row["created_at"],
                "tags": json.loads(row["tags"]) if row["tags"] else [],
                "keyword_score": abs(row["keyword_score"]) if row["keyword_score"] else 0.5,
                "semantic_score": 0.0,  # Would need embeddings for this
                "highlights": [],
            }

            # Try to get content for highlights
            file_path = row["file_path"]
            if file_path:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = json.load(f)

                        # Extract relevant text for highlighting
                        text_fields = []
                        for key in ["claim", "decision", "rationale", "goal", "message"]:
                            if key in content and content[key]:
                                text_fields.append(str(content[key]))

                        # Find matching snippets
                        query_lower = query.lower()
                        for text in text_fields:
                            if query_lower in text.lower():
                                # Extract snippet around match
                                idx = text.lower().find(query_lower)
                                start = max(0, idx - 40)
                                end = min(len(text), idx + len(query) + 40)
                                snippet = text[start:end]
                                hit["highlights"].append(snippet)

                        hit["content"] = content
                except (json.JSONDecodeError, FileNotFoundError, OSError):
                    pass

            # Calculate final score (would be weighted combination with semantic)
            hit["final_score"] = hit["keyword_score"]

            hits.append(hit)

        # Sort by final score
        hits.sort(key=lambda x: x["final_score"], reverse=True)

        took_ms = (time.time() - start_time) * 1000

        return {
            "query": query,
            "hits": hits,
            "total": len(hits),
            "took_ms": took_ms,
            "mode": mode,
        }

    except Exception as e:
        took_ms = (time.time() - start_time) * 1000
        return {
            "query": query,
            "hits": [],
            "total": 0,
            "took_ms": took_ms,
            "mode": "error",
            "error": str(e),
        }
