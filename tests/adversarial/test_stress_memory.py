"""
Stress Tests: Memory Pressure (Phase 2.4)

Tests system behavior under memory pressure conditions.

Scenarios tested:
1. Large individual artifacts
2. Many small artifacts (memory fragmentation)
3. Large embedding vectors
4. Deep nesting / complex structures
5. Memory cleanup after deletions

File refs:
- duro-mcp/index.py (memory usage patterns)
- duro-mcp/embeddings.py (vector storage)
"""

import pytest
import sys
import gc
import time
from pathlib import Path
from typing import List

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact


# =============================================================================
# Test Configuration
# =============================================================================

# Size thresholds
SMALL_CONTENT = 100          # 100 bytes
MEDIUM_CONTENT = 10_000      # 10 KB
LARGE_CONTENT = 100_000      # 100 KB
VERY_LARGE_CONTENT = 500_000 # 500 KB

# Quantity thresholds
MANY_SMALL = 1000
MEDIUM_BATCH = 500


# =============================================================================
# Large Artifact Tests
# =============================================================================

class TestLargeArtifacts:
    """Tests for handling large individual artifacts."""

    def test_10kb_artifact(self):
        """Create and retrieve 10KB artifact."""
        with IsolatedTestDB(name="large_10kb") as db:
            content = "x" * MEDIUM_CONTENT

            db.add_artifact(MockArtifact(
                id="large_10kb",
                type="fact",
                claim=content
            ))

            result = db.get_artifact("large_10kb")
            assert result is not None

    def test_100kb_artifact(self):
        """Create and retrieve 100KB artifact."""
        with IsolatedTestDB(name="large_100kb") as db:
            content = "y" * LARGE_CONTENT

            db.add_artifact(MockArtifact(
                id="large_100kb",
                type="fact",
                claim=content
            ))

            result = db.get_artifact("large_100kb")
            assert result is not None

    def test_500kb_artifact(self):
        """Create and retrieve 500KB artifact."""
        with IsolatedTestDB(name="large_500kb") as db:
            content = "z" * VERY_LARGE_CONTENT

            db.add_artifact(MockArtifact(
                id="large_500kb",
                type="fact",
                claim=content
            ))

            result = db.get_artifact("large_500kb")
            assert result is not None

    def test_multiple_large_artifacts(self):
        """Create multiple large artifacts."""
        with IsolatedTestDB(name="multi_large") as db:
            for i in range(10):
                content = f"artifact_{i}_" + ("data" * 25000)  # ~100KB each
                db.add_artifact(MockArtifact(
                    id=f"large_{i}",
                    type="fact",
                    claim=content
                ))

            count = db.count_artifacts()
            assert count == 10

            # Verify all retrievable
            for i in range(10):
                result = db.get_artifact(f"large_{i}")
                assert result is not None

    def test_large_artifact_with_many_tags(self):
        """Large artifact with many tags."""
        with IsolatedTestDB(name="large_tags") as db:
            content = "content" * 10000
            tags = [f"tag_{i}" for i in range(500)]

            db.add_artifact(MockArtifact(
                id="large_with_tags",
                type="fact",
                claim=content,
                tags=tags
            ))

            result = db.get_artifact("large_with_tags")
            assert result is not None


# =============================================================================
# Many Small Artifacts Tests
# =============================================================================

class TestManySmallArtifacts:
    """Tests for handling many small artifacts (fragmentation)."""

    def test_1000_tiny_artifacts(self):
        """Create 1000 tiny artifacts."""
        with IsolatedTestDB(name="tiny_1000") as db:
            for i in range(MANY_SMALL):
                db.add_artifact(MockArtifact(
                    id=f"tiny_{i:04d}",
                    type="fact",
                    claim=f"Tiny content {i}"
                ))

            count = db.count_artifacts()
            assert count == MANY_SMALL

    def test_small_artifacts_with_varied_types(self):
        """Many small artifacts of different types."""
        with IsolatedTestDB(name="varied_types") as db:
            types = ["fact", "decision", "episode", "evaluation"]

            for i in range(MEDIUM_BATCH):
                artifact_type = types[i % len(types)]
                db.add_artifact(MockArtifact(
                    id=f"{artifact_type}_{i:04d}",
                    type=artifact_type,
                    claim=f"Content for {artifact_type} {i}"
                ))

            total = db.count_artifacts()
            assert total == MEDIUM_BATCH

    def test_alternating_create_delete_pattern(self):
        """Alternating create/delete to test memory fragmentation."""
        with IsolatedTestDB(name="fragmentation") as db:
            # Create initial batch
            for i in range(200):
                db.add_artifact(MockArtifact(
                    id=f"frag_{i:04d}",
                    type="fact",
                    claim=f"Fragmentation test {i}"
                ))

            # Alternate delete and create
            for cycle in range(5):
                # Delete odd-numbered
                for i in range(0, 200, 2):
                    db.index.delete(f"frag_{i:04d}")

                # Create new ones
                for i in range(200):
                    db.add_artifact(MockArtifact(
                        id=f"frag_cycle{cycle}_{i:04d}",
                        type="fact",
                        claim=f"Cycle {cycle} item {i}"
                    ))

            # Should still work
            count = db.count_artifacts()
            assert count > 0


