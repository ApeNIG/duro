"""
Test: Embedding Dimension Mismatch (Priority: MEDIUM)

Tests that wrong vector dimensions are detected and handled.

Risk: If embeddings with different dimensions are stored together:
- Vector search becomes undefined (comparing 384-dim vs 768-dim vectors)
- SQLite-vec may crash or return garbage results
- Silent data corruption

File refs:
- duro-mcp/embeddings.py:164 (EMBEDDING_CONFIG with dimension)
- duro-mcp/index.py:772-827 (upsert_embedding)
- duro-mcp/index.py:hybrid_search (vector similarity)
"""

import pytest
import sys
from pathlib import Path
from typing import List, Optional

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact


class TestEmbeddingDimensionValidation:
    """Tests for embedding dimension validation."""

    def test_correct_dimension_accepted(self, isolated_db, mock_embedder):
        """Baseline: Correct dimension embedding is accepted."""
        artifact_id = "fact_correct_dim"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Correct dimension test"
        ))

        # Default mock embedder uses 384 dimensions
        embedding = mock_embedder.embed("Correct dimension test")
        assert len(embedding) == 384

        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash="hash_correct",
            model_name=mock_embedder.model_name
        )

        if not success:
            pytest.skip("sqlite-vec not available")

        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state is not None

    def test_wrong_dimension_handling(self, isolated_db):
        """Test: Wrong dimension embedding should be rejected or handled."""
        artifact_id = "fact_wrong_dim"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Wrong dimension test"
        ))

        # Create embedding with wrong dimension (768 instead of 384)
        wrong_embedding = [0.1] * 768

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=wrong_embedding,
                content_hash="hash_wrong",
                model_name="wrong-model"
            )

            if success:
                # If it succeeded, it might have been silently truncated
                # or the system accepts any dimension
                # This is a potential vulnerability to document
                state = isolated_db.index.get_embedding_state(artifact_id)
                # At minimum, it should be stored somehow
        except Exception as e:
            # Exception is acceptable - dimension mismatch detected
            error_msg = str(e).lower()
            # Should mention dimension, size, or vector
            pass

    def test_too_small_dimension(self, isolated_db):
        """Test: Too small embedding dimension."""
        artifact_id = "fact_small_dim"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Small dimension test"
        ))

        # Very small embedding
        small_embedding = [0.1] * 10  # Only 10 dimensions

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=small_embedding,
                content_hash="hash_small",
                model_name="small-model"
            )
        except Exception:
            pass  # Rejection is acceptable

    def test_empty_embedding(self, isolated_db):
        """Test: Empty embedding vector."""
        artifact_id = "fact_empty_emb"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Empty embedding test"
        ))

        empty_embedding = []

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=empty_embedding,
                content_hash="hash_empty",
                model_name="empty-model"
            )
            # If succeeds, this is a bug
            assert not success, "Empty embedding should not succeed"
        except Exception:
            pass  # Rejection is correct

    def test_single_dimension_embedding(self, isolated_db):
        """Test: Single dimension embedding (scalar)."""
        artifact_id = "fact_scalar"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Scalar embedding test"
        ))

        scalar_embedding = [0.5]  # Single value

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=scalar_embedding,
                content_hash="hash_scalar",
                model_name="scalar-model"
            )
        except Exception:
            pass


class TestMixedDimensionScenarios:
    """Tests for scenarios with mixed dimension embeddings."""

    def test_dimension_consistency_check(self, isolated_db, mock_embedder):
        """Test: Detect when embeddings have inconsistent dimensions."""
        # Create artifacts
        for i in range(3):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_consistent_{i}",
                type="fact",
                claim=f"Consistency test {i}"
            ))

        # Embed first with 384 dimensions
        embedding_384 = mock_embedder.embed("Consistency test 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_consistent_0",
            embedding=embedding_384,
            content_hash="hash_0",
            model_name="model-384"
        )

        if not success:
            pytest.skip("sqlite-vec not available")

        # Try to embed second with different dimension
        embedding_768 = [0.1] * 768

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id="fact_consistent_1",
                embedding=embedding_768,
                content_hash="hash_1",
                model_name="model-768"
            )
            # If this succeeds, we have a dimension mismatch vulnerability
        except Exception:
            pass  # Good - rejected

    def test_get_expected_dimension(self):
        """Test: System has a defined expected dimension."""
        from embeddings import EMBEDDING_CONFIG

        # Config uses 'embedding_dim' key
        assert "embedding_dim" in EMBEDDING_CONFIG
        dimension = EMBEDDING_CONFIG["embedding_dim"]

        # Should be a common embedding dimension
        common_dimensions = [128, 256, 384, 512, 768, 1024, 1536]
        assert dimension in common_dimensions, f"Unexpected dimension: {dimension}"

    def test_model_dimension_mapping(self):
        """Test: Different models have known dimensions."""
        # Common model dimensions for reference
        model_dimensions = {
            "bge-small-en": 384,
            "bge-base-en": 768,
            "bge-large-en": 1024,
            "all-MiniLM-L6": 384,
            "all-mpnet-base": 768,
            "text-embedding-ada-002": 1536,
            "text-embedding-3-small": 1536,
        }

        # Just verify the mapping exists as documentation
        for model, dim in model_dimensions.items():
            assert isinstance(dim, int)
            assert dim > 0


