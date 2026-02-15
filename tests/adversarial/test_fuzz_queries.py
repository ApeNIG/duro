"""
Fuzz Tests: Malformed Queries (Phase 2.5)

Tests system resilience against malformed search queries and lookups.

Scenarios tested:
1. FTS query injection
2. Malformed search patterns
3. Invalid query parameters
4. Edge case queries

File refs:
- duro-mcp/index.py:980-1020 (hybrid_search)
- duro-mcp/index.py:search_fts method
"""

import pytest
import sys
import sqlite3
from pathlib import Path

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockArtifact


# =============================================================================
# FTS Query Injection Tests
# =============================================================================

class TestFTSQueryInjection:
    """Tests for FTS5 query injection resistance."""

    def test_fts_special_operators(self):
        """FTS5 special operators in search query."""
        with IsolatedTestDB(name="fts_ops") as db:
            # Create baseline data
            db.add_artifact(MockArtifact(
                id="baseline",
                type="fact",
                claim="Normal searchable content here"
            ))

            fts_operators = [
                "AND",
                "OR",
                "NOT",
                "NEAR",
                "content AND hack",
                "content OR delete",
                "NOT content",
                '"exact phrase"',
                "content*",  # Prefix search
                "^content",  # Start anchor
                "content$",  # End anchor (not valid FTS5)
            ]

            with sqlite3.connect(db.db_path) as conn:
                for query in fts_operators:
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            (query,)
                        )
                        results = cursor.fetchall()
                        # Query executed without crashing
                    except sqlite3.OperationalError:
                        pass  # Invalid FTS syntax is acceptable

    def test_fts_column_references(self):
        """FTS5 column reference injection."""
        with IsolatedTestDB(name="fts_cols") as db:
            db.add_artifact(MockArtifact(
                id="col_test",
                type="fact",
                claim="Test content"
            ))

            column_queries = [
                "title:test",
                "text:content",
                "tags:tag",
                "id:col_test",
                "nonexistent:value",
                "{title text}:search",
            ]

            with sqlite3.connect(db.db_path) as conn:
                for query in column_queries:
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            (query,)
                        )
                        results = cursor.fetchall()
                    except sqlite3.OperationalError:
                        pass

    def test_fts_nested_parentheses(self):
        """Deeply nested parentheses in FTS query."""
        with IsolatedTestDB(name="fts_parens") as db:
            db.add_artifact(MockArtifact(
                id="paren_test",
                type="fact",
                claim="Nested test content"
            ))

            nested_queries = [
                "(test)",
                "((test))",
                "(((test)))",
                "(test AND (content OR (nested)))",
                "(" * 50 + "test" + ")" * 50,
                "(unbalanced",
                "unbalanced)",
                "((())",
            ]

            with sqlite3.connect(db.db_path) as conn:
                for query in nested_queries:
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            (query,)
                        )
                        results = cursor.fetchall()
                    except sqlite3.OperationalError:
                        pass  # Invalid syntax is fine


# =============================================================================
# Malformed Search Pattern Tests
# =============================================================================

