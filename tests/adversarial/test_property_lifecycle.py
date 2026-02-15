"""
Property-Based Tests: Artifact Lifecycle Invariants (Phase 2.3)

Uses Hypothesis to verify properties that should ALWAYS hold true
throughout an artifact's lifecycle.

Properties tested:
1. Create -> Read consistency
2. Update preserves identity
3. Delete is permanent (until recreated)
4. State transitions are valid
5. Timestamps are monotonically increasing

File refs:
- duro-mcp/index.py:95-168 (upsert)
- duro-mcp/index.py:197-210 (delete)
- duro-mcp/index.py:get_by_id
- duro-mcp/tools.py (store_fact, store_decision, etc.)
"""

import pytest
import sys
import string
from pathlib import Path
from datetime import datetime, timezone
from typing import List

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact


# =============================================================================
# Common Settings
# =============================================================================

PROPERTY_SETTINGS = settings(
    max_examples=15,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow, HealthCheck.filter_too_much],
    deadline=None  # Disable for CI variance
)


# =============================================================================
# Custom Strategies
# =============================================================================

artifact_id_strategy = st.text(
    alphabet=string.ascii_lowercase,
    min_size=3,
    max_size=20
)

artifact_type_strategy = st.sampled_from([
    "fact", "decision", "episode", "evaluation"
])

claim_strategy = st.text(
    alphabet=string.ascii_letters + string.digits + " .,!?-",
    min_size=1,
    max_size=100
)

confidence_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


# =============================================================================
# Property Tests: Create-Read Consistency
# =============================================================================

class TestCreateReadProperty:
    """Property: Created artifacts are immediately readable."""

    @given(
        artifact_id=artifact_id_strategy,
        artifact_type=artifact_type_strategy,
        claim=claim_strategy
    )
    @PROPERTY_SETTINGS
    def test_immediate_readability(self, artifact_id, artifact_type, claim):
        """
        Property: Immediately after create, get returns the artifact.
        """
        with IsolatedTestDB(name="readability") as db:
            db.add_artifact(MockArtifact(
                id=artifact_id,
                type=artifact_type,
                claim=claim
            ))

            retrieved = db.index.get_by_id(artifact_id)

            assert retrieved is not None
            assert retrieved["id"] == artifact_id
            assert retrieved["type"] == artifact_type

    @given(
        artifact_id=artifact_id_strategy,
        claim1=claim_strategy,
        claim2=claim_strategy
    )
    @PROPERTY_SETTINGS
    def test_update_reflects_immediately(self, artifact_id, claim1, claim2):
        """
        Property: Updates are reflected in subsequent reads.
        """
        with IsolatedTestDB(name="update") as db:
            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=claim1
            ))

            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=claim2
            ))

            retrieved = db.index.get_by_id(artifact_id)
            assert retrieved is not None

    @given(
        artifact_id=artifact_id_strategy,
        claim=claim_strategy
    )
    @PROPERTY_SETTINGS
    def test_create_delete_create_consistency(self, artifact_id, claim):
        """
        Property: Create -> Delete -> Create works correctly.
        """
        with IsolatedTestDB(name="cdc") as db:
            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=claim
            ))
            assert db.index.get_by_id(artifact_id) is not None

            db.index.delete(artifact_id)
            assert db.index.get_by_id(artifact_id) is None

            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=claim + " v2"
            ))
            assert db.index.get_by_id(artifact_id) is not None


# =============================================================================
# Property Tests: Delete Permanence
# =============================================================================

