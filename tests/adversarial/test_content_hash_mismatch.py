"""
Test: Content Hash Mismatch Detection (Priority: HIGH)

Tests that stale embeddings are detected when artifact content changes
without re-embedding.

Risk: If artifact content is updated but embedding isn't refreshed,
search results will be based on old content, leading to:
- Incorrect semantic search results
- False negatives (updated content not found)
- Misleading relevance scores

File refs:
- duro-mcp/embeddings.py:72 (compute_content_hash)
- duro-mcp/index.py:772-827 (upsert_embedding with content_hash)
- duro-mcp/index.py:get_embedding_state (returns content_hash)
"""

import pytest
import sys
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact


def compute_test_hash(content: str) -> str:
    """Compute SHA256[:16] hash like embeddings.py does."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class TestContentHashMismatch:
    """Tests for content hash mismatch detection."""

    def test_matching_hash_is_current(self, isolated_db, mock_embedder):
        """Baseline: Matching content hash indicates current embedding."""
        artifact_id = "fact_hash_match"
        content = "Python uses indentation for blocks"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim=content
        ))

        content_hash = compute_test_hash(content)
        embedding = mock_embedder.embed(content)

        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash=content_hash,
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        # Get state and verify hash matches
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state is not None
        assert state["content_hash"] == content_hash

        # Recompute hash - should match
        current_hash = compute_test_hash(content)
        assert state["content_hash"] == current_hash, "Embedding is current"

    def test_detect_stale_embedding(self, isolated_db, mock_embedder):
        """
        Test: Detect when content changes but embedding wasn't updated.

        This simulates the scenario where artifact content is modified
        but reembed wasn't run.
        """
        artifact_id = "fact_stale"
        original_content = "SQLite is a file-based database"
        updated_content = "SQLite is an embedded SQL database engine"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim=original_content
        ))

        # Embed with original content
        original_hash = compute_test_hash(original_content)
        embedding = mock_embedder.embed(original_content)

        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash=original_hash,
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        # Simulate content update (in real scenario, artifact file would be modified)
        # We just compute what the new hash would be
        updated_hash = compute_test_hash(updated_content)

        # Get stored state
        state = isolated_db.index.get_embedding_state(artifact_id)

        # Detect mismatch
        is_stale = state["content_hash"] != updated_hash
        assert is_stale, "Should detect stale embedding when content changed"

    def test_stale_detection_helper(self, isolated_db, mock_embedder):
        """
        Test: Helper function to check if embedding needs refresh.

        This documents the pattern for detecting stale embeddings.
        """
        def needs_reembed(db, artifact_id: str, current_content: str) -> bool:
            """Check if artifact needs re-embedding."""
            state = db.index.get_embedding_state(artifact_id)
            if state is None:
                return True  # No embedding exists

            current_hash = compute_test_hash(current_content)
            return state["content_hash"] != current_hash

        # Setup
        artifact_id = "fact_helper"
        content_v1 = "Version 1 content"
        content_v2 = "Version 2 content - significantly different"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim=content_v1
        ))

        # Before embedding
        assert needs_reembed(isolated_db, artifact_id, content_v1) == True

        # After embedding
        embedding = mock_embedder.embed(content_v1)
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash=compute_test_hash(content_v1),
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        assert needs_reembed(isolated_db, artifact_id, content_v1) == False

        # After content change (without re-embed)
        assert needs_reembed(isolated_db, artifact_id, content_v2) == True

    def test_batch_stale_detection(self, isolated_db, mock_embedder):
        """
        Test: Detect multiple stale embeddings in batch.

        Simulates health check that scans for stale embeddings.
        """
        NUM_ARTIFACTS = 10
        stale_indices = [2, 5, 7]  # These will have outdated embeddings

        # Create and embed all artifacts
        original_contents = {}
        for i in range(NUM_ARTIFACTS):
            artifact_id = f"fact_batch_{i}"
            content = f"Original content for artifact {i}"
            original_contents[artifact_id] = content

            isolated_db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=content
            ))

        # Embed first to check availability
        embedding = mock_embedder.embed(original_contents["fact_batch_0"])
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_batch_0",
            embedding=embedding,
            content_hash=compute_test_hash(original_contents["fact_batch_0"]),
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        # Embed remaining
        for i in range(1, NUM_ARTIFACTS):
            artifact_id = f"fact_batch_{i}"
            content = original_contents[artifact_id]
            embedding = mock_embedder.embed(content)
            isolated_db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=embedding,
                content_hash=compute_test_hash(content),
                model_name=mock_embedder.model_name
            )

        # Simulate content updates for some artifacts
        updated_contents = original_contents.copy()
        for i in stale_indices:
            artifact_id = f"fact_batch_{i}"
            updated_contents[artifact_id] = f"UPDATED content for artifact {i}"

        # Scan for stale embeddings
        stale_artifacts = []
        for i in range(NUM_ARTIFACTS):
            artifact_id = f"fact_batch_{i}"
            state = isolated_db.index.get_embedding_state(artifact_id)
            current_hash = compute_test_hash(updated_contents[artifact_id])

            if state and state["content_hash"] != current_hash:
                stale_artifacts.append(artifact_id)

        # Should detect exactly the stale ones
        expected_stale = [f"fact_batch_{i}" for i in stale_indices]
        assert sorted(stale_artifacts) == sorted(expected_stale)


class TestContentHashComputation:
    """Tests for content hash computation consistency."""

    def test_hash_deterministic(self):
        """Test: Same content produces same hash."""
        content = "Test content for hashing"

        hash1 = compute_test_hash(content)
        hash2 = compute_test_hash(content)

        assert hash1 == hash2

    def test_hash_sensitive_to_changes(self):
        """Test: Small changes produce different hash."""
        content1 = "Python is great"
        content2 = "Python is great."  # Added period
        content3 = "python is great"  # Lowercase

        hash1 = compute_test_hash(content1)
        hash2 = compute_test_hash(content2)
        hash3 = compute_test_hash(content3)

        assert hash1 != hash2, "Punctuation change should affect hash"
        assert hash1 != hash3, "Case change should affect hash"
        assert hash2 != hash3

    def test_hash_length_consistent(self):
        """Test: Hash is always 16 characters (64 bits)."""
        test_contents = [
            "",
            "a",
            "a" * 1000,
            "unicode: \u00e9\u00e8\u00ea",
            "newlines\n\nand\ttabs",
        ]

        for content in test_contents:
            h = compute_test_hash(content)
            assert len(h) == 16, f"Hash length should be 16 for '{content[:20]}...'"

    def test_embeddings_compute_content_hash(self):
        """Test: Verify embeddings.py compute_content_hash behavior."""
        from embeddings import compute_content_hash

        artifact = {
            "type": "fact",
            "data": {"claim": "Test claim content"},
            "tags": ["test"]
        }

        hash1 = compute_content_hash(artifact)
        hash2 = compute_content_hash(artifact)

        assert hash1 == hash2
        assert len(hash1) == 16

        # Changing claim should change hash
        artifact2 = {
            "type": "fact",
            "data": {"claim": "Different claim content"},
            "tags": ["test"]
        }

        hash3 = compute_content_hash(artifact2)
        assert hash1 != hash3


class TestStaleEmbeddingImpact:
    """Tests demonstrating impact of stale embeddings on search."""

    def test_stale_embedding_wrong_search_results(self, isolated_db, mock_embedder):
        """
        Demonstrate: Stale embedding leads to incorrect search ranking.

        When content changes but embedding stays the same, search results
        will be based on old content, potentially returning irrelevant results.
        """
        artifact_id = "fact_search_stale"

        # Original: about Python
        original_content = "Python is a programming language with dynamic typing"
        # Updated: about Rust (completely different topic)
        updated_content = "Rust is a systems programming language with memory safety"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim=original_content
        ))

        # Embed with original content
        embedding = mock_embedder.embed(original_content)
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash=compute_test_hash(original_content),
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        # In real scenario: artifact file is updated to updated_content
        # But embedding still reflects original_content

        # Searching for "Rust" would NOT find this artifact via semantic search
        # because the embedding is for Python content

        # Searching for "Python" WOULD find this artifact
        # even though content now says "Rust" - misleading!

        # This test documents the risk - actual search behavior depends on
        # vector similarity implementation
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state["content_hash"] == compute_test_hash(original_content)
        assert state["content_hash"] != compute_test_hash(updated_content)

    def test_refresh_fixes_stale_embedding(self, isolated_db, mock_embedder):
        """Test: Re-embedding with current content fixes stale state."""
        artifact_id = "fact_refresh"

        original_content = "Original content about databases"
        updated_content = "Updated content about cloud computing"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim=original_content
        ))

        # Initial embedding
        embedding = mock_embedder.embed(original_content)
        success = isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=embedding,
            content_hash=compute_test_hash(original_content),
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        # Verify stale after content change
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state["content_hash"] != compute_test_hash(updated_content)

        # Re-embed with updated content
        new_embedding = mock_embedder.embed(updated_content)
        isolated_db.index.upsert_embedding(
            artifact_id=artifact_id,
            embedding=new_embedding,
            content_hash=compute_test_hash(updated_content),
            model_name=mock_embedder.model_name
        )

        # Should now be current
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state["content_hash"] == compute_test_hash(updated_content)


class TestMissingEmbedding:
    """Tests for artifacts without embeddings."""

    def test_detect_missing_embedding(self, isolated_db):
        """Test: Detect artifact with no embedding."""
        artifact_id = "fact_no_embedding"

        isolated_db.add_artifact(MockArtifact(
            id=artifact_id,
            type="fact",
            claim="Artifact without embedding"
        ))

        # Should return None for missing embedding
        state = isolated_db.index.get_embedding_state(artifact_id)
        assert state is None

    def test_count_missing_embeddings(self, isolated_db, mock_embedder):
        """Test: Count artifacts missing embeddings."""
        NUM_ARTIFACTS = 10
        EMBEDDED_COUNT = 6

        # Create all artifacts
        for i in range(NUM_ARTIFACTS):
            isolated_db.add_artifact(MockArtifact(
                id=f"fact_missing_{i}",
                type="fact",
                claim=f"Missing embedding test {i}"
            ))

        # Embed only some
        embedding = mock_embedder.embed("Missing embedding test 0")
        success = isolated_db.index.upsert_embedding(
            artifact_id="fact_missing_0",
            embedding=embedding,
            content_hash="hash_0",
            model_name=mock_embedder.model_name
        )
        if not success:
            pytest.skip("sqlite-vec not available")

        for i in range(1, EMBEDDED_COUNT):
            embedding = mock_embedder.embed(f"Missing embedding test {i}")
            isolated_db.index.upsert_embedding(
                artifact_id=f"fact_missing_{i}",
                embedding=embedding,
                content_hash=f"hash_{i}",
                model_name=mock_embedder.model_name
            )

        # Count missing
        missing_count = 0
        for i in range(NUM_ARTIFACTS):
            state = isolated_db.index.get_embedding_state(f"fact_missing_{i}")
            if state is None:
                missing_count += 1

        expected_missing = NUM_ARTIFACTS - EMBEDDED_COUNT
        assert missing_count == expected_missing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
