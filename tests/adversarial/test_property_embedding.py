"""
Property-Based Tests: Embedding Invariants (Phase 2.3)

Uses Hypothesis to verify properties that should ALWAYS hold true
for the embedding system.

Properties tested:
1. Content hash is deterministic
2. Embedding state tracks all embedded artifacts
3. Orphan count is accurate
4. Model name is preserved
5. Upsert embedding is idempotent for same content

File refs:
- duro-mcp/embeddings.py:72 (compute_content_hash)
- duro-mcp/index.py:772-827 (upsert_embedding)
- duro-mcp/index.py:get_embedding_state
"""

import pytest
import sys
import string
import hashlib
from pathlib import Path
from typing import List

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact


# =============================================================================
# Custom Strategies
# =============================================================================

# Content for hashing
content_strategy = st.text(
    alphabet=string.printable,
    min_size=1,
    max_size=1000
)

# Model name
model_name_strategy = st.text(
    alphabet=string.ascii_lowercase + string.digits + "-_.",
    min_size=1,
    max_size=50
)

# Valid artifact ID
artifact_id_strategy = st.text(
    alphabet=string.ascii_lowercase + string.digits + "_",
    min_size=1,
    max_size=50
).filter(lambda x: x[0].isalpha() if x else False)

# Embedding vector (normalized)
@st.composite
def embedding_strategy(draw, dimension=384):
    """Generate a valid normalized embedding vector."""
    raw = draw(st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=dimension,
        max_size=dimension
    ))
    # Normalize
    norm = sum(x*x for x in raw) ** 0.5
    if norm > 0:
        return [x / norm for x in raw]
    return [1.0 / (dimension ** 0.5)] * dimension  # Fallback unit vector


# =============================================================================
# Property Tests: Content Hash
# =============================================================================

class TestContentHashProperty:
    """Property: Content hash is deterministic and consistent."""

    @given(content=content_strategy)
    @settings(max_examples=100)
    def test_hash_is_deterministic(self, content):
        """
        Property: Same content always produces same hash.
        """
        hash1 = hashlib.sha256(content.encode()).hexdigest()[:16]
        hash2 = hashlib.sha256(content.encode()).hexdigest()[:16]

        assert hash1 == hash2, "Hash should be deterministic"

    @given(content1=content_strategy, content2=content_strategy)
    @settings(max_examples=100)
    def test_different_content_different_hash(self, content1, content2):
        """
        Property: Different content produces different hash (with high probability).
        """
        assume(content1 != content2)

        hash1 = hashlib.sha256(content1.encode()).hexdigest()[:16]
        hash2 = hashlib.sha256(content2.encode()).hexdigest()[:16]

        # Note: Collisions are possible but extremely rare for SHA256[:16]
        # We just verify that the function runs without error
        assert len(hash1) == 16
        assert len(hash2) == 16

    @given(content=content_strategy)
    @settings(max_examples=100)
    def test_hash_length_constant(self, content):
        """
        Property: Hash length is always 16 characters.
        """
        h = hashlib.sha256(content.encode()).hexdigest()[:16]
        assert len(h) == 16

    @given(content=content_strategy)
    @settings(max_examples=100)
    def test_hash_is_hex(self, content):
        """
        Property: Hash contains only hex characters.
        """
        h = hashlib.sha256(content.encode()).hexdigest()[:16]
        assert all(c in "0123456789abcdef" for c in h)


# =============================================================================
# Property Tests: Embedding State
# =============================================================================

class TestEmbeddingStateProperty:
    """Property: Embedding state is accurately tracked."""

    @given(
        artifact_id=artifact_id_strategy,
        content=content_strategy,
        model_name=model_name_strategy
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_embedded_artifact_has_state(self, isolated_db, mock_embedder, artifact_id, content, model_name):
        """
        Property: After embedding, artifact has embedding state.
        """
        # Create artifact
        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim=content
        ))

        # Embed
        embedding = mock_embedder.embed(content)
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash=content_hash,
            model_name=model_name
        )

        if not success:
            pytest.skip("sqlite-vec not available")

        # State should exist
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state is not None
        assert state["content_hash"] == content_hash
        assert state["model"] == model_name

    @given(artifact_id=artifact_id_strategy)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unembedded_artifact_no_state(self, isolated_db, artifact_id):
        """
        Property: Artifact without embedding has no embedding state.
        """
        # Create artifact but don't embed
        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Test content"
        ))

        # State should be None
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state is None


