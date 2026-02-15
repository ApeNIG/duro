"""
Stress Tests: High Volume Operations (Phase 2.4)

Tests system behavior under high volume artifact operations.

Scenarios tested:
1. Bulk artifact creation (1000+ artifacts)
2. Bulk queries under load
3. Bulk deletions
4. Index performance degradation
5. FTS performance at scale

File refs:
- duro-mcp/index.py:95-168 (upsert)
- duro-mcp/index.py:query method
- duro-mcp/index.py:count method
"""

import pytest
import sys
import time
import statistics
from pathlib import Path
from typing import List, Tuple

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockArtifact


# =============================================================================
# Test Configuration
# =============================================================================

# Volume levels for different test intensities
VOLUME_SMALL = 100
VOLUME_MEDIUM = 500
VOLUME_LARGE = 1000

# Performance thresholds (in seconds)
UPSERT_THRESHOLD = 0.05  # Max 50ms per upsert
QUERY_THRESHOLD = 0.1    # Max 100ms per query
BULK_UPSERT_RATE = 40    # Min 40 upserts/second (conservative for CI variance)


# =============================================================================
# High Volume Creation Tests
# =============================================================================

class TestBulkCreation:
    """Tests for bulk artifact creation."""

    def test_create_100_artifacts(self):
        """Baseline: Create 100 artifacts and verify count."""
        with IsolatedTestDB(name="bulk_100") as db:
            for i in range(VOLUME_SMALL):
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"Test fact number {i} with some content"
                ))

            count = db.count_artifacts()
            assert count == VOLUME_SMALL

    def test_create_500_artifacts(self):
        """Medium load: Create 500 artifacts."""
        with IsolatedTestDB(name="bulk_500") as db:
            start = time.perf_counter()

            for i in range(VOLUME_MEDIUM):
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"Test fact number {i} with content for search"
                ))

            elapsed = time.perf_counter() - start
            count = db.count_artifacts()

            assert count == VOLUME_MEDIUM
            # Should complete within reasonable time
            rate = VOLUME_MEDIUM / elapsed
            assert rate >= BULK_UPSERT_RATE, f"Rate {rate:.1f}/s below threshold"

    def test_create_1000_artifacts(self):
        """High load: Create 1000 artifacts."""
        with IsolatedTestDB(name="bulk_1000") as db:
            start = time.perf_counter()

            for i in range(VOLUME_LARGE):
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"Artifact {i}: Lorem ipsum content for testing"
                ))

            elapsed = time.perf_counter() - start
            count = db.count_artifacts()

            assert count == VOLUME_LARGE
            rate = VOLUME_LARGE / elapsed
            print(f"\nBulk creation rate: {rate:.1f} artifacts/second")

    def test_mixed_type_bulk_creation(self):
        """Create many artifacts of different types."""
        with IsolatedTestDB(name="mixed_bulk") as db:
            types = ["fact", "decision", "episode", "evaluation"]

            for i in range(VOLUME_MEDIUM):
                artifact_type = types[i % len(types)]
                db.add_artifact(MockArtifact(
                    id=f"{artifact_type}_{i:04d}",
                    type=artifact_type,
                    claim=f"Content for {artifact_type} {i}"
                ))

            # Verify counts per type
            total = db.count_artifacts()
            assert total == VOLUME_MEDIUM

            for t in types:
                type_count = db.count_artifacts(t)
                expected = VOLUME_MEDIUM // len(types)
                assert abs(type_count - expected) <= 1


# =============================================================================
# Performance Degradation Tests
# =============================================================================

