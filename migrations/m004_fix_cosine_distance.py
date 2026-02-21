"""
Migration 004: Fix vec0 table to use cosine distance.

Problem:
- artifact_vectors was created without distance_metric specification
- sqlite-vec defaults to L2 (Euclidean) distance
- Code assumes cosine distance (similarity = 1 - distance)
- L2 distances for 384-dim vectors often exceed 1.0, making similarity = 0

Fix:
- Recreate artifact_vectors with distance_metric=cosine
- Clear embedding_state to trigger re-embedding
- All embeddings will be regenerated on next reembed call

Note: This requires re-embedding all artifacts. Run duro_reembed after migration.
"""

MIGRATION_ID = "004_fix_cosine_distance"
DEPENDS_ON = ["001_add_vectors"]


def up(db_path: str) -> dict:
    """
    Apply migration: recreate vec0 table with cosine distance.

    Returns:
        {
            "success": bool,
            "embeddings_cleared": int,
            "message": str
        }
    """
    import sqlite3

    result = {
        "success": False,
        "embeddings_cleared": 0,
        "message": ""
    }

    conn = sqlite3.connect(db_path)

    try:
        # Idempotency check: if vec table is already configured for cosine, skip.
        cursor = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='artifact_vectors'"
        )
        row = cursor.fetchone()
        if row and row[0] and "distance_metric=cosine" in row[0]:
            result["success"] = True
            result["message"] = "artifact_vectors already configured with cosine distance"
            return result

        # Check if sqlite-vec is available
        vec_available = False
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            vec_available = True
        except Exception as e:
            result["message"] = f"sqlite-vec not available: {e}. Migration skipped."
            result["success"] = True  # Not a failure, just not applicable
            return result

        # Count existing embeddings before clearing
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM embedding_state")
            result["embeddings_cleared"] = cursor.fetchone()[0]
        except Exception:
            result["embeddings_cleared"] = 0

        # Drop old vec0 table (vec0 tables can't be altered)
        conn.execute("DROP TABLE IF EXISTS artifact_vectors")

        # Recreate with cosine distance metric
        conn.execute("""
            CREATE VIRTUAL TABLE artifact_vectors USING vec0(
                artifact_id TEXT PRIMARY KEY,
                embedding FLOAT[384] distance_metric=cosine
            )
        """)

        # Clear embedding_state to mark all as needing re-embedding
        conn.execute("DELETE FROM embedding_state")

        conn.commit()
        result["success"] = True
        result["message"] = f"Recreated artifact_vectors with cosine distance. Cleared {result['embeddings_cleared']} embeddings. Run duro_reembed to regenerate."

    except Exception as e:
        result["message"] = f"Migration failed: {e}"
        conn.rollback()
    finally:
        conn.close()

    return result


def down(db_path: str) -> dict:
    """
    Rollback migration: recreate vec0 table with L2 distance (original).

    Note: This loses all embeddings again.
    """
    import sqlite3

    result = {"success": False, "message": ""}

    conn = sqlite3.connect(db_path)

    try:
        # Check if sqlite-vec is available
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
        except Exception as e:
            result["message"] = f"sqlite-vec not available: {e}"
            result["success"] = True
            return result

        # Drop cosine table
        conn.execute("DROP TABLE IF EXISTS artifact_vectors")

        # Recreate with default L2 distance
        conn.execute("""
            CREATE VIRTUAL TABLE artifact_vectors USING vec0(
                artifact_id TEXT PRIMARY KEY,
                embedding FLOAT[384]
            )
        """)

        # Clear embedding_state
        conn.execute("DELETE FROM embedding_state")

        # Remove migration record
        try:
            conn.execute("DELETE FROM schema_migrations WHERE migration_id = ?", (MIGRATION_ID,))
        except Exception:
            pass

        conn.commit()
        result["success"] = True
        result["message"] = "Rolled back to L2 distance. All embeddings cleared."

    except Exception as e:
        result["message"] = f"Rollback failed: {e}"
        conn.rollback()
    finally:
        conn.close()

    return result


def check_status(db_path: str) -> dict:
    """
    Check migration status and verify cosine distance is configured.
    """
    import sqlite3

    status = {
        "applied": False,
        "vec_table_exists": False,
        "embeddings_count": 0,
        "distance_metric": "unknown"
    }

    conn = sqlite3.connect(db_path)

    try:
        # Check schema_migrations (if migration runner was used)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        )
        if cursor.fetchone():
            cursor = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE migration_id = ?", (MIGRATION_ID,)
            )
            status["applied"] = cursor.fetchone() is not None

        # Check vec table exists + inspect DDL to determine metric
        cursor = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='artifact_vectors'"
        )
        row = cursor.fetchone()
        status["vec_table_exists"] = row is not None
        if row and row[0]:
            ddl = row[0]
            if "distance_metric=cosine" in ddl:
                status["distance_metric"] = "cosine"
                # Consider migration applied if schema reflects desired state.
                status["applied"] = True
            else:
                status["distance_metric"] = "L2 (default)"

        # Count embeddings
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM embedding_state")
            status["embeddings_count"] = cursor.fetchone()[0]
        except Exception:
            pass

    except Exception:
        pass
    finally:
        conn.close()

    return status


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python m004_fix_cosine_distance.py <db_path> [up|down|status]")
        sys.exit(1)

    db_path = sys.argv[1]
    action = sys.argv[2] if len(sys.argv) > 2 else "up"

    if action == "up":
        result = up(db_path)
    elif action == "down":
        result = down(db_path)
    elif action == "status":
        result = check_status(db_path)
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)

    print(json.dumps(result, indent=2))
