"""
Test: Orphan Embedding Accumulation (Priority: HIGH)

Tests that orphan embeddings don't accumulate when artifacts are deleted
faster than prune operations run.

Risk: If artifacts are deleted rapidly without corresponding prune operations,
orphan embeddings can accumulate indefinitely, wasting storage and potentially
corrupting search results with stale data.

File refs:
- duro-mcp/index.py:868-930 (prune_orphan_embeddings)
- duro-mcp/index.py:772-827 (upsert_embedding)
- skills/ops/duro_bash_ops.py:149 (prune CLI)
"""

import pytest
import sys
import time
import sqlite3
from pathlib import Path
from typing import List, Dict

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact


class TestOrphanAccumulation:
    """Tests for orphan embedding accumulation scenarios."""

    def test_single_delete_creates_orphan(self, isolated_db, mock_embedder):
        """Baseline: Deleting an artifact leaves an orphan embedding."""
        artifact_id = "fact_orphan_single"
        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="This artifact will be deleted"
        ))

        # Create embedding
        embedding = mock_embedder.embed("This artifact will be deleted")
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash="hash_orphan_single",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        # Verify embedding exists
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state is not None

        # Delete artifact (but not embedding)
        isolated_db.index.delete(artifact_id)

        # Embedding state should still exist (orphan)
        orphan_count = isolated_db.index.count_orphan_embeddings()
        assert orphan_count == 1

    def test_rapid_delete_accumulation(self, isolated_db, mock_embedder):
        """
        Test: Rapidly deleting many artifacts accumulates orphans.

        Simulates scenario where artifacts are created/deleted in bursts
        without intervening prune operations.
        """
        NUM_ARTIFACTS = 20

        # Create and embed artifacts
        for i in range(NUM_ARTIFACTS):
            artifact_id = f"fact_rapid_{i}"
            isolated_db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=f"Rapid delete test fact {i}"
            ))

        # Embed first one to check availability
        embedding = mock_embedder.embed("Rapid delete test fact 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_rapid_0",
            embedding=embedding,
            content_hash="hash_rapid_0",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        # Embed remaining
        for i in range(1, NUM_ARTIFACTS):
            embedding = mock_embedder.embed(f"Rapid delete test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_rapid_{i}",
                embedding=embedding,
                content_hash=f"hash_rapid_{i}",
                model_name=mock_embedder.model_name
            )

        # Rapidly delete all artifacts
        for i in range(NUM_ARTIFACTS):
            isolated_db.index.delete(f"fact_rapid_{i}")

        # All should be orphans now
        orphan_count = isolated_db.index.count_orphan_embeddings()
        assert orphan_count == NUM_ARTIFACTS, f"Expected {NUM_ARTIFACTS} orphans, got {orphan_count}"

    def test_prune_clears_all_orphans(self, isolated_db, mock_embedder):
        """Test: Single prune operation clears all accumulated orphans."""
        NUM_ARTIFACTS = 15

        # Create, embed, then delete artifacts
        for i in range(NUM_ARTIFACTS):
            artifact_id = f"fact_prune_{i}"
            isolated_db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=f"Prune test fact {i}"
            ))

        # Check availability with first embedding
        embedding = mock_embedder.embed("Prune test fact 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_prune_0",
            embedding=embedding,
            content_hash="hash_prune_0",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        # Embed remaining
        for i in range(1, NUM_ARTIFACTS):
            embedding = mock_embedder.embed(f"Prune test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_prune_{i}",
                embedding=embedding,
                content_hash=f"hash_prune_{i}",
                model_name=mock_embedder.model_name
            )

        # Delete all
        for i in range(NUM_ARTIFACTS):
            isolated_db.index.delete(f"fact_prune_{i}")

        # Verify orphans exist
        orphan_count = isolated_db.index.count_orphan_embeddings()
        assert orphan_count == NUM_ARTIFACTS

        # Run prune
        result = isolated_db.index.prune_orphan_embeddings()

        # Verify all orphans cleared
        orphan_count_after = isolated_db.index.count_orphan_embeddings()
        assert orphan_count_after == 0, f"Expected 0 orphans after prune, got {orphan_count_after}"

    def test_interleaved_create_delete_prune(self, isolated_db, mock_embedder):
        """
        Test: Interleaved create/delete/prune operations maintain consistency.

        Simulates realistic usage pattern where operations happen in mixed order.
        """
        # Phase 1: Create and embed 5 artifacts
        for i in range(5):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_interleave_{i}",
                type="fact",
                claim=f"Interleave test fact {i}"
            ))

        embedding = mock_embedder.embed("Interleave test fact 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_interleave_0",
            embedding=embedding,
            content_hash="hash_interleave_0",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        for i in range(1, 5):
            embedding = mock_embedder.embed(f"Interleave test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_interleave_{i}",
                embedding=embedding,
                content_hash=f"hash_interleave_{i}",
                model_name=mock_embedder.model_name
            )

        # Phase 2: Delete 2 artifacts
        isolated_db.index.delete("fact_interleave_0")
        isolated_db.index.delete("fact_interleave_2")

        # Should have 2 orphans
        assert isolated_db.index.count_orphan_embeddings() == 2

        # Phase 3: Create 3 more artifacts while orphans exist
        for i in range(5, 8):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_interleave_{i}",
                type="fact",
                claim=f"Interleave test fact {i}"
            ))
            embedding = mock_embedder.embed(f"Interleave test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_interleave_{i}",
                embedding=embedding,
                content_hash=f"hash_interleave_{i}",
                model_name=mock_embedder.model_name
            )

        # Still 2 orphans (new ones have artifacts)
        assert isolated_db.index.count_orphan_embeddings() == 2

        # Phase 4: Prune
        isolated_db.index.prune_orphan_embeddings()

        # Should be 0 orphans
        assert isolated_db.index.count_orphan_embeddings() == 0

        # Phase 5: Verify remaining artifacts still have embeddings
        for i in [1, 3, 4, 5, 6, 7]:  # 0 and 2 were deleted
            state = isolated_db.index.get_embedding_state(f"fact_interleave_{i}")
            assert state is not None, f"Embedding for fact_interleave_{i} was incorrectly pruned"


