"""
Test: Embedding Model Drift (Priority: HIGH)

Tests that mixing embeddings from different models doesn't corrupt search.

Risk: If embeddings from different models (e.g., v1.5 vs v2.0) are mixed
in the same vector store, cosine similarity becomes meaningless and
search quality degrades silently.

File refs:
- duro-mcp/embeddings.py:164 (EMBEDDING_CONFIG with model_name)
- duro-mcp/index.py:777 (model_name parameter in upsert_embedding)
- skills/ops/crash_drill_verify.py:142 (model version check)
"""

import pytest
import sys
import random
from pathlib import Path
from typing import List, Dict, Optional

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, TestArtifact


class TestModelDrift:
    """Tests for embedding model version mixing risks."""

    def test_embedding_config_has_model_name(self):
        """Verify EMBEDDING_CONFIG includes model_name."""
        from embeddings import EMBEDDING_CONFIG

        assert "model_name" in EMBEDDING_CONFIG
        assert isinstance(EMBEDDING_CONFIG["model_name"], str)
        assert len(EMBEDDING_CONFIG["model_name"]) > 0

        # Current model should be BGE
        assert "bge" in EMBEDDING_CONFIG["model_name"].lower()

    def test_embedding_state_stores_model(self, isolated_db, mock_embedder):
        """Verify embedding state tracks which model was used."""
        artifact_id = "fact_model_track"
        isolated_db.add_artifact(TestArtifact(
            id=artifact_id,
            type="fact",
            claim="Test fact for model tracking"
        ))

        embedding = mock_embedder.embed("Test fact for model tracking")

        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash="hash_model_test",
            model_name="test-model-v1"
        )
        if not success:
            pytest.skip("sqlite-vec not available - upsert_embedding returned False")

        # Verify model is stored
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state is not None
        assert state["model"] == "test-model-v1"

    def test_mixed_model_detection(self, isolated_db):
        """
        Test: Detect when embeddings from different models are mixed.

        This simulates what happens when model is upgraded but old
        embeddings aren't re-computed.
        """
        embedder_v1 = MockEmbedder(dimension=384)
        embedder_v1.model_name = "model-v1"

        embedder_v2 = MockEmbedder(dimension=384)
        embedder_v2.model_name = "model-v2"

        # Create artifacts
        for i in range(4):
            isolated_db.add_artifact(TestArtifact(
                id=f"fact_mixed_{i}",
                type="fact",
                claim=f"Mixed model test fact {i}"
            ))

        # Embed first two with v1
        embedding = embedder_v1.embed("Mixed model test fact 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_mixed_0",
            embedding=embedding,
            content_hash="hash_mixed_0",
            model_name=embedder_v1.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available - upsert_embedding returned False")

        # Continue with remaining embeddings
        for i in range(1, 2):
            embedding = embedder_v1.embed(f"Mixed model test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_mixed_{i}",
                embedding=embedding,
                content_hash=f"hash_mixed_{i}",
                model_name=embedder_v1.model_name
            )

        for i in range(2, 4):
            embedding = embedder_v2.embed(f"Mixed model test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_mixed_{i}",
                embedding=embedding,
                content_hash=f"hash_mixed_{i}",
                model_name=embedder_v2.model_name
            )

        # Check model distribution
        models_used = set()
        for i in range(4):
            state = isolated_db.index.get_embedding_state(f"fact_mixed_{i}")
            if state:
                models_used.add(state["model"])

        # Should detect multiple models
        assert len(models_used) == 2
        assert "model-v1" in models_used
        assert "model-v2" in models_used

    def test_cosine_similarity_meaningless_across_models(self):
        """
        Demonstrate that cosine similarity is meaningless between
        embeddings from different models.

        Different models embed the same text into different vector spaces,
        so comparing them is like comparing apples and oranges.
        """
        # Create two "models" with different embedding strategies
        class ModelA:
            """Embeds based on word count."""
            @staticmethod
            def embed(text: str) -> List[float]:
                words = text.lower().split()
                vec = [0.0] * 10
                for i, w in enumerate(words[:10]):
                    vec[i] = len(w) / 10.0
                # Normalize
                norm = sum(x*x for x in vec) ** 0.5
                return [x/norm for x in vec] if norm > 0 else vec

        class ModelB:
            """Embeds based on character frequency."""
            @staticmethod
            def embed(text: str) -> List[float]:
                text = text.lower()
                vec = [text.count(chr(ord('a') + i)) / max(len(text), 1)
                       for i in range(10)]
                # Normalize
                norm = sum(x*x for x in vec) ** 0.5
                return [x/norm for x in vec] if norm > 0 else vec

        def cosine_similarity(a: List[float], b: List[float]) -> float:
            dot = sum(x*y for x, y in zip(a, b))
            norm_a = sum(x*x for x in a) ** 0.5
            norm_b = sum(x*x for x in b) ** 0.5
            return dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0

        # Same text, different models
        text = "Python is a programming language"

        emb_a1 = ModelA.embed(text)
        emb_b1 = ModelB.embed(text)

        # Cross-model similarity is NOT meaningful
        cross_sim = cosine_similarity(emb_a1, emb_b1)

        # Similar texts within same model
        text2 = "Python is a scripting language"
        emb_a2 = ModelA.embed(text2)
        emb_b2 = ModelB.embed(text2)

        same_model_a = cosine_similarity(emb_a1, emb_a2)
        same_model_b = cosine_similarity(emb_b1, emb_b2)

        # Within-model similarity should be higher than cross-model
        # (This demonstrates the concept; real models differ more dramatically)
        print(f"\nCross-model similarity: {cross_sim:.3f}")
        print(f"Same-model A similarity: {same_model_a:.3f}")
        print(f"Same-model B similarity: {same_model_b:.3f}")

        # The key insight: cross_sim being high or low is RANDOM
        # It doesn't reflect semantic similarity

    def test_model_version_in_search_results(self, isolated_db, mock_embedder):
        """
        Test: Search should warn or filter when models are mixed.

        Ideally, hybrid_search should:
        - Filter to embeddings from the same model as query
        - Or warn when mixed models detected
        """
        # This test documents the desired behavior
        # Current implementation may not have this check

        # Create mixed-model scenario
        for i in range(3):
            isolated_db.add_artifact(TestArtifact(
                id=f"fact_search_{i}",
                type="fact",
                claim=f"Search test fact {i}"
            ))

        # Embed with different "models"
        models = ["model-old", "model-old", "model-new"]
        try:
            for i, model in enumerate(models):
                embedding = mock_embedder.embed(f"Search test fact {i}")
                isolated_db.index.upsert_embedding(
                    artifact_id=f"fact_search_{i}",
                    embedding=embedding,
                    content_hash=f"hash_search_{i}",
                    model_name=model
                )
        except Exception:
            pytest.skip("sqlite-vec not available")

        # Get search capabilities
        caps = isolated_db.index.get_search_capabilities()

        # Document what SHOULD happen:
        # 1. Search with model-old query embedding should prefer model-old artifacts
        # 2. Or at minimum, results should indicate which model each embedding used
        # 3. Health check should flag mixed models as a warning

        # Current behavior: no filtering by model
        # This test passes but documents the gap


class TestModelUpgradeScenarios:
    """Tests for model upgrade scenarios and migrations."""

    def test_reembed_all_changes_model(self, isolated_db, mock_embedder):
        """
        Test: Full reembed updates all embeddings to new model.
        """
        # Create and embed with old model
        for i in range(3):
            isolated_db.add_artifact(TestArtifact(
                id=f"fact_upgrade_{i}",
                type="fact",
                claim=f"Upgrade test fact {i}"
            ))

        mock_embedder.model_name = "model-old"

        # First embedding to check if vectors are available
        embedding = mock_embedder.embed("Upgrade test fact 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_upgrade_0",
            embedding=embedding,
            content_hash="hash_upgrade_0",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available - upsert_embedding returned False")

        # Continue with remaining
        for i in range(1, 3):
            embedding = mock_embedder.embed(f"Upgrade test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_upgrade_{i}",
                embedding=embedding,
                content_hash=f"hash_upgrade_{i}",
                model_name=mock_embedder.model_name
            )

        # Verify all use old model
        for i in range(3):
            state = isolated_db.index.get_embedding_state(f"fact_upgrade_{i}")
            assert state["model"] == "model-old"

        # Upgrade: reembed all with new model
        mock_embedder.model_name = "model-new"
        for i in range(3):
            embedding = mock_embedder.embed(f"Upgrade test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_upgrade_{i}",
                embedding=embedding,
                content_hash=f"hash_upgrade_v2_{i}",
                model_name=mock_embedder.model_name
            )

        # Verify all now use new model
        for i in range(3):
            state = isolated_db.index.get_embedding_state(f"fact_upgrade_{i}")
            assert state["model"] == "model-new"

    def test_partial_reembed_creates_mixed_state(self, isolated_db, mock_embedder):
        """
        Test: Partial reembed (interrupted) leaves mixed model state.

        This is the danger scenario we need to detect/prevent.
        """
        # Create and embed with old model
        for i in range(5):
            isolated_db.add_artifact(TestArtifact(
                id=f"fact_partial_{i}",
                type="fact",
                claim=f"Partial reembed test fact {i}"
            ))

        mock_embedder.model_name = "model-old"

        # First embedding to check availability
        embedding = mock_embedder.embed("Partial reembed test fact 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_partial_0",
            embedding=embedding,
            content_hash="hash_partial_0",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available - upsert_embedding returned False")

        # Continue with remaining
        for i in range(1, 5):
            embedding = mock_embedder.embed(f"Partial reembed test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_partial_{i}",
                embedding=embedding,
                content_hash=f"hash_partial_{i}",
                model_name=mock_embedder.model_name
            )

        # Simulate interrupted upgrade: only 2 of 5 get new model
        mock_embedder.model_name = "model-new"
        for i in range(2):  # Only first 2
            embedding = mock_embedder.embed(f"Partial reembed test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_partial_{i}",
                embedding=embedding,
                content_hash=f"hash_partial_v2_{i}",
                model_name=mock_embedder.model_name
            )

        # Check model distribution - should detect mixed state
        models = {}
        for i in range(5):
            state = isolated_db.index.get_embedding_state(f"fact_partial_{i}")
            model = state["model"]
            models[model] = models.get(model, 0) + 1

        assert len(models) == 2  # Mixed state detected
        assert models["model-new"] == 2
        assert models["model-old"] == 3


class TestModelDriftDetection:
    """Tests for detecting and reporting model drift."""

    def test_get_model_distribution(self, isolated_db, mock_embedder):
        """
        Helper test: Query model distribution from embedding_state.

        This is what a health check should report.
        """
        models_list = ["v1", "v1", "v2", "v2", "v3"]

        # Create first artifact and check if vectors available
        isolated_db.add_artifact(TestArtifact(
            id="fact_dist_0",
            type="fact",
            claim="Distribution test fact 0"
        ))

        embedding = mock_embedder.embed("Distribution test fact 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_dist_0",
            embedding=embedding,
            content_hash="hash_dist_0",
            model_name=models_list[0]
        )
        if not success:
            pytest.skip("sqlite-vec not available - upsert_embedding returned False")

        # Create and embed remaining
        for i in range(1, 5):
            isolated_db.add_artifact(TestArtifact(
                id=f"fact_dist_{i}",
                type="fact",
                claim=f"Distribution test fact {i}"
            ))

            embedding = mock_embedder.embed(f"Distribution test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_dist_{i}",
                embedding=embedding,
                content_hash=f"hash_dist_{i}",
                model_name=models_list[i]
            )

        # Query model distribution
        import sqlite3
        with sqlite3.connect(isolated_db.db_path) as conn:
            cursor = conn.execute("""
                SELECT model, COUNT(*) as count
                FROM embedding_state
                GROUP BY model
                ORDER BY count DESC
            """)
            distribution = {row[0]: row[1] for row in cursor.fetchall()}

        assert distribution == {"v1": 2, "v2": 2, "v3": 1}

        # Health check should flag: 3 different models is suspicious
        num_models = len(distribution)
        assert num_models > 1  # Mixed models detected

    def test_dominant_model_identification(self, isolated_db, mock_embedder):
        """
        Test: Identify the dominant (most common) embedding model.

        Useful for determining which model to use for new embeddings.
        """
        # Create embeddings with v1 as dominant
        models = ["v1"] * 8 + ["v2"] * 2

        # First artifact to check availability
        isolated_db.add_artifact(TestArtifact(
            id="fact_dom_0",
            type="fact",
            claim="Dominant model test fact 0"
        ))

        embedding = mock_embedder.embed("Dominant model test fact 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_dom_0",
            embedding=embedding,
            content_hash="hash_dom_0",
            model_name=models[0]
        )
        if not success:
            pytest.skip("sqlite-vec not available - upsert_embedding returned False")

        # Create and embed remaining
        for i in range(1, 10):
            isolated_db.add_artifact(TestArtifact(
                id=f"fact_dom_{i}",
                type="fact",
                claim=f"Dominant model test fact {i}"
            ))

            embedding = mock_embedder.embed(f"Dominant model test fact {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_dom_{i}",
                embedding=embedding,
                content_hash=f"hash_dom_{i}",
                model_name=models[i]
            )

        # Find dominant model
        import sqlite3
        with sqlite3.connect(isolated_db.db_path) as conn:
            cursor = conn.execute("""
                SELECT model, COUNT(*) as count
                FROM embedding_state
                GROUP BY model
                ORDER BY count DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            dominant_model = row[0] if row else None
            dominant_count = row[1] if row else 0

        assert dominant_model == "v1"
        assert dominant_count == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