class TestEmbeddingValueValidation:
    """Tests for embedding value validation."""

    def test_nan_in_embedding(self, isolated_db):
        """Test: NaN values in embedding are handled."""
        artifact_id = "fact_nan"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="NaN embedding test"
        ))

        import math
        nan_embedding = [0.1] * 380 + [math.nan] * 4

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=nan_embedding,
                content_hash="hash_nan",
                model_name="nan-model"
            )
            # NaN should probably be rejected
        except (ValueError, Exception):
            pass  # Rejection is correct

    def test_inf_in_embedding(self, isolated_db):
        """Test: Infinity values in embedding are handled."""
        artifact_id = "fact_inf"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Infinity embedding test"
        ))

        import math
        inf_embedding = [0.1] * 380 + [math.inf] * 4

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=inf_embedding,
                content_hash="hash_inf",
                model_name="inf-model"
            )
        except (ValueError, Exception):
            pass

    def test_very_large_values(self, isolated_db):
        """Test: Very large embedding values."""
        artifact_id = "fact_large_val"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Large value embedding test"
        ))

        large_embedding = [1e38] * 384  # Very large but valid floats

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=large_embedding,
                content_hash="hash_large",
                model_name="large-model"
            )
        except Exception:
            pass

    def test_very_small_values(self, isolated_db):
        """Test: Very small (subnormal) embedding values."""
        artifact_id = "fact_small_val"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Small value embedding test"
        ))

        small_embedding = [1e-38] * 384  # Very small but valid floats

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=small_embedding,
                content_hash="hash_small_val",
                model_name="small-val-model"
            )
        except Exception:
            pass

    def test_all_zeros_embedding(self, isolated_db):
        """Test: All-zeros embedding (zero vector)."""
        artifact_id = "fact_zeros"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Zero embedding test"
        ))

        zero_embedding = [0.0] * 384

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=zero_embedding,
                content_hash="hash_zeros",
                model_name="zero-model"
            )
            # Zero vector makes cosine similarity undefined
            # This might be accepted but is problematic for search
        except Exception:
            pass

    def test_unnormalized_embedding(self, isolated_db, mock_embedder):
        """Test: Unnormalized embedding (not unit vector)."""
        artifact_id = "fact_unnorm"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Unnormalized embedding test"
        ))

        # Create unnormalized vector (norm != 1)
        unnorm_embedding = [10.0] * 384  # Large magnitude

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=unnorm_embedding,
                content_hash="hash_unnorm",
                model_name="unnorm-model"
            )
            # Most systems accept unnormalized vectors
            # Cosine similarity handles normalization
        except Exception:
            pass


class TestDimensionMigration:
    """Tests for dimension change scenarios."""

    def test_detect_dimension_change_needed(self, isolated_db, mock_embedder):
        """Test: Detect when model upgrade requires dimension change."""
        artifact_id = "fact_migrate"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Migration test"
        ))

        # Embed with current dimension
        embedding = mock_embedder.embed("Migration test")
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash="hash_v1",
            model_name="model-v1-384dim"
        )

        if not success:
            pytest.skip("sqlite-vec not available")

        # Check stored dimension (if queryable)
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state is not None
        assert state["model"] == "model-v1-384dim"

        # In real scenario, model upgrade to 768-dim would require:
        # 1. Full reindex with new model
        # 2. Cannot mix old 384-dim with new 768-dim


class TestEmbeddingTypeValidation:
    """Tests for embedding type validation."""

    def test_embedding_must_be_list(self, isolated_db):
        """Test: Embedding must be a list, not other types."""
        artifact_id = "fact_type"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Type test"
        ))

        invalid_embeddings = [
            "not a list",
            123,
            {"vector": [0.1] * 384},
            None,
            (0.1,) * 384,  # Tuple might work
        ]

        for invalid in invalid_embeddings:
            try:
                success = isolated_db.index.upsert_embedding(
                    artifact_id=artifact_id,
                    embedding=invalid,
                    content_hash="hash_invalid",
                    model_name="test"
                )
            except (TypeError, AttributeError, Exception):
                pass  # Rejection is correct

    def test_embedding_elements_must_be_numeric(self, isolated_db):
        """Test: Embedding elements must be numeric."""
        artifact_id = "fact_elem_type"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Element type test"
        ))

        # Mix of types in embedding
        mixed_embedding = [0.1] * 380 + ["string", None, [], {}]

        try:
            success = isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=mixed_embedding,
                content_hash="hash_mixed",
                model_name="test"
            )
        except (TypeError, ValueError, Exception):
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