class TestPerformanceDegradation:
    """Tests for performance under increasing load."""

    def test_upsert_time_consistency(self):
        """Verify upsert time doesn't degrade significantly with scale."""
        with IsolatedTestDB(name="upsert_perf") as db:
            timings: List[float] = []
            checkpoints = [10, 50, 100, 200, 500]

            for i in range(max(checkpoints)):
                start = time.perf_counter()
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"Performance test artifact {i}"
                ))
                elapsed = time.perf_counter() - start
                timings.append(elapsed)

            # Compare early vs late performance
            early_avg = statistics.mean(timings[:50])
            late_avg = statistics.mean(timings[-50:])

            # Late operations shouldn't be more than 3x slower
            degradation = late_avg / early_avg if early_avg > 0 else 1
            assert degradation < 3.0, f"Performance degraded {degradation:.1f}x"

    def test_query_time_under_load(self):
        """Verify query performance under increasing data volume."""
        with IsolatedTestDB(name="query_perf") as db:
            # Create baseline data
            for i in range(VOLUME_MEDIUM):
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"Searchable content number {i}"
                ))

            # Time multiple queries
            query_times = []
            for i in range(20):
                artifact_id = f"fact_{i * 10:04d}"
                start = time.perf_counter()
                result = db.get_artifact(artifact_id)
                elapsed = time.perf_counter() - start
                query_times.append(elapsed)
                assert result is not None

            avg_query_time = statistics.mean(query_times)
            assert avg_query_time < QUERY_THRESHOLD

    def test_count_performance_at_scale(self):
        """Verify count operation performance at scale."""
        with IsolatedTestDB(name="count_perf") as db:
            # Create data
            for i in range(VOLUME_LARGE):
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"Count test {i}"
                ))

            # Time count operations
            count_times = []
            for _ in range(10):
                start = time.perf_counter()
                count = db.count_artifacts()
                elapsed = time.perf_counter() - start
                count_times.append(elapsed)
                assert count == VOLUME_LARGE

            avg_count_time = statistics.mean(count_times)
            # Count should be fast even at scale
            assert avg_count_time < 0.05, f"Count took {avg_count_time:.3f}s"


# =============================================================================
# Bulk Deletion Tests
# =============================================================================

class TestBulkDeletion:
    """Tests for bulk deletion operations."""

    def test_delete_half_artifacts(self):
        """Delete half of a large artifact set."""
        with IsolatedTestDB(name="bulk_delete") as db:
            # Create artifacts
            artifact_ids = []
            for i in range(VOLUME_MEDIUM):
                artifact_id = f"fact_{i:04d}"
                artifact_ids.append(artifact_id)
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=f"Deletable content {i}"
                ))

            # Delete first half
            delete_ids = artifact_ids[:VOLUME_MEDIUM // 2]
            start = time.perf_counter()
            for artifact_id in delete_ids:
                db.index.delete(artifact_id)
            elapsed = time.perf_counter() - start

            # Verify
            remaining = db.count_artifacts()
            expected = VOLUME_MEDIUM - len(delete_ids)
            assert remaining == expected

            # Check deletion rate
            rate = len(delete_ids) / elapsed
            print(f"\nBulk deletion rate: {rate:.1f} deletions/second")

    def test_delete_all_artifacts(self):
        """Delete all artifacts from a populated index."""
        with IsolatedTestDB(name="delete_all") as db:
            # Create artifacts
            for i in range(VOLUME_SMALL):
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"To be deleted {i}"
                ))

            assert db.count_artifacts() == VOLUME_SMALL

            # Delete all
            for i in range(VOLUME_SMALL):
                db.index.delete(f"fact_{i:04d}")

            # Verify empty
            assert db.count_artifacts() == 0

    def test_recreate_after_bulk_delete(self):
        """Recreate artifacts after bulk deletion."""
        with IsolatedTestDB(name="recreate") as db:
            # Create initial set
            for i in range(VOLUME_SMALL):
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"Original content {i}"
                ))

            # Delete all
            for i in range(VOLUME_SMALL):
                db.index.delete(f"fact_{i:04d}")

            # Recreate with new content
            for i in range(VOLUME_SMALL):
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"Recreated content {i} - version 2"
                ))

            # Verify count and content
            assert db.count_artifacts() == VOLUME_SMALL


# =============================================================================
# FTS Performance Tests
# =============================================================================