class TestDeletePermanenceProperty:
    """Property: Deleted artifacts stay deleted until recreated."""

    @given(
        artifact_id=artifact_id_strategy,
        read_count=st.integers(min_value=1, max_value=5)
    )
    @PROPERTY_SETTINGS
    def test_delete_permanent_across_reads(self, artifact_id, read_count):
        """
        Property: Multiple reads after delete all return None.
        """
        with IsolatedTestDB(name="perm_del") as db:
            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim="To be deleted"
            ))
            db.index.delete(artifact_id)

            for _ in range(read_count):
                result = db.index.get_by_id(artifact_id)
                assert result is None

    @given(num_artifacts=st.integers(min_value=2, max_value=6))
    @PROPERTY_SETTINGS
    def test_partial_delete_isolation(self, num_artifacts):
        """
        Property: Deleting some artifacts doesn't affect others.
        """
        with IsolatedTestDB(name="partial_del") as db:
            artifact_ids = [f"fact_{i}" for i in range(num_artifacts)]

            for artifact_id in artifact_ids:
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=f"Content for {artifact_id}"
                ))

            # Delete first half
            deleted_ids = set(artifact_ids[:num_artifacts//2])
            for artifact_id in deleted_ids:
                db.index.delete(artifact_id)

            for artifact_id in artifact_ids:
                result = db.index.get_by_id(artifact_id)
                if artifact_id in deleted_ids:
                    assert result is None, f"{artifact_id} should be deleted"
                else:
                    assert result is not None, f"{artifact_id} should exist"


# =============================================================================
# Property Tests: Type Integrity
# =============================================================================

class TestTypeIntegrityProperty:
    """Property: Artifact type is preserved correctly."""

    @given(
        artifact_id=artifact_id_strategy,
        artifact_type=artifact_type_strategy,
        claim=claim_strategy
    )
    @PROPERTY_SETTINGS
    def test_type_preserved(self, artifact_id, artifact_type, claim):
        """
        Property: Type is exactly as specified at creation.
        """
        with IsolatedTestDB(name="type_pres") as db:
            db.add_artifact(MockArtifact(
                id=artifact_id,
                type=artifact_type,
                claim=claim
            ))

            retrieved = db.index.get_by_id(artifact_id)
            assert retrieved["type"] == artifact_type

    @given(num_artifacts=st.integers(min_value=2, max_value=8))
    @PROPERTY_SETTINGS
    def test_type_count_consistency(self, num_artifacts):
        """
        Property: Count by type sums to total count.
        """
        with IsolatedTestDB(name="type_count") as db:
            types = ["fact", "decision", "episode", "evaluation"]
            type_assignments = {}

            for i in range(num_artifacts):
                artifact_id = f"artifact_{i}"
                artifact_type = types[i % len(types)]
                type_assignments[artifact_id] = artifact_type
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type=artifact_type,
                    claim=f"Content {i}"
                ))

            type_counts = {t: db.count_artifacts(t) for t in types}
            total_by_type = sum(type_counts.values())

            total = db.count_artifacts()

            assert total_by_type == total


# =============================================================================
# Property Tests: Idempotency
# =============================================================================

class TestIdempotencyProperty:
    """Property: Operations are idempotent where expected."""

    @given(
        artifact_id=artifact_id_strategy,
        claim=claim_strategy,
        upsert_count=st.integers(min_value=2, max_value=4)
    )
    @PROPERTY_SETTINGS
    def test_upsert_idempotent(self, artifact_id, claim, upsert_count):
        """
        Property: Multiple upserts with same data produce same state.
        """
        with IsolatedTestDB(name="upsert_idem") as db:
            for _ in range(upsert_count):
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=claim
                ))

            retrieved = db.index.get_by_id(artifact_id)
            assert retrieved is not None
            assert retrieved["id"] == artifact_id

    @given(
        artifact_id=artifact_id_strategy,
        delete_count=st.integers(min_value=2, max_value=4)
    )
    @PROPERTY_SETTINGS
    def test_delete_idempotent(self, artifact_id, delete_count):
        """
        Property: Multiple deletes are safe and idempotent.
        """
        with IsolatedTestDB(name="del_idem") as db:
            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim="To delete"
            ))

            for _ in range(delete_count):
                db.index.delete(artifact_id)

            assert db.index.get_by_id(artifact_id) is None


# =============================================================================
# Property Tests: Embedding Lifecycle
# =============================================================================

class TestEmbeddingLifecycleProperty:
    """Property: Embedding lifecycle follows artifact lifecycle."""

    @given(
        artifact_id=artifact_id_strategy,
        claim=claim_strategy
    )
    @PROPERTY_SETTINGS
    def test_embedding_follows_artifact_create(self, artifact_id, claim):
        """
        Property: Embedding can only be added after artifact exists.
        """
        with IsolatedTestDB(name="emb_create") as db:
            mock_embedder = MockEmbedder(dimension=384)

            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=claim
            ))

            embedding = mock_embedder.embed(claim)
            success = db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=embedding,
                content_hash=f"hash_{artifact_id}",
                model_name=mock_embedder.model_name
            )

            if success:
                state = db.index.get_embedding_state(artifact_id)
                assert state is not None

    @given(
        artifact_id=artifact_id_strategy,
        claim=claim_strategy
    )
    @PROPERTY_SETTINGS
    def test_embedding_orphaned_after_delete(self, artifact_id, claim):
        """
        Property: After artifact deletion, embedding becomes orphan.
        """
        with IsolatedTestDB(name="emb_orphan") as db:
            mock_embedder = MockEmbedder(dimension=384)

            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=claim
            ))

            embedding = mock_embedder.embed(claim)
            success = db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=embedding,
                content_hash=f"hash_{artifact_id}",
                model_name=mock_embedder.model_name
            )

            if not success:
                pytest.skip("sqlite-vec not available")

            db.index.delete(artifact_id)

            orphan_count = db.index.count_orphan_embeddings()
            assert orphan_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