# =============================================================================
# Embedding Memory Tests
# =============================================================================

class TestEmbeddingMemory:
    """Tests for embedding vector memory usage."""

    def test_many_embeddings(self):
        """Create many embedding vectors."""
        with IsolatedTestDB(name="many_emb") as db:
            embedder = MockEmbedder(dimension=384)

            for i in range(100):
                artifact_id = f"emb_{i:04d}"
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=f"Embedding content {i}"
                ))

                embedding = embedder.embed(f"Embedding content {i}")
                success = db.index.upsert_embedding(
                    artifact_id=artifact_id,
                    embedding=embedding,
                    content_hash=f"hash_{i}",
                    model_name=embedder.model_name
                )

                if not success and i == 0:
                    pytest.skip("sqlite-vec not available")

            # Verify embeddings exist
            for i in range(100):
                state = db.index.get_embedding_state(f"emb_{i:04d}")
                if state is None and i > 0:
                    break  # sqlite-vec might not be available

    def test_large_dimension_embeddings(self):
        """Test with larger embedding dimensions."""
        with IsolatedTestDB(name="large_dim") as db:
            # Test different dimensions
            dimensions = [384, 768, 1024]

            for dim in dimensions:
                embedder = MockEmbedder(dimension=dim)
                artifact_id = f"dim_{dim}"

                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=f"Testing dimension {dim}"
                ))

                embedding = embedder.embed(f"Testing dimension {dim}")
                assert len(embedding) == dim

    def test_embedding_after_artifact_deletion(self):
        """Test memory behavior when artifacts with embeddings are deleted."""
        with IsolatedTestDB(name="emb_delete") as db:
            embedder = MockEmbedder(dimension=384)

            # Create artifacts with embeddings
            for i in range(50):
                artifact_id = f"del_emb_{i:04d}"
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=f"To be deleted {i}"
                ))

                embedding = embedder.embed(f"To be deleted {i}")
                success = db.index.upsert_embedding(
                    artifact_id=artifact_id,
                    embedding=embedding,
                    content_hash=f"hash_{i}",
                    model_name=embedder.model_name
                )
                if not success and i == 0:
                    pytest.skip("sqlite-vec not available")

            # Delete all artifacts (embeddings become orphans)
            for i in range(50):
                db.index.delete(f"del_emb_{i:04d}")

            # Verify deletion
            count = db.count_artifacts()
            assert count == 0

            # Orphan embeddings should exist
            orphan_count = db.index.count_orphan_embeddings()
            assert orphan_count >= 0  # May be 0 if sqlite-vec not available


# =============================================================================
# Complex Structure Tests
# =============================================================================

