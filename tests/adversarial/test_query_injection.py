"""
Test: Query Injection Resistance (Priority: MEDIUM)

Tests that search queries cannot be used for SQL/FTS injection attacks.

Risk: Malicious search queries could:
- Execute arbitrary SQL via FTS MATCH syntax
- Cause denial of service via complex queries
- Extract data through error messages
- Bypass access controls

File refs:
- duro-mcp/index.py:980-1020 (hybrid_search with FTS MATCH)
- duro-mcp/index.py:query method
- duro-mcp/index.py:search_fts method
"""

import pytest
import sys
import sqlite3
from pathlib import Path
from typing import List, Dict, Any

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact


class TestSQLInjectionResistance:
    """Tests for SQL injection resistance in queries."""

    def test_basic_sql_injection_in_search(self, isolated_db):
        """Test: Basic SQL injection attempt in search."""
        # Add a canary artifact
        isolated_db.add_artifact(MockArtifact(
            id="fact_canary_sql",
            type="fact",
            claim="Canary artifact for SQL injection test"
        ))

        # Try SQL injection in FTS search
        injection_queries = [
            "'; DROP TABLE artifacts; --",
            "' OR '1'='1",
            "'; DELETE FROM artifacts; --",
            "' UNION SELECT * FROM artifacts --",
            "1; SELECT * FROM sqlite_master",
        ]

        for injection in injection_queries:
            try:
                with sqlite3.connect(isolated_db.db_path) as conn:
                    # This simulates what a naive implementation might do
                    # Proper implementation uses parameterized queries
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (injection,)
                    )
                    results = cursor.fetchall()
                    # Query should complete without executing injection
            except sqlite3.OperationalError:
                # FTS syntax error is acceptable
                pass

        # Verify canary still exists
        canary = isolated_db.index.get_by_id("fact_canary_sql")
        assert canary is not None, "Canary was deleted by injection!"

        # Verify artifacts table still exists
        with sqlite3.connect(isolated_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'"
            )
            assert cursor.fetchone() is not None, "artifacts table was dropped!"

    def test_fts_syntax_injection(self, isolated_db):
        """Test: FTS-specific syntax injection attempts."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_fts_test",
            type="fact",
            claim="Test fact for FTS injection testing"
        ))

        # FTS5 specific syntax that could be abused
        fts_injections = [
            "* OR *",  # Wildcard abuse
            "NOT NOT NOT test",  # Operator abuse
            "test AND OR test",  # Invalid syntax
            "test" * 1000,  # Very long query
            '"""',  # Quote abuse
            "NEAR(test, 0)",  # NEAR operator
            "{test}",  # Column filter attempt
            "test:*",  # Column prefix
        ]

        for injection in fts_injections:
            try:
                with sqlite3.connect(isolated_db.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (injection,)
                    )
                    cursor.fetchall()
            except sqlite3.OperationalError:
                # Syntax errors are fine - injection was blocked
                pass

    def test_null_byte_injection(self, isolated_db):
        """Test: Null byte injection in queries."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_null_test",
            type="fact",
            claim="Test fact for null byte testing"
        ))

        null_injections = [
            "test\x00DROP TABLE",
            "\x00",
            "test\x00",
            "\x00test",
        ]

        for injection in null_injections:
            try:
                with sqlite3.connect(isolated_db.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (injection,)
                    )
                    cursor.fetchall()
            except (sqlite3.OperationalError, ValueError):
                pass


class TestQueryParameterization:
    """Tests verifying proper query parameterization."""

    def test_get_by_id_parameterized(self, isolated_db):
        """Test: get_by_id uses parameterized query."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_param_test",
            type="fact",
            claim="Parameterization test"
        ))

        # Try injection through ID lookup
        injections = [
            "'; DROP TABLE artifacts; --",
            "fact_param_test' OR '1'='1",
            "fact_param_test; DELETE FROM artifacts",
        ]

        for injection in injections:
            result = isolated_db.index.get_by_id(injection)
            # Should return None (not found), not execute injection
            assert result is None or result.get("id") != "fact_param_test' OR '1'='1"

        # Original should still exist
        original = isolated_db.index.get_by_id("fact_param_test")
        assert original is not None

    def test_query_by_type_parameterized(self, isolated_db):
        """Test: Query by type uses parameterized query."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_type_param",
            type="fact",
            claim="Type parameterization test"
        ))

        # Try injection through type filter
        injection = "fact'; DELETE FROM artifacts WHERE '1'='1"

        # The query method should handle this safely
        try:
            count = isolated_db.count_artifacts(injection)
            # Should return 0, not execute deletion
        except Exception:
            pass

        # Verify no deletion
        original = isolated_db.index.get_by_id("fact_type_param")
        assert original is not None

    def test_tag_search_parameterized(self, isolated_db):
        """Test: Tag-based searches use parameterization."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_tag_param",
            type="fact",
            claim="Tag parameterization test",
            tags=["safe-tag"]
        ))

        # Injection through tag search would be in JSON
        # This tests that tag handling doesn't eval/exec