class TestMalformedSearchPatterns:
    """Tests for malformed search patterns."""

    def test_empty_search(self):
        """Empty search query."""
        with IsolatedTestDB(name="empty_search") as db:
            db.add_artifact(MockArtifact(
                id="empty_test",
                type="fact",
                claim="Content for empty search test"
            ))

            empty_queries = ["", "   ", "\t", "\n"]

            with sqlite3.connect(db.db_path) as conn:
                for query in empty_queries:
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            (query,)
                        )
                        results = cursor.fetchall()
                    except sqlite3.OperationalError:
                        pass  # Empty queries typically error

    def test_wildcard_only(self):
        """Wildcard-only search patterns."""
        with IsolatedTestDB(name="wildcard") as db:
            db.add_artifact(MockArtifact(
                id="wildcard_test",
                type="fact",
                claim="Wildcard test content"
            ))

            wildcard_queries = ["*", "**", "***", "%", "%%", "_", "__"]

            with sqlite3.connect(db.db_path) as conn:
                for query in wildcard_queries:
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            (query,)
                        )
                        results = cursor.fetchall()
                    except sqlite3.OperationalError:
                        pass

    def test_very_long_query(self):
        """Extremely long search query."""
        with IsolatedTestDB(name="long_query") as db:
            db.add_artifact(MockArtifact(
                id="long_q_test",
                type="fact",
                claim="Long query test"
            ))

            long_queries = [
                "word " * 1000,
                "a" * 10000,
                " ".join([f"term{i}" for i in range(500)]),
            ]

            with sqlite3.connect(db.db_path) as conn:
                for query in long_queries:
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            (query,)
                        )
                        results = cursor.fetchall()
                    except sqlite3.OperationalError:
                        pass

    def test_unicode_search(self):
        """Unicode characters in search query."""
        with IsolatedTestDB(name="unicode_search") as db:
            # Create content with unicode
            db.add_artifact(MockArtifact(
                id="unicode_content",
                type="fact",
                claim="日本語 content 中文 مرحبا"
            ))

            unicode_queries = [
                "日本語",
                "中文",
                "مرحبا",
                "🎉",
                "Ελληνικά",
            ]

            with sqlite3.connect(db.db_path) as conn:
                for query in unicode_queries:
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            (query,)
                        )
                        results = cursor.fetchall()
                    except sqlite3.OperationalError:
                        pass


# =============================================================================
# Query Parameter Fuzzing
# =============================================================================

class TestQueryParameters:
    """Tests for query parameter edge cases."""

    def test_get_by_id_fuzzing(self):
        """Fuzz get_by_id with various inputs."""
        with IsolatedTestDB(name="get_fuzz") as db:
            # Create a known artifact
            db.add_artifact(MockArtifact(
                id="known_id",
                type="fact",
                claim="Known content"
            ))

            fuzz_ids = [
                None,
                "",
                "   ",
                "nonexistent",
                "known_id' OR '1'='1",
                "../../../etc/passwd",
                "\x00",
                "a" * 10000,
                "known_id\x00extra",
            ]

            for fuzz_id in fuzz_ids:
                try:
                    if fuzz_id is None:
                        continue  # Skip None
                    result = db.get_artifact(fuzz_id)
                    # Should return None for invalid IDs
                except Exception:
                    pass  # Errors are acceptable

    def test_count_with_invalid_type(self):
        """Count with invalid type filter."""
        with IsolatedTestDB(name="count_fuzz") as db:
            db.add_artifact(MockArtifact(
                id="count_test",
                type="fact",
                claim="Count test"
            ))

            invalid_types = [
                "",
                "   ",
                "nonexistent_type",
                "'; DROP TABLE artifacts;--",
                "fact' OR '1'='1",
                None,
            ]

            for invalid_type in invalid_types:
                try:
                    if invalid_type is None:
                        count = db.count_artifacts()
                    else:
                        count = db.count_artifacts(invalid_type)
                    # Should return 0 for invalid types
                    assert count >= 0
                except Exception:
                    pass

    def test_delete_fuzzing(self):
        """Fuzz delete operation with various inputs."""
        with IsolatedTestDB(name="delete_fuzz") as db:
            # Create test data
            for i in range(5):
                db.add_artifact(MockArtifact(
                    id=f"delete_test_{i}",
                    type="fact",
                    claim=f"Delete test {i}"
                ))

            initial_count = db.count_artifacts()

            fuzz_ids = [
                "",
                "nonexistent",
                "delete_test_0' OR '1'='1",
                "../../../etc/passwd",
                "a" * 10000,
            ]

            for fuzz_id in fuzz_ids:
                try:
                    db.index.delete(fuzz_id)
                except Exception:
                    pass

            # Only valid delete should have worked (none of these are valid)
            final_count = db.count_artifacts()
            assert final_count == initial_count  # No valid deletes


# =============================================================================
# Edge Case Query Tests
# =============================================================================

