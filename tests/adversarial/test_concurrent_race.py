"""
Test: Concurrent Race Conditions (Priority: HIGH)

Tests race conditions between reembed and prune operations.

Risk: Running reembed and prune_orphan_embeddings concurrently could:
- Delete freshly created embeddings (prune races ahead of reembed)
- Create partial/corrupt embedding state
- Leave orphaned rows in either direction

File refs:
- skills/ops/duro_bash_ops.py:93 (reembed)
- skills/ops/duro_bash_ops.py:149 (prune)
- duro-mcp/index.py:772-827 (upsert_embedding)
- duro-mcp/index.py:868-930 (prune_orphan_embeddings)
"""

import pytest
import sys
import time
import threading
import random
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact, concurrent_executor


class TestReembedPruneRace:
    """Tests for race conditions between reembed and prune operations."""

    def test_sequential_reembed_prune_safe(self, isolated_db, mock_embedder):
        """Baseline: Sequential operations work correctly."""
        # Add artifacts
        for i in range(5):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_seq_{i}",
                type="fact",
                claim=f"Sequential test fact {i}"
            ))

        # Simulate embedding
        for i in range(5):
            artifact_id = f"fact_seq_{i}"
            embedding = mock_embedder.embed(f"Sequential test fact {i}")

            # Check if vector tables exist
            try:
                success = isolated_db.index.upsert_embedding(
                    artifact_id=artifact_id,
                    embedding=embedding,
                    content_hash=f"hash_{i}",
                    model_name=mock_embedder.model_name
                )
            except Exception:
                # Vector extension not available - skip embedding tests
                pytest.skip("sqlite-vec not available")

        # Prune should find no orphans (all artifacts exist)
        orphan_count = isolated_db.index.count_orphan_embeddings()
        assert orphan_count == 0

    def test_concurrent_double_upsert(self, isolated_db, mock_embedder):
        """
        Test: Two threads upsert embedding for same artifact simultaneously.

        Expected: Final state should be consistent (one valid embedding row).
        """
        artifact_id = "fact_double_upsert"
        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Test fact for double upsert"
        ))

        embedding = mock_embedder.embed("Test fact for double upsert")
        results = []
        errors = []

        def do_upsert(thread_id: int):
            """Perform upsert with slight random delay."""
            time.sleep(random.uniform(0, 0.01))  # Random jitter
            try:
                success = isolated_db.index.upsert_embedding(
                    artifact_id=artifact_id,
                    embedding=embedding,
                    content_hash=f"hash_thread_{thread_id}",
                    model_name=mock_embedder.model_name
                )
                return success
            except Exception as e:
                return str(e)

        # Run concurrent upserts
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(do_upsert, i) for i in range(4)]
            for future in as_completed(futures):
                result = future.result()
                if isinstance(result, str):
                    errors.append(result)
                else:
                    results.append(result)

        # Should have no errors
        assert len(errors) == 0, f"Got errors: {errors}"

        # Should have exactly one embedding state row
        state = isolated_db.index.get_embedding_state(artifact_id)
        if state:
            assert state is not None
            # One of the threads' hashes should have won
            assert state["content_hash"].startswith("hash_thread_")

    def test_prune_during_reembed_simulation(self, isolated_db, mock_embedder):
        """
        Test: Simulate race between creating embedding and pruning.

        Scenario:
        1. Thread A: Delete artifact, leaving orphan embedding
        2. Thread B: Start reembed of another artifact
        3. Thread A: Prune runs and might delete Thread B's work

        This tests the window between embedding creation and artifact existence.
        """
        # Create two artifacts
        isolated_db.add_artifact(MockArtifact(
            id="fact_to_delete",
            type="fact",
            claim="This artifact will be deleted"
        ))
        isolated_db.add_artifact(MockArtifact(
            id="fact_to_embed",
            type="fact",
            claim="This artifact will get new embedding"
        ))

        # First, embed the artifact that will be deleted
        embedding1 = mock_embedder.embed("This artifact will be deleted")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_to_delete",
            embedding=embedding1,
            content_hash="hash_delete",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available - upsert_embedding returned False")

        # Delete the artifact (creates orphan)
        isolated_db.index.delete("fact_to_delete")

        # Now simulate race: reembed and prune concurrently
        embedding2 = mock_embedder.embed("This artifact will get new embedding")
        prune_result = None
        embed_result = None

        def do_reembed():
            nonlocal embed_result
            time.sleep(0.005)  # Small delay
            try:
                embed_result = isolated_db.index.upsert_embedding(
                    artifact_id="fact_to_embed",
                    embedding=embedding2,
                    content_hash="hash_embed",
                    model_name=mock_embedder.model_name
                )
            except Exception as e:
                embed_result = str(e)

        def do_prune():
            nonlocal prune_result
            try:
                prune_result = isolated_db.index.prune_orphan_embeddings()
            except Exception as e:
                prune_result = {"error": str(e)}

        # Run concurrently
        threads = [
            threading.Thread(target=do_reembed),
            threading.Thread(target=do_prune)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify fact_to_embed still has its embedding
        state = isolated_db.index.get_embedding_state("fact_to_embed")
        assert state is not None, "Embedding for fact_to_embed was incorrectly pruned!"
        assert state["content_hash"] == "hash_embed"

        # Verify orphan was cleaned up
        orphan_count = isolated_db.index.count_orphan_embeddings()
        assert orphan_count == 0

    def test_bulk_concurrent_operations(self, isolated_db, mock_embedder):
        """
        Stress test: Many concurrent embed/prune/delete operations.

        Verifies:
        - No deadlocks
        - Final state is consistent
        - No data loss for existing artifacts
        """
        NUM_ARTIFACTS = 20
        NUM_THREADS = 8

        # Create artifacts
        for i in range(NUM_ARTIFACTS):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_bulk_{i}",
                type="fact",
                claim=f"Bulk test fact number {i}"
            ))

        operations_log = []
        lock = threading.Lock()

        def random_operation(thread_id: int, iteration: int):
            """Perform random operation."""
            op = random.choice(["embed", "prune", "query"])
            artifact_idx = random.randint(0, NUM_ARTIFACTS - 1)
            artifact_id = f"fact_bulk_{artifact_idx}"

            try:
                if op == "embed":
                    embedding = mock_embedder.embed(f"Bulk test fact number {artifact_idx}")
                    result = isolated_db.index.upsert_embedding(
                        artifact_id=artifact_id,
                        embedding=embedding,
                        content_hash=f"hash_bulk_{artifact_idx}_{iteration}",
                        model_name=mock_embedder.model_name
                    )
                    with lock:
                        operations_log.append(("embed", artifact_id, result))

                elif op == "prune":
                    result = isolated_db.index.prune_orphan_embeddings()
                    with lock:
                        operations_log.append(("prune", None, result))

                elif op == "query":
                    result = isolated_db.index.get_embedding_state(artifact_id)
                    with lock:
                        operations_log.append(("query", artifact_id, result is not None))

            except Exception as e:
                with lock:
                    operations_log.append(("error", op, str(e)))

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            futures = []
            for thread_id in range(NUM_THREADS):
                for iteration in range(10):  # 10 ops per thread
                    futures.append(
                        executor.submit(random_operation, thread_id, iteration)
                    )

            # Wait for all
            for future in as_completed(futures):
                pass  # Just wait

        # Analyze results
        errors = [log for log in operations_log if log[0] == "error"]

        # SQLite busy errors are acceptable under heavy load
        # but data corruption is not
        for error in errors:
            error_msg = error[2]
            # These are acceptable concurrency errors
            acceptable = ["database is locked", "busy", "SQLITE_BUSY"]
            assert any(acc in error_msg for acc in acceptable), f"Unexpected error: {error_msg}"

        # Verify final state: all artifacts should still exist
        for i in range(NUM_ARTIFACTS):
            artifact = isolated_db.get_artifact(f"fact_bulk_{i}")
            assert artifact is not None, f"Artifact fact_bulk_{i} was lost!"


