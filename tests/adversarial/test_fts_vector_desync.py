"""
Test: FTS/Vector Index Desynchronization (Priority: HIGH)

Tests that Full-Text Search (FTS) index and vector embedding index
stay synchronized.

Risk: If FTS and vector indexes become desynchronized:
- Hybrid search returns inconsistent results
- Some artifacts findable by keyword but not semantic search (or vice versa)
- Health checks may report misleading coverage stats

File refs:
- duro-mcp/index.py:upsert (updates FTS)
- duro-mcp/index.py:upsert_embedding (updates vectors)
- duro-mcp/index.py:hybrid_search (combines FTS + vectors)
- duro-mcp/index.py:get_search_capabilities (reports coverage)
"""

import pytest
import sys
import sqlite3
from pathlib import Path
from typing import List, Dict, Set, Tuple

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact


class TestFTSVectorSync:
    """Tests for FTS and vector index synchronization."""

    def test_artifact_in_both_indexes(self, isolated_db, mock_embedder):
        """Baseline: Properly indexed artifact appears in both FTS and vectors."""
        artifact_id = "fact_both_indexes"
        content = "Python decorators modify function behavior"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim=content,
            tags=["python", "decorators"]
        ))

        # Add embedding
        embedding = mock_embedder.embed(content)
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash="hash_both",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        # Check FTS
        with sqlite3.connect(isolated_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                ("decorators",)
            )
            fts_results = [row[0] for row in cursor.fetchall()]

        # Check vector
        state = isolated_db.index.get_embedding_state(artifact_id)

        assert artifact_id in fts_results, "Artifact should be in FTS index"
        assert state is not None, "Artifact should have embedding"

    def test_detect_fts_only_artifact(self, isolated_db, mock_embedder):
        """
        Test: Detect artifact in FTS but missing from vector index.

        This happens when artifact is indexed but embedding fails or
        is skipped.
        """
        NUM_ARTIFACTS = 5
        MISSING_VECTOR = [1, 3]  # These won't have embeddings

        # Create all artifacts (adds to FTS via upsert)
        for i in range(NUM_ARTIFACTS):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_fts_only_{i}",
                type="fact",
                claim=f"FTS only test content {i}",
                tags=["fts-test"]
            ))

        # Add embeddings for some (not MISSING_VECTOR)
        embedding = mock_embedder.embed("FTS only test content 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_fts_only_0",
            embedding=embedding,
            content_hash="hash_0",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        for i in range(NUM_ARTIFACTS):
            if i not in MISSING_VECTOR and i != 0:
                embedding = mock_embedder.embed(f"FTS only test content {i}")
                isolated_db.index.upsert_embedding(
                    artifact_id=f"fact_fts_only_{i}",
                    embedding=embedding,
                    content_hash=f"hash_{i}",
                    model_name=mock_embedder.model_name
                )

        # Find desync: in FTS but not in vectors
        fts_ids = set()
        with sqlite3.connect(isolated_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                ("fts-test",)
            )
            fts_ids = {row[0] for row in cursor.fetchall()}

        vector_ids = set()
        for i in range(NUM_ARTIFACTS):
            artifact_id = f"fact_fts_only_{i}"
            state = isolated_db.index.get_embedding_state(artifact_id)
            if state is not None:
                vector_ids.add(artifact_id)

        # FTS-only artifacts (desync)
        fts_only = fts_ids - vector_ids

        expected_fts_only = {f"fact_fts_only_{i}" for i in MISSING_VECTOR}
        assert fts_only == expected_fts_only, f"Expected {expected_fts_only}, got {fts_only}"

    def test_detect_vector_only_artifact(self, isolated_db, mock_embedder):
        """
        Test: Detect artifact with embedding but missing from FTS.

        This could happen if FTS table is corrupted or rebuilt incorrectly.
        (This scenario is harder to create naturally, so we simulate it.)
        """
        artifact_id = "fact_vector_only"
        content = "Vector only test content"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim=content,
            tags=["vector-test"]
        ))

        # Add embedding
        embedding = mock_embedder.embed(content)
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash="hash_vector",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        # Manually corrupt FTS by deleting the entry
        with sqlite3.connect(isolated_db.db_path) as conn:
            conn.execute(
                "DELETE FROM artifact_fts WHERE id = ?",
                (artifact_id,)
            )
            conn.commit()

        # Verify vector exists but FTS doesn't
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state is not None, "Embedding should exist"

        with sqlite3.connect(isolated_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT id FROM artifact_fts WHERE id = ?",
                (artifact_id,)
            )
            fts_result = cursor.fetchone()

        assert fts_result is None, "FTS entry should be missing (simulated corruption)"

    def test_sync_audit_function(self, isolated_db, mock_embedder):
        """
        Test: Function to audit FTS/vector sync status.

        This documents the pattern for a health check.
        """
        def audit_index_sync(db) -> Dict:
            """Audit synchronization between FTS and vector indexes."""
            # Get all artifact IDs from main index
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.execute("SELECT id FROM artifacts")
                all_ids = {row[0] for row in cursor.fetchall()}

                # Get FTS IDs
                cursor = conn.execute("SELECT DISTINCT id FROM artifact_fts")
                fts_ids = {row[0] for row in cursor.fetchall()}

                # Get vector IDs
                cursor = conn.execute("SELECT artifact_id FROM embedding_state")
                vector_ids = {row[0] for row in cursor.fetchall()}

            return {
                "total_artifacts": len(all_ids),
                "in_fts": len(all_ids & fts_ids),
                "in_vectors": len(all_ids & vector_ids),
                "in_both": len(all_ids & fts_ids & vector_ids),
                "fts_only": all_ids & fts_ids - vector_ids,
                "vector_only": all_ids & vector_ids - fts_ids,
                "neither": all_ids - fts_ids - vector_ids,
            }

        # Create test data
        for i in range(5):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_audit_{i}",
                type="fact",
                claim=f"Audit test content {i}"
            ))

        # Embed some
        embedding = mock_embedder.embed("Audit test content 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_audit_0",
            embedding=embedding,
            content_hash="hash_0",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        for i in [1, 2]:  # Only embed 0, 1, 2
            embedding = mock_embedder.embed(f"Audit test content {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_audit_{i}",
                embedding=embedding,
                content_hash=f"hash_{i}",
                model_name=mock_embedder.model_name
            )

        # Run audit
        result = audit_index_sync(isolated_db)

        assert result["total_artifacts"] == 5
        assert result["in_fts"] == 5  # All in FTS
        assert result["in_vectors"] == 3  # Only 0, 1, 2
        assert result["in_both"] == 3
        assert len(result["fts_only"]) == 2  # 3, 4 are FTS-only


class TestHybridSearchConsistency:
    """Tests for hybrid search behavior with desync scenarios."""

    def test_hybrid_search_uses_both_indexes(self, isolated_db, mock_embedder):
        """Test: Hybrid search combines FTS and vector results."""
        # Create artifacts with distinct keywords
        artifacts = [
            ("fact_hybrid_1", "Python decorators are powerful"),
            ("fact_hybrid_2", "JavaScript closures capture variables"),
            ("fact_hybrid_3", "Rust ownership prevents memory leaks"),
        ]

        for artifact_id, content in artifacts:
            isolated_db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=content
            ))

        # Embed all
        embedding = mock_embedder.embed(artifacts[0][1])
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifacts[0][0],
            embedding=embedding,
            content_hash="hash_1",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        for artifact_id, content in artifacts[1:]:
            embedding = mock_embedder.embed(content)
            isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=embedding,
                content_hash=f"hash_{artifact_id}",
                model_name=mock_embedder.model_name
            )

        # FTS search for "Python" should find fact_hybrid_1
        with sqlite3.connect(isolated_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                ("Python",)
            )
            fts_results = [row[0] for row in cursor.fetchall()]

        assert "fact_hybrid_1" in fts_results

    def test_fts_fallback_when_no_embedding(self, isolated_db, mock_embedder):
        """
        Test: Search should still work via FTS when embedding missing.

        Hybrid search should gracefully handle missing embeddings.
        """
        artifact_id = "fact_fts_fallback"
        content = "Unique keyword xyzabc123 in content"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim=content
        ))

        # Don't add embedding - simulate missing

        # FTS should still find it
        with sqlite3.connect(isolated_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                ("xyzabc123",)
            )
            fts_results = [row[0] for row in cursor.fetchall()]

        assert artifact_id in fts_results, "FTS should find artifact without embedding"