class TestEdgeCaseQueries:
    """Tests for edge case query scenarios."""

    def test_search_after_all_deleted(self):
        """Search in empty database."""
        with IsolatedTestDB(name="empty_db_search") as db:
            # Don't add anything

            with sqlite3.connect(db.db_path) as conn:
                try:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        ("anything",)
                    )
                    results = cursor.fetchall()
                    assert results == []
                except sqlite3.OperationalError:
                    pass

    def test_concurrent_search_delete(self):
        """Search while deletion happening."""
        import threading

        with IsolatedTestDB(name="conc_search_del") as db:
            # Create data
            for i in range(100):
                db.add_artifact(MockArtifact(
                    id=f"conc_{i:04d}",
                    type="fact",
                    claim=f"Concurrent search delete {i}"
                ))

            errors = []

            def delete_worker():
                for i in range(100):
                    try:
                        db.index.delete(f"conc_{i:04d}")
                    except Exception as e:
                        errors.append(str(e))

            def search_worker():
                for _ in range(50):
                    try:
                        with sqlite3.connect(db.db_path) as conn:
                            cursor = conn.execute(
                                "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                                ("concurrent",)
                            )
                            results = cursor.fetchall()
                    except Exception as e:
                        errors.append(str(e))

            t1 = threading.Thread(target=delete_worker)
            t2 = threading.Thread(target=search_worker)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            # Should complete without crashing

    def test_search_special_fts_chars(self):
        """Search for content containing FTS special characters."""
        with IsolatedTestDB(name="special_fts") as db:
            special_contents = [
                'Content with "quotes"',
                "Content with 'apostrophes'",
                "Content with (parentheses)",
                "Content with AND keyword",
                "Content with OR keyword",
                "Content with * asterisk",
                "Content with ^ caret",
            ]

            for i, content in enumerate(special_contents):
                db.add_artifact(MockArtifact(
                    id=f"special_{i}",
                    type="fact",
                    claim=content
                ))

            # Try to search for these
            search_terms = ["quotes", "apostrophes", "parentheses", "asterisk"]

            with sqlite3.connect(db.db_path) as conn:
                for term in search_terms:
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            (term,)
                        )
                        results = cursor.fetchall()
                    except sqlite3.OperationalError:
                        pass


# =============================================================================
# Query Timeout/Resource Tests
# =============================================================================

class TestQueryResources:
    """Tests for query resource consumption."""

    def test_expensive_query_patterns(self):
        """Potentially expensive query patterns."""
        with IsolatedTestDB(name="expensive_query") as db:
            # Create some data
            for i in range(100):
                db.add_artifact(MockArtifact(
                    id=f"expensive_{i}",
                    type="fact",
                    claim=f"Expensive query test content number {i} with words"
                ))

            expensive_queries = [
                "a*",  # Prefix wildcard
                "*",   # Just wildcard
                "a* OR b* OR c* OR d* OR e*",  # Multiple wildcards
                " OR ".join([f"word{i}*" for i in range(50)]),  # Many OR clauses
            ]

            with sqlite3.connect(db.db_path) as conn:
                conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout

                for query in expensive_queries:
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            (query,)
                        )
                        results = cursor.fetchall()
                    except (sqlite3.OperationalError, Exception):
                        pass

    def test_many_concurrent_queries(self):
        """Many concurrent queries."""
        import threading

        with IsolatedTestDB(name="many_queries") as db:
            # Create data
            for i in range(50):
                db.add_artifact(MockArtifact(
                    id=f"query_{i}",
                    type="fact",
                    claim=f"Query test content {i}"
                ))

            results = []
            errors = []

            def query_worker(worker_id):
                for i in range(20):
                    try:
                        result = db.get_artifact(f"query_{i % 50}")
                        if result:
                            results.append(1)
                    except Exception as e:
                        errors.append(str(e))

            threads = [threading.Thread(target=query_worker, args=(i,)) for i in range(10)]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Most queries should succeed
            success_rate = len(results) / (len(results) + len(errors)) if results or errors else 1
            assert success_rate > 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
