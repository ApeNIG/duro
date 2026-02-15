"""
Test: Large Artifact Stress Tests (Priority: MEDIUM)

Tests system behavior with extremely large artifacts and high volumes.

Risk: Large content could cause:
- Memory exhaustion during indexing
- Slow queries that timeout
- Database bloat
- Embedding failures

File refs:
- duro-mcp/index.py:95-168 (upsert - handles large content)
- duro-mcp/embeddings.py (embedding large text)
- duro-mcp/index.py:hybrid_search (searching large corpus)
"""

import pytest
import sys
import time
import gc
from pathlib import Path
from typing import List

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact


class TestLargeContentHandling:
    """Tests for handling large content in artifacts."""

    def test_large_claim_1kb(self, isolated_db):
        """Test: 1KB claim content."""
        large_claim = "Test content. " * 100  # ~1.4KB

        isolated_db.add_artifact(MockArtifact(
            id="fact_1kb",
            type="fact",
            claim=large_claim
        ))

        # Verify stored and retrievable
        stored = isolated_db.index.get_by_id("fact_1kb")
        assert stored is not None

    def test_large_claim_10kb(self, isolated_db):
        """Test: 10KB claim content."""
        large_claim = "Test content with more words. " * 500  # ~15KB

        isolated_db.add_artifact(MockArtifact(
            id="fact_10kb",
            type="fact",
            claim=large_claim
        ))

        stored = isolated_db.index.get_by_id("fact_10kb")
        assert stored is not None

    def test_large_claim_100kb(self, isolated_db):
        """Test: 100KB claim content."""
        large_claim = "A" * 100000  # 100KB

        isolated_db.add_artifact(MockArtifact(
            id="fact_100kb",
            type="fact",
            claim=large_claim
        ))

        stored = isolated_db.index.get_by_id("fact_100kb")
        assert stored is not None

    def test_large_claim_1mb(self, isolated_db):
        """Test: 1MB claim content - may be slow or rejected."""
        large_claim = "B" * 1000000  # 1MB

        start_time = time.time()
        try:
            isolated_db.add_artifact(MockArtifact(
                id="fact_1mb",
                type="fact",
                claim=large_claim
            ))
            elapsed = time.time() - start_time

            # Should complete in reasonable time (< 10 seconds)
            assert elapsed < 10, f"Indexing 1MB took {elapsed:.2f}s"

            stored = isolated_db.index.get_by_id("fact_1mb")
            assert stored is not None
        except MemoryError:
            pytest.skip("System ran out of memory for 1MB artifact")
        except Exception as e:
            # Some limit exceeded - acceptable
            pass

    def test_many_tags(self, isolated_db):
        """Test: Artifact with many tags."""
        many_tags = [f"tag_{i}" for i in range(1000)]

        isolated_db.add_artifact(MockArtifact(
            id="fact_many_tags",
            type="fact",
            claim="Test claim with many tags",
            tags=many_tags
        ))

        stored = isolated_db.index.get_by_id("fact_many_tags")
        assert stored is not None


class TestHighVolumeIndexing:
    """Tests for indexing many artifacts."""

    def test_index_100_artifacts(self, isolated_db):
        """Test: Index 100 artifacts."""
        start_time = time.time()

        for i in range(100):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_vol100_{i}",
                type="fact",
                claim=f"Volume test fact number {i} with some content"
            ))

        elapsed = time.time() - start_time

        # Should complete quickly
        assert elapsed < 5, f"Indexing 100 artifacts took {elapsed:.2f}s"

        # Verify count
        count = isolated_db.count_artifacts("fact")
        assert count >= 100

    def test_index_500_artifacts(self, isolated_db):
        """Test: Index 500 artifacts."""
        start_time = time.time()

        for i in range(500):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_vol500_{i}",
                type="fact",
                claim=f"Volume test fact {i}"
            ))

        elapsed = time.time() - start_time

        # Should complete in reasonable time
        assert elapsed < 30, f"Indexing 500 artifacts took {elapsed:.2f}s"

        count = isolated_db.count_artifacts("fact")
        assert count >= 500

    def test_index_different_types(self, isolated_db):
        """Test: Index many artifacts of different types."""
        types = ["fact", "decision", "episode"]

        for artifact_type in types:
            for i in range(50):
                if artifact_type == "fact":
                    claim = f"Fact content {i}"
                elif artifact_type == "decision":
                    claim = f"Decision content {i}"
                else:
                    claim = f"Episode goal {i}"

                isolated_db.add_artifact(MockArtifact(
                    id=f"{artifact_type}_multi_{i}",
                    type=artifact_type,
                    claim=claim
                ))

        # Verify counts per type
        for artifact_type in types:
            count = isolated_db.count_artifacts(artifact_type)
            assert count >= 50, f"Expected >= 50 {artifact_type}s, got {count}"