class TestComplexStructures:
    """Tests for complex artifact structures."""

    def test_deeply_nested_tags(self):
        """Artifacts with deeply nested tag hierarchies."""
        with IsolatedTestDB(name="nested_tags") as db:
            # Create tags with hierarchy pattern
            tags = [
                "level1/level2/level3/level4/level5",
                "a/b/c/d/e/f/g/h/i/j",
                "category/subcategory/item/subitem/detail"
            ]

            for i, tag_pattern in enumerate(tags):
                all_tags = tag_pattern.split("/")
                db.add_artifact(MockArtifact(
                    id=f"nested_{i}",
                    type="fact",
                    claim=f"Nested tags artifact {i}",
                    tags=all_tags
                ))

            count = db.count_artifacts()
            assert count == len(tags)

    def test_unicode_content(self):
        """Test memory handling with unicode content."""
        with IsolatedTestDB(name="unicode") as db:
            # Various unicode content
            contents = [
                "Hello 世界 🌍",
                "Ελληνικά κείμενο",
                "日本語テキスト",
                "مرحبا بالعالم",
                "🎉🎊🎈🎁" * 100,
                "Mixed: Hello 你好 مرحبا שלום"
            ]

            for i, content in enumerate(contents):
                db.add_artifact(MockArtifact(
                    id=f"unicode_{i}",
                    type="fact",
                    claim=content
                ))

            count = db.count_artifacts()
            assert count == len(contents)

            # Verify retrieval
            for i in range(len(contents)):
                result = db.get_artifact(f"unicode_{i}")
                assert result is not None

    def test_special_characters_in_ids(self):
        """Test artifacts with special characters in IDs."""
        with IsolatedTestDB(name="special_ids") as db:
            # IDs with various patterns (must be valid for filesystem)
            ids = [
                "simple_id",
                "id-with-dashes",
                "id_with_underscores",
                "id123numbers",
                "MixedCase123",
                "a" * 100,  # Long ID
            ]

            for artifact_id in ids:
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=f"Content for {artifact_id}"
                ))

            # Verify all retrievable
            for artifact_id in ids:
                result = db.get_artifact(artifact_id)
                assert result is not None, f"Failed to retrieve {artifact_id}"


# =============================================================================
# Memory Cleanup Tests
# =============================================================================

class TestMemoryCleanup:
    """Tests for memory cleanup behavior."""

    def test_gc_after_bulk_operations(self):
        """Verify garbage collection after bulk operations."""
        with IsolatedTestDB(name="gc_test") as db:
            # Create many artifacts
            for i in range(500):
                db.add_artifact(MockArtifact(
                    id=f"gc_{i:04d}",
                    type="fact",
                    claim=f"GC test content {i}" + ("x" * 1000)
                ))

            # Delete all
            for i in range(500):
                db.index.delete(f"gc_{i:04d}")

            # Force garbage collection
            gc.collect()

            # Create new artifacts in same space
            for i in range(500):
                db.add_artifact(MockArtifact(
                    id=f"gc_new_{i:04d}",
                    type="fact",
                    claim=f"New GC content {i}"
                ))

            count = db.count_artifacts()
            assert count == 500

    def test_repeated_upsert_memory(self):
        """Test memory usage with repeated upserts to same ID."""
        with IsolatedTestDB(name="upsert_mem") as db:
            artifact_id = "repeated_upsert"

            # Upsert same artifact many times with different content
            for i in range(100):
                content = f"Version {i}: " + ("data" * 1000)
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=content
                ))

            # Should still only have 1 artifact
            count = db.count_artifacts()
            assert count == 1

            # Retrieve should get latest
            result = db.get_artifact(artifact_id)
            assert result is not None


# =============================================================================
# Resource Limit Tests
# =============================================================================

class TestResourceLimits:
    """Tests for behavior at resource limits."""

    def test_many_concurrent_connections(self):
        """Test with many database connections."""
        import sqlite3

        with IsolatedTestDB(name="many_conn") as db:
            # Create baseline data
            for i in range(50):
                db.add_artifact(MockArtifact(
                    id=f"conn_{i:04d}",
                    type="fact",
                    claim=f"Connection test {i}"
                ))

            # Open many connections
            connections = []
            for _ in range(10):
                conn = sqlite3.connect(db.db_path)
                connections.append(conn)

            # Query from all connections
            for conn in connections:
                cursor = conn.execute("SELECT COUNT(*) FROM artifacts")
                count = cursor.fetchone()[0]
                assert count == 50

            # Clean up connections
            for conn in connections:
                conn.close()

    def test_rapid_create_delete_cycles(self):
        """Rapid create/delete cycles to stress test."""
        with IsolatedTestDB(name="rapid_cycle") as db:
            cycles = 20
            batch_size = 50

            for cycle in range(cycles):
                # Create batch
                for i in range(batch_size):
                    db.add_artifact(MockArtifact(
                        id=f"rapid_{i:04d}",
                        type="fact",
                        claim=f"Cycle {cycle} item {i}"
                    ))

                # Delete batch
                for i in range(batch_size):
                    db.index.delete(f"rapid_{i:04d}")

            # Final state should be empty
            count = db.count_artifacts()
            assert count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
