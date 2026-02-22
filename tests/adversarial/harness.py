"""
Adversarial Test Harness - Isolated DB and controlled environment for testing.

Provides:
- IsolatedTestDB: Temp SQLite database that auto-cleans
- MockEmbedder: Controlled embedding generation
- Utilities for concurrent testing
- test_with_timeout: Timeout wrapper with stack trace dump for debugging hangs
"""

import os
import sys
import json
import shutil
import tempfile
import hashlib
import sqlite3
import threading
import faulthandler
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field


# =============================================================================
# Timeout Utilities
# =============================================================================

class HarnessTimeoutError(Exception):
    """Raised when a test exceeds its timeout."""
    pass


@contextmanager
def test_with_timeout(seconds: int = 30, exit_on_timeout: bool = False):
    """
    Context manager for test timeout with stack trace dump.

    Uses faulthandler.dump_traceback_later() which:
    - Works cross-platform
    - Can interrupt truly stuck code (with exit=True)
    - Dumps all thread stacks to stderr

    Usage:
        with test_with_timeout(10):
            # ... test code that might hang ...

    Args:
        seconds: Timeout in seconds
        exit_on_timeout: If True, hard-exit the process on timeout (useful for CI)
    """
    # Enable faulthandler timeout - dumps stacks after `seconds` and optionally exits
    faulthandler.dump_traceback_later(seconds, repeat=False, exit=exit_on_timeout)

    try:
        yield
    finally:
        # Cancel the timeout if we finished in time
        faulthandler.cancel_dump_traceback_later()

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))


@dataclass
class MockArtifact:
    """A test artifact with controlled properties."""
    id: str
    type: str
    claim: str
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> dict:
        """Convert to full artifact dict format."""
        return {
            "id": self.id,
            "type": self.type,
            "version": "1.1",
            "created_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "sensitivity": "public",
            "tags": self.tags,
            "source": {"workflow": "adversarial_test"},
            "data": {
                "claim": self.claim,
                "confidence": self.confidence,
                "provenance": "test"
            }
        }


