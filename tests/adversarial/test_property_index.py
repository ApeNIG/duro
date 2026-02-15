"""
Property-Based Tests: Index Invariants (Phase 2.3)

Uses Hypothesis to verify properties that should ALWAYS hold true
for the artifact index, regardless of input data.

Properties tested:
1. Indexed artifacts are always retrievable
2. Deleted artifacts are never retrievable
3. Count is always accurate
4. Upsert is idempotent (same data = same result)
5. Index state is consistent after any operation sequence

File refs:
- duro-mcp/index.py:95-168 (upsert)
- duro-mcp/index.py:197-210 (delete)
- duro-mcp/index.py:get_by_id, count
"""

import pytest
import sys
import string
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from hypothesis import given, settings, assume, note, HealthCheck
from hypothesis import strategies as st

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockArtifact


# =============================================================================
# Settings for property tests - all tests need fresh DB per example
# =============================================================================

PROPERTY_SETTINGS = settings(
    max_examples=20,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    deadline=5000  # 5 seconds per example
)


# =============================================================================
# Custom Hypothesis Strategies
# =============================================================================

# Valid artifact ID: alphanumeric with underscores, reasonable length
artifact_id_strategy = st.text(
    alphabet=string.ascii_lowercase + string.digits + "_",
    min_size=1,
    max_size=30
).filter(lambda x: x[0].isalpha() if x else False)

# Valid artifact type
artifact_type_strategy = st.sampled_from([
    "fact", "decision", "episode", "evaluation", "skill", "rule", "log", "skill_stats"
])

# Valid claim/content
claim_strategy = st.text(
    alphabet=string.ascii_letters + string.digits + " .,!?-",
    min_size=1,
    max_size=200
)

# Valid tags
tag_strategy = st.lists(
    st.text(alphabet=string.ascii_lowercase + "_", min_size=1, max_size=15),
    min_size=0,
    max_size=5
)

# Confidence value
confidence_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


@st.composite
def artifact_strategy(draw):
    """Generate a valid MockArtifact."""
    return MockArtifact(
        id=draw(artifact_id_strategy),
        type=draw(artifact_type_strategy),
        claim=draw(claim_strategy),
        tags=draw(tag_strategy),
        confidence=draw(confidence_strategy)
    )


# =============================================================================
# Property Tests: Basic Index Operations
# =============================================================================

class TestIndexRetrievalProperty:
    """Property: Any indexed artifact must be retrievable."""

    @given(artifact=artifact_strategy())
    @PROPERTY_SETTINGS
    def test_indexed_artifact_is_retrievable(self, artifact):
        """
        Property: For any valid artifact A, after index(A), get(A.id) returns A.
        """
        with IsolatedTestDB(name="retrieval") as db:
            # Index the artifact
            db.add_artifact(artifact)

            # Must be retrievable
            retrieved = db.index.get_by_id(artifact.id)

            assert retrieved is not None, f"Artifact {artifact.id} not retrievable after indexing"
            assert retrieved["id"] == artifact.id

    @given(artifact=artifact_strategy())
    @PROPERTY_SETTINGS
    def test_deleted_artifact_not_retrievable(self, artifact):
        """
        Property: For any artifact A, after index(A) then delete(A.id), get(A.id) returns None.
        """
        with IsolatedTestDB(name="deletion") as db:
            # Index then delete
            db.add_artifact(artifact)
            db.index.delete(artifact.id)

            # Must not be retrievable
            retrieved = db.index.get_by_id(artifact.id)

            assert retrieved is None, f"Artifact {artifact.id} still retrievable after deletion"


class TestIndexCountProperty:
    """Property: Count is always accurate."""

    @given(artifacts=st.lists(artifact_strategy(), min_size=1, max_size=10, unique_by=lambda a: a.id))
    @PROPERTY_SETTINGS
    def test_count_matches_indexed(self, artifacts):
        """
        Property: count() equals number of artifacts indexed.
        """
        with IsolatedTestDB(name="count") as db:
            for artifact in artifacts:
                db.add_artifact(artifact)

            # Count should match
            total_count = db.count_artifacts()

            assert total_count == len(artifacts), f"Expected {len(artifacts)}, got {total_count}"

    @given(
        artifacts=st.lists(artifact_strategy(), min_size=1, max_size=8, unique_by=lambda a: a.id),
        delete_indices=st.lists(st.integers(min_value=0, max_value=7), min_size=0, max_size=4)
    )
    @PROPERTY_SETTINGS
    def test_count_after_deletions(self, artifacts, delete_indices):
        """
        Property: count() is accurate after deletions.
        """
        with IsolatedTestDB(name="count_del") as db:
            # Index all
            for artifact in artifacts:
                db.add_artifact(artifact)

            # Delete some (use valid indices only)
            deleted_ids = set()
            for idx in delete_indices:
                if idx < len(artifacts):
                    artifact_id = artifacts[idx].id
                    if artifact_id not in deleted_ids:
                        db.index.delete(artifact_id)
                        deleted_ids.add(artifact_id)

            # Count should be accurate
            expected = len(artifacts) - len(deleted_ids)
            actual = db.count_artifacts()

            assert actual == expected, f"Expected {expected}, got {actual}"