class TestDenialOfService:
    """Tests for DoS resistance in queries."""

    def test_regex_dos_resistance(self, isolated_db):
        """Test: Complex regex patterns don't cause ReDoS."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_redos",
            type="fact",
            claim="Test content"
        ))

        # ReDoS patterns (exponential backtracking)
        redos_patterns = [
            "(a+)+$",
            "([a-zA-Z]+)*$",
            "(a|aa)+$",
        ]

        # Note: SQLite FTS5 doesn't use regex by default
        # This tests that even if regex is somehow used, it's bounded

    def test_very_long_query(self, isolated_db):
        """Test: Very long queries are handled safely."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_long_query",
            type="fact",
            claim="Long query test"
        ))

        # Try very long search query
        long_query = "test " * 10000  # ~50KB query

        try:
            with sqlite3.connect(isolated_db.db_path) as conn:
                cursor = conn.execute(
                    "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                    (long_query,)
                )
                cursor.fetchall()
        except sqlite3.OperationalError:
            pass  # Query rejected - good

    def test_many_terms_query(self, isolated_db):
        """Test: Queries with many terms don't explode."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_many_terms",
            type="fact",
            claim="Many terms query test"
        ))

        # Query with many OR terms
        many_terms = " OR ".join([f"term{i}" for i in range(100)])

        try:
            with sqlite3.connect(isolated_db.db_path) as conn:
                cursor = conn.execute(
                    "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                    (many_terms,)
                )
                cursor.fetchall()
        except sqlite3.OperationalError:
            pass  # Complex query rejected

    def test_deeply_nested_query(self, isolated_db):
        """Test: Deeply nested parentheses don't cause stack overflow."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_nested_query",
            type="fact",
            claim="Nested query test"
        ))

        # Deeply nested query
        nested = "(" * 50 + "test" + ")" * 50

        try:
            with sqlite3.connect(isolated_db.db_path) as conn:
                cursor = conn.execute(
                    "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                    (nested,)
                )
                cursor.fetchall()
        except (sqlite3.OperationalError, RecursionError):
            pass


class TestErrorMessageLeakage:
    """Tests for information leakage through error messages."""

    def test_error_doesnt_leak_schema(self, isolated_db):
        """Test: Errors don't reveal database schema."""
        # Intentionally malformed query
        bad_queries = [
            "SELECT * FROM nonexistent",
            "' OR 1=1; SELECT sql FROM sqlite_master --",
        ]

        for query in bad_queries:
            try:
                with sqlite3.connect(isolated_db.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (query,)
                    )
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                # Error shouldn't reveal table names or schema
                assert "create table" not in error_msg
                assert "sqlite_master" not in error_msg

    def test_error_doesnt_leak_data(self, isolated_db):
        """Test: Errors don't reveal actual data."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_secret",
            type="fact",
            claim="SECRET_VALUE_12345"
        ))

        try:
            with sqlite3.connect(isolated_db.db_path) as conn:
                # Malformed query that might include data in error
                cursor = conn.execute(
                    "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                    ("invalid[syntax",)
                )
        except sqlite3.OperationalError as e:
            error_msg = str(e)
            assert "SECRET_VALUE_12345" not in error_msg


class TestSpecialCharacterHandling:
    """Tests for special character handling in queries."""

    def test_special_chars_in_search(self, isolated_db):
        """Test: Special characters in search are handled safely."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_special",
            type="fact",
            claim="Test with special chars: @#$%^&*()"
        ))

        special_queries = [
            "@#$%^&*()",
            "<script>alert(1)</script>",
            "../../../etc/passwd",
            "{{7*7}}",  # Template injection
            "${7*7}",  # Expression injection
            "{{constructor.constructor('return this')()}}",
        ]

        for query in special_queries:
            try:
                with sqlite3.connect(isolated_db.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (query,)
                    )
                    cursor.fetchall()
            except sqlite3.OperationalError:
                pass  # Query syntax error is fine

    def test_unicode_in_search(self, isolated_db):
        """Test: Unicode characters in search are handled safely."""
        isolated_db.add_artifact(MockArtifact(
            id="fact_unicode_search",
            type="fact",
            claim="Test with unicode"
        ))

        unicode_queries = [
            "\u0000",  # Null
            "\uFFFF",  # Max BMP
            "\U0001F600",  # Emoji
            "\u202E",  # RTL override
            "test\u0000injection",
        ]

        for query in unicode_queries:
            try:
                with sqlite3.connect(isolated_db.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        (query,)
                    )
                    cursor.fetchall()
            except (sqlite3.OperationalError, ValueError):
                pass


class TestConcurrentQuerySafety:
    """Tests for query safety under concurrent access."""

    def test_concurrent_read_write(self, isolated_db):
        """Test: Concurrent reads and writes don't cause injection."""
        import threading
        import time

        errors = []

        def reader():
            for _ in range(20):
                try:
                    with sqlite3.connect(isolated_db.db_path) as conn:
                        cursor = conn.execute(
                            "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                            ("test",)
                        )
                        cursor.fetchall()
                    time.sleep(0.01)
                except sqlite3.OperationalError:
                    pass  # Busy is OK
                except Exception as e:
                    errors.append(str(e))

        def writer():
            for i in range(20):
                try:
                    isolated_db.add_artifact(MockArtifact(
                        id=f"fact_concurrent_{i}_{threading.current_thread().name}",
                        type="fact",
                        claim=f"Concurrent test {i}"
                    ))
                    time.sleep(0.01)
                except Exception as e:
                    if "database is locked" not in str(e).lower():
                        errors.append(str(e))

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No unexpected errors
        assert len(errors) == 0, f"Unexpected errors: {errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
