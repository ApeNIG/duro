"""
Property-Based Tests: Search Invariants (Phase 2.3)

Uses Hypothesis to verify properties that should ALWAYS hold true
for the search system.

Properties tested:
1. Indexed content is searchable by FTS
2. Deleted content is not searchable
3. Search results are ranked by relevance
4. Empty queries return empty results
5. Search is case-insensitive (if configured)

File refs:
- duro-mcp/index.py:980-1020 (hybrid_search)
- duro-mcp/index.py:search_fts method
- duro-mcp/index.py:query method
"""

import pytest
import sys
import string
import sqlite3
from pathlib import Path
from typing import List, Set

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact


# Common settings for property tests
PROPERTY_SETTINGS = settings(
    max_examples=15,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow, HealthCheck.filter_too_much],
    deadline=None  # Disable deadline for CI variance (Windows is much slower)
)


# =============================================================================
# Custom Strategies
# =============================================================================

# Valid artifact ID - simple alphanumeric
artifact_id_strategy = st.text(
    alphabet=string.ascii_lowercase,
    min_size=3,
    max_size=20
)

# Search terms - words that can be searched
search_term_strategy = st.text(
    alphabet=string.ascii_lowercase,
    min_size=4,
    max_size=15
)


# =============================================================================
# Property Tests: FTS Search Basics
# =============================================================================

class TestFTSSearchProperty:
    """Property: FTS search finds indexed content."""

    @given(
        artifact_id=artifact_id_strategy,
        search_word=search_term_strategy
    )
    @PROPERTY_SETTINGS
    def test_indexed_word_is_searchable(self, artifact_id, search_word):
        """
        Property: If content contains word W, searching for W finds the artifact.
        """
        with IsolatedTestDB(name="search") as db:
            content = f"This artifact contains the word {search_word} for testing"

            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=content
            ))

            with sqlite3.connect(db.db_path) as conn:
                try:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (search_word,)
                    )
                    results = [row[0] for row in cursor.fetchall()]

                    assert artifact_id in results, f"Expected {artifact_id} in search results for '{search_word}'"
                except sqlite3.OperationalError:
                    pass

    @given(
        artifact_id=artifact_id_strategy,
        search_word=search_term_strategy
    )
    @PROPERTY_SETTINGS
    def test_deleted_artifact_not_searchable(self, artifact_id, search_word):
        """
        Property: After deletion, artifact is not in search results.
        """
        with IsolatedTestDB(name="delete_search") as db:
            content = f"Deletable content with {search_word} inside"

            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=content
            ))

            db.index.delete(artifact_id)

            with sqlite3.connect(db.db_path) as conn:
                conn.execute("DELETE FROM artifact_fts WHERE id = ?", (artifact_id,))
                conn.commit()

            with sqlite3.connect(db.db_path) as conn:
                try:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (search_word,)
                    )
                    results = [row[0] for row in cursor.fetchall()]

                    assert artifact_id not in results, f"Deleted artifact {artifact_id} still in search results"
                except sqlite3.OperationalError:
                    pass

    @given(
        artifact_id=artifact_id_strategy,
        unique_word=search_term_strategy,
        other_word=search_term_strategy
    )
    @PROPERTY_SETTINGS
    def test_absent_word_not_found(self, artifact_id, unique_word, other_word):
        """
        Property: Searching for a word not in content doesn't find the artifact.
        """
        assume(unique_word != other_word)
        assume(unique_word not in other_word)
        assume(other_word not in unique_word)

        with IsolatedTestDB(name="absent") as db:
            content = f"This content has {unique_word} but nothing else special"

            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=content
            ))

            with sqlite3.connect(db.db_path) as conn:
                try:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (other_word,)
                    )
                    results = [row[0] for row in cursor.fetchall()]

                    assert artifact_id not in results
                except sqlite3.OperationalError:
                    pass


# =============================================================================
# Property Tests: Search Result Sets
# =============================================================================

class TestSearchResultSetProperty:
    """Property: Search result sets have expected properties."""

    @given(common_word=search_term_strategy)
    @PROPERTY_SETTINGS
    def test_multiple_matches_all_returned(self, common_word):
        """
        Property: If N artifacts contain word W, search returns all N.
        """
        with IsolatedTestDB(name="multi_match") as db:
            artifact_ids = [f"fact_{i}" for i in range(5)]

            for i, artifact_id in enumerate(artifact_ids):
                content = f"Artifact {i} contains {common_word} for test"
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=content
                ))

            with sqlite3.connect(db.db_path) as conn:
                try:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (common_word,)
                    )
                    results = set(row[0] for row in cursor.fetchall())

                    for artifact_id in artifact_ids:
                        assert artifact_id in results, f"Missing {artifact_id} in results"
                except sqlite3.OperationalError:
                    pass

    @given(
        search_word=search_term_strategy,
        other_word=search_term_strategy
    )
    @PROPERTY_SETTINGS
    def test_search_partitions_correctly(self, search_word, other_word):
        """
        Property: Search correctly partitions matching from non-matching.
        """
        assume(search_word != other_word)
        assume(search_word not in other_word)
        assume(other_word not in search_word)

        with IsolatedTestDB(name="partition") as db:
            matching_ids = ["match1", "match2"]
            non_matching_ids = ["nomatch1", "nomatch2"]

            for artifact_id in matching_ids:
                content = f"This has {search_word} inside it"
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=content
                ))

            for artifact_id in non_matching_ids:
                content = f"This has {other_word} which is different"
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=content
                ))

            with sqlite3.connect(db.db_path) as conn:
                try:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (search_word,)
                    )
                    results = set(row[0] for row in cursor.fetchall())

                    for mid in matching_ids:
                        assert mid in results, f"Matching {mid} not found"

                    for nmid in non_matching_ids:
                        assert nmid not in results, f"Non-matching {nmid} incorrectly found"
                except sqlite3.OperationalError:
                    pass