class TestIndexIdempotencyProperty:
    """Property: Upsert is idempotent."""

    @given(artifact=artifact_strategy())
    @PROPERTY_SETTINGS
    def test_double_index_same_result(self, artifact):
        """
        Property: Indexing same artifact twice produces same state as once.
        """
        with IsolatedTestDB(name="idempotent") as db:
            # Index twice
            db.add_artifact(artifact)
            db.add_artifact(artifact)

            # Should still be retrievable as single artifact
            retrieved = db.index.get_by_id(artifact.id)
            assert retrieved is not None

            # Count should be 1, not 2
            all_of_type = db.count_artifacts(artifact.type)
            assert all_of_type == 1, f"Expected 1 artifact of type {artifact.type}, got {all_of_type}"


class TestIndexTypeFilterProperty:
    """Property: Type filtering is accurate."""

    @given(artifacts=st.lists(artifact_strategy(), min_size=1, max_size=10, unique_by=lambda a: a.id))
    @PROPERTY_SETTINGS
    def test_type_count_sums_to_total(self, artifacts):
        """
        Property: Sum of counts per type equals total count.
        """
        with IsolatedTestDB(name="type_count") as db:
            # Index all
            for artifact in artifacts:
                db.add_artifact(artifact)

            # Count by type
            types = ["fact", "decision", "episode", "evaluation", "skill", "rule", "log", "skill_stats"]
            type_counts = sum(db.count_artifacts(t) for t in types)

            total = db.count_artifacts()

            assert type_counts == total, f"Sum of type counts ({type_counts}) != total ({total})"


# =============================================================================
# Property Tests: Data Integrity
# =============================================================================

class TestDataIntegrityProperty:
    """Property: Data is stored correctly."""

    @given(artifact=artifact_strategy())
    @PROPERTY_SETTINGS
    def test_stored_type_matches(self, artifact):
        """
        Property: Retrieved artifact has same type as indexed.
        """
        with IsolatedTestDB(name="type_integrity") as db:
            db.add_artifact(artifact)
            retrieved = db.index.get_by_id(artifact.id)

            assert retrieved is not None
            assert retrieved["type"] == artifact.type

    @given(
        id1=artifact_id_strategy,
        id2=artifact_id_strategy,
        claim=claim_strategy
    )
    @PROPERTY_SETTINGS
    def test_different_ids_independent(self, id1, id2, claim):
        """
        Property: Artifacts with different IDs are independent.
        """
        assume(id1 != id2)

        with IsolatedTestDB(name="id_independence") as db:
            artifact1 = MockArtifact(id=id1, type="fact", claim=claim)
            artifact2 = MockArtifact(id=id2, type="decision", claim=claim)

            db.add_artifact(artifact1)
            db.add_artifact(artifact2)

            # Both retrievable
            r1 = db.index.get_by_id(id1)
            r2 = db.index.get_by_id(id2)

            assert r1 is not None
            assert r2 is not None
            assert r1["type"] == "fact"
            assert r2["type"] == "decision"

            # Deleting one doesn't affect other
            db.index.delete(id1)

            r1_after = db.index.get_by_id(id1)
            r2_after = db.index.get_by_id(id2)

            assert r1_after is None
            assert r2_after is not None


# =============================================================================
# Property Tests: Operation Sequences
# =============================================================================

class TestOperationSequenceProperty:
    """Property: System is consistent after any valid operation sequence."""

    @given(
        artifacts=st.lists(artifact_strategy(), min_size=1, max_size=5, unique_by=lambda a: a.id),
        operations=st.lists(
            st.tuples(
                st.sampled_from(["index", "delete", "get"]),
                st.integers(min_value=0, max_value=4)
            ),
            min_size=1,
            max_size=10
        )
    )
    @PROPERTY_SETTINGS
    def test_random_operation_sequence(self, artifacts, operations):
        """
        Property: Any sequence of valid operations leaves consistent state.
        """
        with IsolatedTestDB(name="op_seq") as db:
            indexed_ids = set()

            for op, idx in operations:
                artifact_idx = idx % len(artifacts)
                artifact = artifacts[artifact_idx]

                if op == "index":
                    db.add_artifact(artifact)
                    indexed_ids.add(artifact.id)
                elif op == "delete":
                    if artifact.id in indexed_ids:
                        db.index.delete(artifact.id)
                        indexed_ids.discard(artifact.id)
                elif op == "get":
                    result = db.index.get_by_id(artifact.id)
                    # Should match our tracking
                    if artifact.id in indexed_ids:
                        assert result is not None
                    else:
                        assert result is None

            # Final consistency check
            for artifact in artifacts:
                result = db.index.get_by_id(artifact.id)
                if artifact.id in indexed_ids:
                    assert result is not None, f"{artifact.id} should exist"
                else:
                    assert result is None, f"{artifact.id} should not exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