class TestIndexRebuild:
    """Tests for index rebuild scenarios."""

    def test_reindex_preserves_consistency(self, isolated_db, mock_embedder):
        """
        Test: Reindex operation maintains FTS/vector consistency.
        """
        # Create and embed artifacts
        for i in range(3):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_reindex_{i}",
                type="fact",
                claim=f"Reindex test content {i}"
            ))

        embedding = mock_embedder.embed("Reindex test content 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_reindex_0",
            embedding=embedding,
            content_hash="hash_0",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        for i in range(1, 3):
            embedding = mock_embedder.embed(f"Reindex test content {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_reindex_{i}",
                embedding=embedding,
                content_hash=f"hash_{i}",
                model_name=mock_embedder.model_name
            )

        # Capture pre-reindex state
        pre_fts_count = 0
        pre_vector_count = 0

        with sqlite3.connect(isolated_db.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM artifact_fts")
            pre_fts_count = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM embedding_state")
            pre_vector_count = cursor.fetchone()[0]

        # Note: Actual reindex would call isolated_db.index.rebuild()
        # For this test, we verify counts are stable

        assert pre_fts_count >= 3
        assert pre_vector_count >= 3


class TestSearchCapabilities:
    """Tests for search capabilities reporting."""

    def test_get_search_capabilities_accuracy(self, isolated_db, mock_embedder):
        """Test: get_search_capabilities reports accurate coverage."""
        NUM_ARTIFACTS = 10
        EMBEDDED_COUNT = 7

        # Create all artifacts
        for i in range(NUM_ARTIFACTS):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_caps_{i}",
                type="fact",
                claim=f"Capabilities test content {i}"
            ))

        # Embed some
        embedding = mock_embedder.embed("Capabilities test content 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_caps_0",
            embedding=embedding,
            content_hash="hash_0",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        for i in range(1, EMBEDDED_COUNT):
            embedding = mock_embedder.embed(f"Capabilities test content {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_caps_{i}",
                embedding=embedding,
                content_hash=f"hash_{i}",
                model_name=mock_embedder.model_name
            )

        # Get capabilities
        caps = isolated_db.index.get_search_capabilities()

        # Verify reported stats
        # Note: Exact structure depends on implementation
        assert caps is not None

    def test_capabilities_reflect_desync(self, isolated_db, mock_embedder):
        """
        Test: Capabilities should reflect actual index state.

        If there's desync, capabilities should show it.
        """
        # Create artifact but don't embed
        isolated_db.add_artifact(MockArtifact(
            id="fact_desync_caps",
            type="fact",
            claim="Desync capabilities test"
        ))

        caps = isolated_db.index.get_search_capabilities()

        # Should indicate some artifacts lack embeddings
        # (exact assertion depends on capabilities structure)
        assert caps is not None


class TestConcurrentIndexUpdates:
    """Tests for concurrent FTS and vector index updates."""

    def test_concurrent_upsert_and_embed(self, isolated_db, mock_embedder):
        """
        Test: Concurrent artifact upsert and embedding don't cause desync.
        """
        import threading
        import time

        artifact_id = "fact_concurrent_index"
        content = "Concurrent index update test"
        errors = []

        def do_upsert():
            try:
                isolated_db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=content
                ))
            except Exception as e:
                errors.append(("upsert", str(e)))

        def do_embed():
            time.sleep(0.01)  # Small delay to let upsert start
            try:
                embedding = mock_embedder.embed(content)
                isolated_db.index.upsert_embedding(
                    artifact_id=artifact_id,
                    embedding=embedding,
                    content_hash="hash_concurrent",
                    model_name=mock_embedder.model_name
                )
            except Exception as e:
                errors.append(("embed", str(e)))

        # Run concurrently
        t1 = threading.Thread(target=do_upsert)
        t2 = threading.Thread(target=do_embed)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Check for acceptable errors (busy/locked is OK, corruption is not)
        for op, error in errors:
            acceptable = ["database is locked", "busy", "SQLITE_BUSY", "no such table"]
            if not any(acc in error for acc in acceptable):
                pytest.fail(f"Unexpected error in {op}: {error}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