class TestOrphanDetection:
    """Tests for orphan detection accuracy."""

    def test_count_orphan_embeddings_accuracy(self, isolated_db, mock_embedder):
        """Test: count_orphan_embeddings returns accurate count."""
        # Create 10 artifacts with embeddings
        for i in range(10):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_count_{i}",
                type="fact",
                claim=f"Count test fact {i}"
            ))

        embedding = mock_embedder.embed("Count test fact 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_count_0",
            embedding=embedding,
            content_hash="hash_count_0",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        for i in range(1, 10):
            embedding = mock_embedder.embed(f"Count test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_count_{i}",
                embedding=embedding,
                content_hash=f"hash_count_{i}",
                model_name=mock_embedder.model_name
            )

        # No orphans yet
        assert isolated_db.index.count_orphan_embeddings() == 0

        # Delete specific artifacts: 0, 3, 5, 7, 9 (5 total)
        for i in [0, 3, 5, 7, 9]:
            isolated_db.index.delete(f"fact_count_{i}")

        # Should have exactly 5 orphans
        assert isolated_db.index.count_orphan_embeddings() == 5

    def test_orphan_detection_with_mixed_types(self, isolated_db, mock_embedder):
        """Test: Orphan detection works across different artifact types."""
        # Create mixed artifact types
        artifacts = [
            MockArtifact(id="fact_mixed_1", type="fact", claim="A fact"),
            MockArtifact(id="decision_mixed_1", type="decision", claim="A decision"),
            MockArtifact(id="fact_mixed_2", type="fact", claim="Another fact"),
        ]

        for artifact in artifacts:
            isolated_db.add_artifact(artifact)

        # Embed all
        embedding = mock_embedder.embed("A fact")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_mixed_1",
            embedding=embedding,
            content_hash="hash_fact_1",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        isolated_db.index.upsert_embedding(
            artifact_id="decision_mixed_1",
            embedding=mock_embedder.embed("A decision"),
            content_hash="hash_decision_1",
            model_name=mock_embedder.model_name
        )
        isolated_db.index.upsert_embedding(
            artifact_id="fact_mixed_2",
            embedding=mock_embedder.embed("Another fact"),
            content_hash="hash_fact_2",
            model_name=mock_embedder.model_name
        )

        # Delete the decision
        isolated_db.index.delete("decision_mixed_1")

        # Should detect 1 orphan regardless of type
        assert isolated_db.index.count_orphan_embeddings() == 1


class TestOrphanPruneEdgeCases:
    """Tests for edge cases in orphan pruning."""

    def test_prune_empty_database(self, isolated_db):
        """Test: Prune on empty database doesn't error."""
        # Should not raise any errors
        result = isolated_db.index.prune_orphan_embeddings()
        assert result is not None

    def test_prune_no_orphans(self, isolated_db, mock_embedder):
        """Test: Prune when no orphans exist is safe."""
        # Create artifact with embedding
        isolated_db.add_artifact(MockArtifact(
            id="fact_no_orphan",
            type="fact",
            claim="No orphan test"
        ))

        embedding = mock_embedder.embed("No orphan test")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_no_orphan",
            embedding=embedding,
            content_hash="hash_no_orphan",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        # Prune should succeed and not delete anything
        result = isolated_db.index.prune_orphan_embeddings()

        # Embedding should still exist
        state = isolated_db.index.get_embedding_state("fact_no_orphan")
        assert state is not None

    def test_double_prune_idempotent(self, isolated_db, mock_embedder):
        """Test: Running prune twice is idempotent."""
        # Create and delete artifact
        isolated_db.add_artifact(MockArtifact(
            id="fact_double_prune",
            type="fact",
            claim="Double prune test"
        ))

        embedding = mock_embedder.embed("Double prune test")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_double_prune",
            embedding=embedding,
            content_hash="hash_double_prune",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        isolated_db.index.delete("fact_double_prune")

        # First prune
        result1 = isolated_db.index.prune_orphan_embeddings()
        count1 = isolated_db.index.count_orphan_embeddings()

        # Second prune
        result2 = isolated_db.index.prune_orphan_embeddings()
        count2 = isolated_db.index.count_orphan_embeddings()

        # Both should result in 0 orphans
        assert count1 == 0
        assert count2 == 0

    def test_recreate_deleted_artifact_not_orphan(self, isolated_db, mock_embedder):
        """
        Test: Re-creating an artifact with same ID removes orphan status.

        If an artifact is deleted then re-created with same ID before prune,
        the embedding should no longer be considered orphan.
        """
        artifact_id = "fact_recreate"

        # Create, embed, delete
        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Original content"
        ))

        embedding = mock_embedder.embed("Original content")
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash="hash_original",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        isolated_db.index.delete(artifact_id)

        # Should be 1 orphan
        assert isolated_db.index.count_orphan_embeddings() == 1

        # Re-create artifact with same ID
        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="New content"
        ))

        # Should no longer be orphan (artifact exists again)
        assert isolated_db.index.count_orphan_embeddings() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