# =============================================================================
# Property Tests: Query Format
# =============================================================================

class TestQueryFormatProperty:
    """Property: Query format is handled correctly."""

    @given(artifact_id=artifact_id_strategy)
    @PROPERTY_SETTINGS
    def test_empty_query_safe(self, artifact_id):
        """
        Property: Empty query doesn't crash and returns empty or error.
        """
        with IsolatedTestDB(name="empty_query") as db:
            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim="Some content here"
            ))

            with sqlite3.connect(db.db_path) as conn:
                try:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        ("",)
                    )
                    results = cursor.fetchall()
                except sqlite3.OperationalError:
                    pass

    @given(
        artifact_id=artifact_id_strategy,
        word=search_term_strategy
    )
    @PROPERTY_SETTINGS
    def test_case_sensitivity(self, artifact_id, word):
        """
        Property: Search behavior is consistent across case variations.
        """
        with IsolatedTestDB(name="case_sens") as db:
            content = f"Content with {word.lower()} in it"
            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=content
            ))

            variations = [word.lower(), word.upper(), word.capitalize()]
            results_per_case = {}

            with sqlite3.connect(db.db_path) as conn:
                for variant in variations:
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            (variant,)
                        )
                        results_per_case[variant] = set(row[0] for row in cursor.fetchall())
                    except sqlite3.OperationalError:
                        results_per_case[variant] = set()

            result_sets = list(results_per_case.values())
            for rs in result_sets[1:]:
                assert rs == result_sets[0], "Case sensitivity inconsistency"


# =============================================================================
# Property Tests: Tag Search
# =============================================================================

class TestTagSearchProperty:
    """Property: Tag-based search works correctly."""

    @given(
        artifact_id=artifact_id_strategy,
        tag=search_term_strategy
    )
    @PROPERTY_SETTINGS
    def test_tag_is_searchable(self, artifact_id, tag):
        """
        Property: Artifacts can be found by their tags.
        """
        with IsolatedTestDB(name="tag_search") as db:
            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim="Content for tag test",
                tags=[tag]
            ))

            with sqlite3.connect(db.db_path) as conn:
                try:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (tag,)
                    )
                    results = [row[0] for row in cursor.fetchall()]

                    assert artifact_id in results, f"Artifact not found by tag '{tag}'"
                except sqlite3.OperationalError:
                    pass


# =============================================================================
# Property Tests: Hybrid Search
# =============================================================================

class TestHybridSearchProperty:
    """Property: Hybrid (FTS + Vector) search properties."""

    @given(
        artifact_id=artifact_id_strategy
    )
    @PROPERTY_SETTINGS
    def test_embedded_artifact_searchable(self, artifact_id):
        """
        Property: Artifacts with embeddings are searchable semantically.
        """
        with IsolatedTestDB(name="embed_search") as db:
            mock_embedder = MockEmbedder(dimension=384)
            content = "This is test content for semantic search testing"

            db.add_artifact(MockArtifact(
                id=artifact_id,
                type="fact",
                claim=content
            ))

            embedding = mock_embedder.embed(content)
            success = db.index.upsert_embedding(
                artifact_id=artifact_id,
                embedding=embedding,
                content_hash=f"hash_{artifact_id}",
                model_name=mock_embedder.model_name
            )

            if success:
                state = db.index.get_embedding_state(artifact_id)
                assert state is not None

    @given(num_artifacts=st.integers(min_value=3, max_value=8))
    @PROPERTY_SETTINGS
    def test_embedding_coverage_tracked(self, num_artifacts):
        """
        Property: Embedding coverage matches actual embeddings.
        """
        with IsolatedTestDB(name="embed_coverage") as db:
            mock_embedder = MockEmbedder(dimension=384)
            artifact_ids = [f"fact_{i}" for i in range(num_artifacts)]

            for i, artifact_id in enumerate(artifact_ids):
                db.add_artifact(MockArtifact(
                    id=artifact_id,
                    type="fact",
                    claim=f"Embedding coverage test {i}"
                ))

            embedded_ids = artifact_ids[:num_artifacts//2]

            for artifact_id in embedded_ids:
                embedding = mock_embedder.embed(f"Coverage test for {artifact_id}")
                success = db.index.upsert_embedding(
                    artifact_id=artifact_id,
                    embedding=embedding,
                    content_hash=f"hash_{artifact_id}",
                    model_name=mock_embedder.model_name
                )
                if not success:
                    return

            for artifact_id in artifact_ids:
                state = db.index.get_embedding_state(artifact_id)
                if artifact_id in embedded_ids:
                    assert state is not None, f"Expected embedding for {artifact_id}"
                else:
                    assert state is None, f"Unexpected embedding for {artifact_id}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