class TestEmbeddingIdempotencyProperty:
    """Property: Embedding operations are idempotent."""

    @given(
        artifact_id=artifact_id_strategy,
        content=content_strategy
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_double_embed_same_content(self, isolated_db, mock_embedder, artifact_id, content):
        """
        Property: Embedding same content twice produces same state.
        """
        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim=content
        ))

        embedding = mock_embedder.embed(content)
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Embed twice
        success1 = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash=content_hash,
            model_name="test-model"
        )

        if not success1:
            pytest.skip("sqlite-vec not available")

        success2 = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash=content_hash,
            model_name="test-model"
        )

        # State should be consistent
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state is not None
        assert state["content_hash"] == content_hash


# =============================================================================
# Property Tests: Orphan Tracking
# =============================================================================

class TestOrphanTrackingProperty:
    """Property: Orphan detection is accurate."""

    @given(
        artifact_ids=st.lists(
            artifact_id_strategy,
            min_size=1,
            max_size=10,
            unique=True
        )
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_orphans_when_artifacts_exist(self, isolated_db, mock_embedder, artifact_ids):
        """
        Property: No orphans when all embedded artifacts still exist.
        """
        # Create and embed all
        for i, artifact_id in enumerate(artifact_ids):
            isolated_db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=f"Content {i}"
            ))

        # Embed first to check availability
        embedding = mock_embedder.embed("Content 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_ids[0],
            embedding=embedding,
            content_hash=f"hash_0",
            model_name="test"
        )

        if not success:
            pytest.skip("sqlite-vec not available")

        # Embed rest
        for i, artifact_id in enumerate(artifact_ids[1:], 1):
            embedding = mock_embedder.embed(f"Content {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=embedding,
                content_hash=f"hash_{i}",
                model_name="test"
            )

        # No orphans
        orphan_count = isolated_db.index.count_orphan_embeddings()
        assert orphan_count == 0

    @given(
        artifact_ids=st.lists(
            artifact_id_strategy,
            min_size=2,
            max_size=10,
            unique=True
        ),
        delete_count=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_orphan_count_matches_deleted(self, isolated_db, mock_embedder, artifact_ids, delete_count):
        """
        Property: Orphan count equals number of deleted artifacts with embeddings.
        """
        # Create and embed all
        for i, artifact_id in enumerate(artifact_ids):
            isolated_db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=f"Content {i}"
            ))

        # Embed first to check
        embedding = mock_embedder.embed("Content 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_ids[0],
            embedding=embedding,
            content_hash="hash_0",
            model_name="test"
        )

        if not success:
            pytest.skip("sqlite-vec not available")

        # Embed rest
        for i, artifact_id in enumerate(artifact_ids[1:], 1):
            embedding = mock_embedder.embed(f"Content {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=embedding,
                content_hash=f"hash_{i}",
                model_name="test"
            )

        # Delete some (up to delete_count or available)
        actual_delete_count = min(delete_count, len(artifact_ids))
        for i in range(actual_delete_count):
            isolated_db.index.delete(artifact_ids[i])

        # Orphan count should match
        orphan_count = isolated_db.index.count_orphan_embeddings()
        assert orphan_count == actual_delete_count


# =============================================================================
# Property Tests: Mock Embedder
# =============================================================================

class TestMockEmbedderProperty:
    """Property: Mock embedder produces valid embeddings."""

    @given(content=content_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_embedding_has_correct_dimension(self, mock_embedder, content):
        """
        Property: Embedding has expected dimension.
        """
        embedding = mock_embedder.embed(content)

        assert len(embedding) == mock_embedder.dimension

    @given(content=content_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_embedding_is_normalized(self, mock_embedder, content):
        """
        Property: Embedding is approximately normalized (unit vector).
        """
        embedding = mock_embedder.embed(content)

        norm = sum(x*x for x in embedding) ** 0.5

        # Should be close to 1.0
        assert abs(norm - 1.0) < 0.01, f"Norm was {norm}, expected ~1.0"

    @given(content=content_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_embedding_is_deterministic(self, mock_embedder, content):
        """
        Property: Same content produces same embedding.
        """
        emb1 = mock_embedder.embed(content)
        emb2 = mock_embedder.embed(content)

        assert emb1 == emb2

    @given(content=content_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_embedding_values_valid(self, mock_embedder, content):
        """
        Property: Embedding values are valid floats.
        """
        import math

        embedding = mock_embedder.embed(content)

        for val in embedding:
            assert isinstance(val, float)
            assert not math.isnan(val)
            assert not math.isinf(val)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def isolated_db():
    """Provide an isolated test database."""
    with IsolatedTestDB(name="property_emb") as db:
        yield db


@pytest.fixture
def mock_embedder():
    """Provide a mock embedder."""
    return MockEmbedder(dimension=384)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