class IsolatedTestDB:
    """
    Creates an isolated test environment with temporary database.

    Usage:
        with IsolatedTestDB() as env:
            env.add_artifact(artifact)
            env.delete_artifact(artifact_id)
            # ... tests ...
        # Auto-cleanup on exit

    Thread-safety:
        Uses an INSTANCE-level write lock to coordinate file + SQLite operations.
        This prevents race conditions where file I/O and SQLite ops interleave badly.

        The shared connection (_conn) is ONLY safe because all access is guarded by
        _write_lock. Never call _populate_fts() or _delete_fts() without holding the lock.
    """

    def __init__(self, name: str = "test"):
        self.name = name
        self.temp_dir = None
        self.db_path = None
        self.memory_dir = None
        self.index = None
        self._artifacts: Dict[str, dict] = {}
        self._conn: Optional[sqlite3.Connection] = None  # Shared connection for FTS
        self._write_lock = threading.Lock()  # Instance-level lock (not class-level)
        self._lock_holder: Optional[int] = None  # Track which thread holds the lock

    def __enter__(self):
        # Create temp directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"duro_test_{self.name}_"))
        self.db_path = self.temp_dir / "index.db"
        self.memory_dir = self.temp_dir / "artifacts"
        self.memory_dir.mkdir()

        # Create index
        from index import ArtifactIndex
        self.index = ArtifactIndex(self.db_path)

        # Run migrations to add all required columns
        self._run_migrations()

        # Create shared connection for FTS operations with WAL mode
        # check_same_thread=False allows use from multiple threads (needed for concurrent tests)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._conn.execute("PRAGMA synchronous = NORMAL")

        return self

    def _run_migrations(self):
        """Apply database migrations for test environment."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)

        # Add temporal columns (m002)
        try:
            conn.execute("ALTER TABLE artifacts ADD COLUMN valid_from TEXT")
            conn.execute("ALTER TABLE artifacts ADD COLUMN valid_until TEXT")
            conn.execute("ALTER TABLE artifacts ADD COLUMN superseded_by TEXT")
            conn.execute("ALTER TABLE artifacts ADD COLUMN importance REAL DEFAULT 0.5")
            conn.execute("ALTER TABLE artifacts ADD COLUMN pinned INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Columns already exist

        # Add reinforcement columns (m003)
        try:
            conn.execute("ALTER TABLE artifacts ADD COLUMN last_reinforced_at TEXT")
            conn.execute("ALTER TABLE artifacts ADD COLUMN reinforcement_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        # Create embedding tables
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embedding_state (
                    artifact_id TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    embedded_at TEXT NOT NULL,
                    model TEXT NOT NULL
                )
            """)
        except sqlite3.OperationalError:
            pass

        # Create FTS table
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS artifact_fts USING fts5(
                    id UNINDEXED,
                    title,
                    tags,
                    text
                )
            """)
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Close shared FTS connection first
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

        # Close any open connections
        self.index = None

        # Cleanup temp directory with retry for Windows file locking
        if self.temp_dir and self.temp_dir.exists():
            import gc
            gc.collect()  # Help release file handles

            for attempt in range(3):
                try:
                    shutil.rmtree(self.temp_dir)
                    break
                except PermissionError:
                    import time
                    time.sleep(0.1 * (attempt + 1))
            else:
                # Final attempt - ignore errors
                shutil.rmtree(self.temp_dir, ignore_errors=True)

        return False

    def add_artifact(self, artifact: MockArtifact) -> str:
        """Add a test artifact to the isolated environment.

        Uses a write lock to coordinate file I/O + SQLite operations,
        preventing potential deadlocks during rapid create/delete cycles.
        """
        artifact_dict = artifact.to_dict()

        # Single lock for all write operations: file + index + FTS
        with self._write_lock:
            self._lock_holder = threading.current_thread().ident

            # Write artifact file
            artifact_dir = self.memory_dir / artifact.type
            artifact_dir.mkdir(exist_ok=True)
            file_path = artifact_dir / f"{artifact.id}.json"

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(artifact_dict, f)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk (prevents stale handles)

            # Calculate hash
            file_hash = hashlib.sha256(json.dumps(artifact_dict).encode()).hexdigest()[:16]

            # Index artifact
            self.index.upsert(artifact_dict, str(file_path), file_hash)

            # Populate FTS and commit (single-artifact path still commits per-op for safety)
            self._populate_fts_no_commit(artifact)
            self._conn.commit()

            # Track internally
            self._artifacts[artifact.id] = artifact_dict
            self._lock_holder = None

        return artifact.id

    def add_artifacts_batch(self, artifacts: List[MockArtifact]) -> List[str]:
        """Add multiple artifacts in a single FTS transaction (faster than per-item).

        Strategy: Do all file writes + index upserts first, then batch FTS inserts
        with a single commit. This avoids connection conflicts between index and FTS.
        """
        ids = []
        fts_pending = []  # Store (artifact, artifact_dict) for FTS phase

        with self._write_lock:
            self._lock_holder = threading.current_thread().ident

            # Phase 1: File writes + index upserts (each index.upsert commits internally)
            for artifact in artifacts:
                artifact_dict = artifact.to_dict()

                # Write artifact file
                artifact_dir = self.memory_dir / artifact.type
                artifact_dir.mkdir(exist_ok=True)
                file_path = artifact_dir / f"{artifact.id}.json"

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(artifact_dict, f)
                    f.flush()
                    os.fsync(f.fileno())

                # Calculate hash and index
                file_hash = hashlib.sha256(json.dumps(artifact_dict).encode()).hexdigest()[:16]
                self.index.upsert(artifact_dict, str(file_path), file_hash)

                # Track internally
                self._artifacts[artifact.id] = artifact_dict
                ids.append(artifact.id)
                fts_pending.append(artifact)

            # Phase 2: Batch FTS inserts (single commit for all)
            for artifact in fts_pending:
                self._populate_fts_no_commit(artifact)
            self._conn.commit()

            self._lock_holder = None

        return ids

    def delete_artifact(self, artifact_id: str) -> bool:
        """Delete an artifact with proper locking.

        Removes from: FTS index, main index, file system, internal tracking.
        Uses same lock as add_artifact to prevent race conditions.
        """
        with self._write_lock:
            self._lock_holder = threading.current_thread().ident

            # Delete from FTS
            self._delete_fts_no_commit(artifact_id)

            # Delete from index
            self.index.delete(artifact_id)

            # Delete file if exists
            artifact = self._artifacts.get(artifact_id)
            if artifact:
                artifact_type = artifact.get("type", "unknown")
                file_path = self.memory_dir / artifact_type / f"{artifact_id}.json"
                if file_path.exists():
                    file_path.unlink()

            # Remove from internal tracking
            self._artifacts.pop(artifact_id, None)

            # Commit FTS changes
            self._conn.commit()
            self._lock_holder = None

        return True

    def delete_artifacts_batch(self, artifact_ids: List[str]) -> int:
        """Delete multiple artifacts in a single FTS transaction (faster)."""
        deleted = 0

        with self._write_lock:
            self._lock_holder = threading.current_thread().ident

            # Phase 1: Index deletes + file deletes (index.delete commits internally)
            for artifact_id in artifact_ids:
                # Delete from index first
                self.index.delete(artifact_id)

                # Delete file if exists
                artifact = self._artifacts.get(artifact_id)
                if artifact:
                    artifact_type = artifact.get("type", "unknown")
                    file_path = self.memory_dir / artifact_type / f"{artifact_id}.json"
                    if file_path.exists():
                        file_path.unlink()

                # Remove from internal tracking
                self._artifacts.pop(artifact_id, None)
                deleted += 1

            # Phase 2: Batch FTS deletes (single commit)
            for artifact_id in artifact_ids:
                self._delete_fts_no_commit(artifact_id)
            self._conn.commit()

            self._lock_holder = None

        return deleted

    def _assert_lock_held(self):
        """Assert that the current thread holds the write lock."""
        current = threading.current_thread().ident
        if self._lock_holder != current:
            raise RuntimeError(
                f"_write_lock must be held! Current thread: {current}, "
                f"lock holder: {self._lock_holder}"
            )

    def _populate_fts_no_commit(self, artifact: MockArtifact):
        """Populate FTS without committing (for batching).

        INTERNAL: Caller MUST hold _write_lock.
        """
        self._assert_lock_held()

        title = artifact.claim[:100] if artifact.claim else ""
        tags_str = " ".join(artifact.tags)
        text = artifact.claim

        # Delete existing entry if any, then insert
        self._conn.execute("DELETE FROM artifact_fts WHERE id = ?", (artifact.id,))
        self._conn.execute(
            "INSERT INTO artifact_fts (id, title, tags, text) VALUES (?, ?, ?, ?)",
            (artifact.id, title, tags_str, text)
        )
        # No commit - caller handles batching

    def _delete_fts_no_commit(self, artifact_id: str):
        """Delete from FTS without committing (for batching).

        INTERNAL: Caller MUST hold _write_lock.
        """
        self._assert_lock_held()
        self._conn.execute("DELETE FROM artifact_fts WHERE id = ?", (artifact_id,))
        # No commit - caller handles batching

    def get_artifact(self, artifact_id: str) -> Optional[dict]:
        """Get artifact from index."""
        return self.index.get_by_id(artifact_id)

    def count_artifacts(self, artifact_type: Optional[str] = None) -> int:
        """Count artifacts in index."""
        return self.index.count(artifact_type)


class MockEmbedder:
    """
    Mock embedder for controlled testing.

    Can be configured to:
    - Return specific embeddings for specific content
    - Simulate failures
    - Return different model names
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.model_name = "test-model-v1"
        self.embeddings: Dict[str, List[float]] = {}
        self.fail_on: List[str] = []
        self.call_count = 0
        self._lock = threading.Lock()

    def set_embedding(self, content_hash: str, embedding: List[float]):
        """Set a specific embedding for a content hash."""
        self.embeddings[content_hash] = embedding

    def fail_for(self, content_hash: str):
        """Configure embedder to fail for specific content."""
        self.fail_on.append(content_hash)

    def embed(self, text: str) -> Optional[List[float]]:
        """Generate or return embedding."""
        with self._lock:
            self.call_count += 1

        # Check for configured failure
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        if content_hash in self.fail_on:
            return None

        # Check for pre-configured embedding
        if content_hash in self.embeddings:
            return self.embeddings[content_hash]

        # Generate deterministic embedding from hash
        return self._hash_to_embedding(content_hash)

    def _hash_to_embedding(self, content_hash: str) -> List[float]:
        """Convert hash to deterministic embedding vector."""
        import struct

        # Use hash bytes to seed deterministic vector
        hash_bytes = bytes.fromhex(content_hash.ljust(32, '0')[:32])

        # Generate dimension floats from hash
        embedding = []
        for i in range(self.dimension):
            # Mix hash bytes for each dimension
            idx = i % 16
            value = hash_bytes[idx] / 255.0 - 0.5
            # Add some variation based on position
            value += (hash_bytes[(idx + 1) % 16] / 512.0) * ((-1) ** i)
            embedding.append(value)

        # Normalize to unit vector
        norm = sum(x*x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding


def generate_collision_candidates(target_hash_prefix: str, count: int = 100) -> List[str]:
    """
    Generate strings that might collide on truncated MD5 hash.

    For testing dedup collision risk.

    Args:
        target_hash_prefix: The hash prefix to try to collide with
        count: Number of candidates to generate

    Returns:
        List of strings to test
    """
    candidates = []
    base = "test content "

    for i in range(count * 1000):  # Try many more to find collisions
        candidate = f"{base}{i}"
        h = hashlib.md5(candidate.encode()).hexdigest()[:len(target_hash_prefix)]
        if h == target_hash_prefix:
            candidates.append(candidate)
            if len(candidates) >= count:
                break

    return candidates


def find_md5_collision_pair(prefix_len: int = 12, max_attempts: int = 1000000) -> Optional[tuple]:
    """
    Find two different strings that produce the same truncated MD5 hash.

    This demonstrates the birthday paradox - with 12 hex chars (48 bits),
    collisions become likely after ~2^24 attempts.

    For testing purposes, we use a smaller search space.

    Args:
        prefix_len: Length of hash prefix to match
        max_attempts: Maximum attempts before giving up

    Returns:
        Tuple of (string1, string2, shared_hash) or None if not found
    """
    seen: Dict[str, str] = {}

    for i in range(max_attempts):
        # Generate test string
        test_str = f"collision_test_{i}_{datetime.now().timestamp()}"
        h = hashlib.md5(test_str.encode()).hexdigest()[:prefix_len]

        if h in seen:
            return (seen[h], test_str, h)
        seen[h] = test_str

    return None


@contextmanager
def concurrent_executor(num_threads: int = 4):
    """
    Context manager for running concurrent operations.

    Usage:
        with concurrent_executor(4) as executor:
            results = executor.run([fn1, fn2, fn3, fn4])
    """
    results = []
    errors = []
    barrier = threading.Barrier(num_threads + 1)  # +1 for main thread

    class Executor:
        def run(self, functions: List[Callable]) -> List[Any]:
            threads = []
            local_results = [None] * len(functions)
            local_errors = [None] * len(functions)

            def worker(idx, fn):
                barrier.wait()  # Sync start
                try:
                    local_results[idx] = fn()
                except Exception as e:
                    local_errors[idx] = e

            for i, fn in enumerate(functions):
                t = threading.Thread(target=worker, args=(i, fn))
                threads.append(t)
                t.start()

            # Release all threads at once
            barrier.wait()

            # Wait for completion
            for t in threads:
                t.join()

            return local_results, local_errors

    try:
        yield Executor()
    finally:
        pass