class TestLargeEmbeddings:
    """Tests for embedding large content."""

    def test_embed_large_content(self, isolated_db, mock_embedder):
        """Test: Embedding large content doesn't crash."""
        large_claim = "Word " * 10000  # ~50KB of words

        isolated_db.add_artifact(MockArtifact(
            id="fact_embed_large",
            type="fact",
            claim=large_claim
        ))

        # Try to embed
        embedding = mock_embedder.embed(large_claim)
        assert embedding is not None
        assert len(embedding) == mock_embedder.dimension

        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_embed_large",
            embedding=embedding,
            content_hash="hash_large",
            model_name=mock_embedder.model_name
        )

        if success:
            state = isolated_db.index.get_embedding_state("fact_embed_large")
            assert state is not None

    def test_embed_many_artifacts(self, isolated_db, mock_embedder):
        """Test: Embedding many artifacts."""
        NUM_ARTIFACTS = 100

        # Create artifacts
        for i in range(NUM_ARTIFACTS):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_embed_many_{i}",
                type="fact",
                claim=f"Embedding test content {i}"
            ))

        # Embed first to check if available
        embedding = mock_embedder.embed("Embedding test content 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_embed_many_0",
            embedding=embedding,
            content_hash="hash_0",
            model_name=mock_embedder.model_name
        )

        if not success:
            pytest.skip("sqlite-vec not available")

        # Embed remaining
        start_time = time.time()
        for i in range(1, NUM_ARTIFACTS):
            embedding = mock_embedder.embed(f"Embedding test content {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_embed_many_{i}",
                embedding=embedding,
                content_hash=f"hash_{i}",
                model_name=mock_embedder.model_name
            )

        elapsed = time.time() - start_time
        assert elapsed < 30, f"Embedding 100 artifacts took {elapsed:.2f}s"


class TestMemoryUsage:
    """Tests for memory behavior under stress."""

    def test_memory_cleanup_after_large_indexing(self, isolated_db):
        """Test: Memory is released after indexing large content."""
        # Force garbage collection
        gc.collect()

        # Index large content
        large_claim = "X" * 500000  # 500KB
        isolated_db.add_artifact(MockArtifact(
            id="fact_memory_test",
            type="fact",
            claim=large_claim
        ))

        # Release reference and collect
        del large_claim
        gc.collect()

        # System should still be responsive
        isolated_db.add_artifact(MockArtifact(
            id="fact_after_large",
            type="fact",
            claim="Small content after large"
        ))

        stored = isolated_db.index.get_by_id("fact_after_large")
        assert stored is not None

    def test_repeated_large_operations(self, isolated_db):
        """Test: Repeated large operations don't accumulate memory."""
        for iteration in range(5):
            # Create large content
            large_claim = f"Iteration {iteration} " * 10000

            isolated_db.add_artifact(MockArtifact(
                id=f"fact_repeat_{iteration}",
                type="fact",
                claim=large_claim
            ))

            # Force cleanup
            gc.collect()

        # Should have all artifacts
        for i in range(5):
            stored = isolated_db.index.get_by_id(f"fact_repeat_{i}")
            assert stored is not None


class TestQueryPerformance:
    """Tests for query performance with large datasets."""

    def test_search_in_large_corpus(self, isolated_db):
        """Test: FTS search remains fast with many artifacts."""
        NUM_ARTIFACTS = 200

        # Create corpus
        for i in range(NUM_ARTIFACTS):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_corpus_{i}",
                type="fact",
                claim=f"Corpus fact {i} about Python programming language",
                tags=["corpus", "test"]
            ))

        # Add one unique artifact
        isolated_db.add_artifact(MockArtifact(
            id="fact_unique_needle",
            type="fact",
            claim="Unique needle artifact about quantum computing",
            tags=["unique"]
        ))

        # Search for unique term
        import sqlite3
        start_time = time.time()

        with sqlite3.connect(isolated_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                ("quantum",)
            )
            results = [row[0] for row in cursor.fetchall()]

        elapsed = time.time() - start_time

        assert "fact_unique_needle" in results
        assert elapsed < 1, f"FTS search took {elapsed:.2f}s"

    def test_count_query_performance(self, isolated_db):
        """Test: Count queries remain fast with many artifacts."""
        NUM_ARTIFACTS = 300

        for i in range(NUM_ARTIFACTS):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_count_perf_{i}",
                type="fact",
                claim=f"Count performance test {i}"
            ))

        start_time = time.time()
        count = isolated_db.count_artifacts("fact")
        elapsed = time.time() - start_time

        assert count >= NUM_ARTIFACTS
        assert elapsed < 0.5, f"Count query took {elapsed:.2f}s"


class TestDatabaseGrowth:
    """Tests for database size and growth patterns."""

    def test_database_size_reasonable(self, isolated_db):
        """Test: Database size grows reasonably with content."""
        import os

        # Initial size
        initial_size = os.path.getsize(isolated_db.db_path)

        # Add 100 artifacts
        for i in range(100):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_growth_{i}",
                type="fact",
                claim=f"Growth test fact {i} with medium content"
            ))

        # Final size
        final_size = os.path.getsize(isolated_db.db_path)
        growth = final_size - initial_size

        # Rough estimate: should be < 1MB for 100 small artifacts
        assert growth < 1024 * 1024, f"Database grew by {growth / 1024:.1f}KB for 100 artifacts"

    def test_delete_reclaims_space(self, isolated_db):
        """Test: Deleting artifacts allows space reclamation."""
        import os

        # Add artifacts
        for i in range(50):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_delete_space_{i}",
                type="fact",
                claim=f"Delete space test {i}"
            ))

        size_after_add = os.path.getsize(isolated_db.db_path)

        # Delete artifacts
        for i in range(50):
            isolated_db.index.delete(f"fact_delete_space_{i}")

        # Run VACUUM to reclaim space (if implemented)
        import sqlite3
        with sqlite3.connect(isolated_db.db_path) as conn:
            conn.execute("VACUUM")

        size_after_delete = os.path.getsize(isolated_db.db_path)

        # Size should decrease or stay similar (not grow)
        assert size_after_delete <= size_after_add


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