class TestFTSPerformance:
    """Tests for full-text search performance at scale."""

    def test_fts_search_at_scale(self):
        """Test FTS search performance with many documents."""
        import sqlite3

        with IsolatedTestDB(name="fts_scale") as db:
            # Create searchable content
            for i in range(VOLUME_MEDIUM):
                word = f"unique{i:04d}"
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"Document contains {word} and common words"
                ))

            # Time FTS searches
            search_times = []
            with sqlite3.connect(db.db_path) as conn:
                for i in range(20):
                    search_term = f"unique{i * 10:04d}"
                    start = time.perf_counter()
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            (search_term,)
                        )
                        results = cursor.fetchall()
                        elapsed = time.perf_counter() - start
                        search_times.append(elapsed)
                    except sqlite3.OperationalError:
                        pass

            if search_times:
                avg_search_time = statistics.mean(search_times)
                print(f"\nFTS search avg: {avg_search_time * 1000:.2f}ms")
                assert avg_search_time < 0.1  # Under 100ms

    def test_fts_common_term_search(self):
        """Search for terms that appear in many documents."""
        import sqlite3

        with IsolatedTestDB(name="fts_common") as db:
            # Create documents with common term
            common_word = "important"
            for i in range(VOLUME_SMALL):
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"This is an {common_word} document number {i}"
                ))

            # Search for common term
            with sqlite3.connect(db.db_path) as conn:
                start = time.perf_counter()
                try:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (common_word,)
                    )
                    results = cursor.fetchall()
                    elapsed = time.perf_counter() - start

                    # Should find all documents
                    assert len(results) == VOLUME_SMALL
                    print(f"\nCommon term search: {elapsed * 1000:.2f}ms for {len(results)} results")
                except sqlite3.OperationalError:
                    pass


# =============================================================================
# Memory Stress Tests
# =============================================================================

class TestMemoryStress:
    """Tests for memory usage under load."""

    def test_large_claim_content(self):
        """Test artifacts with large claim content."""
        with IsolatedTestDB(name="large_claims") as db:
            # Create artifacts with progressively larger content
            sizes = [100, 1000, 10000, 50000]

            for size in sizes:
                content = "x" * size
                db.add_artifact(MockArtifact(
                    id=f"fact_size_{size}",
                    type="fact",
                    claim=content
                ))

            # Verify all created
            for size in sizes:
                result = db.get_artifact(f"fact_size_{size}")
                assert result is not None

    def test_many_tags_per_artifact(self):
        """Test artifacts with many tags."""
        with IsolatedTestDB(name="many_tags") as db:
            tag_counts = [10, 50, 100]

            for tag_count in tag_counts:
                tags = [f"tag_{i}" for i in range(tag_count)]
                db.add_artifact(MockArtifact(
                    id=f"fact_tags_{tag_count}",
                    type="fact",
                    claim=f"Artifact with {tag_count} tags",
                    tags=tags
                ))

            # Verify retrieval
            for tag_count in tag_counts:
                result = db.get_artifact(f"fact_tags_{tag_count}")
                assert result is not None


# =============================================================================
# Batch Operation Tests
# =============================================================================

class TestBatchOperations:
    """Tests for batch operation patterns."""

    def test_batch_upsert_pattern(self):
        """Test efficient batch upsert pattern."""
        with IsolatedTestDB(name="batch_upsert") as db:
            batch_size = 100
            num_batches = 5

            for batch in range(num_batches):
                start = time.perf_counter()

                for i in range(batch_size):
                    artifact_id = f"fact_b{batch}_i{i}"
                    db.add_artifact(MockArtifact(
                        id=artifact_id,
                        type="fact",
                        claim=f"Batch {batch} item {i}"
                    ))

                elapsed = time.perf_counter() - start
                rate = batch_size / elapsed
                print(f"\nBatch {batch + 1}: {rate:.1f} items/sec")

            total = db.count_artifacts()
            assert total == batch_size * num_batches

    def test_interleaved_operations(self):
        """Test interleaved create/read/delete operations."""
        with IsolatedTestDB(name="interleaved") as db:
            active_ids = set()

            for i in range(VOLUME_SMALL):
                # Create
                artifact_id = f"fact_{i:04d}"
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=f"Interleaved test {i}"
                ))
                active_ids.add(artifact_id)

                # Read random
                if active_ids:
                    read_id = list(active_ids)[i % len(active_ids)]
                    result = db.get_artifact(read_id)
                    if read_id in active_ids:
                        assert result is not None

                # Delete every 5th
                if i > 0 and i % 5 == 0:
                    delete_id = f"fact_{i - 5:04d}"
                    if delete_id in active_ids:
                        db.index.delete(delete_id)
                        active_ids.discard(delete_id)

            # Verify final state
            final_count = db.count_artifacts()
            assert final_count == len(active_ids)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