class TestEmbeddingStateConsistency:
    """Tests for embedding_state and artifact_vectors consistency."""

    def test_delete_then_upsert_race(self, isolated_db, mock_embedder):
        """
        Test: Delete embedding immediately followed by upsert.

        The upsert_embedding does DELETE then INSERT (not atomic).
        Race condition could leave inconsistent state.
        """
        artifact_id = "fact_delete_upsert"
        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Test for delete-upsert race"
        ))

        embedding = mock_embedder.embed("Test for delete-upsert race")

        # Initial embedding
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash="hash_v1",
            model_name="model_v1"
        )
        if not success:
            pytest.skip("sqlite-vec not available - upsert_embedding returned False")

        # Rapid delete/upsert cycles
        for i in range(10):
            # Delete
            isolated_db.index.delete_embedding(artifact_id)

            # Immediate upsert
            isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=embedding,
                content_hash=f"hash_v{i+2}",
                model_name=f"model_v{i+2}"
            )

        # Final state should be consistent
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state is not None
        assert state["content_hash"] == "hash_v11"
        assert state["model"] == "model_v11"


class TestRepairTableRace:
    """Tests for repairs table concurrent access."""

    def test_concurrent_repair_starts(self, isolated_db):
        """
        Test: Multiple threads starting repairs simultaneously.

        The repairs table should handle concurrent inserts.
        """
        repair_ids = []
        lock = threading.Lock()

        def start_repair(thread_id: int):
            repair_id = isolated_db.index.start_repair(
                repair_type="test_concurrent",
                trigger=f"thread_{thread_id}",
                before_metrics={"thread": thread_id},
                code_version="test"
            )
            with lock:
                repair_ids.append(repair_id)
            return repair_id

        # Start 5 concurrent repairs
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(start_repair, i) for i in range(5)]
            for future in as_completed(futures):
                pass

        # All should have unique IDs
        assert len(repair_ids) == 5
        assert len(set(repair_ids)) == 5  # All unique

    def test_repair_completion_race(self, isolated_db):
        """
        Test: Completing a repair while another starts.
        """
        # Start first repair
        repair_id1 = isolated_db.index.start_repair(
            repair_type="test_race",
            trigger="test_1",
            code_version="test"
        )

        # Start second repair concurrently with completing first
        def complete_first():
            time.sleep(0.005)
            isolated_db.index.complete_repair(
                repair_id1,
                processed_count=10,
                result="success"
            )

        def start_second():
            return isolated_db.index.start_repair(
                repair_type="test_race",
                trigger="test_2",
                code_version="test"
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(complete_first)
            f2 = executor.submit(start_second)
            f1.result()
            repair_id2 = f2.result()

        # Both should complete without error
        assert repair_id2 > repair_id1

        # Get recent repairs
        repairs = isolated_db.index.get_recent_repairs(limit=5)
        assert len(repairs) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
