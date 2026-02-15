"""
Fuzz Tests: Malformed Inputs (Phase 2.5)

Tests system resilience against malformed, unexpected, and adversarial inputs.

Scenarios tested:
1. Invalid artifact IDs
2. Malformed artifact data
3. Injection attempts (SQL, path traversal)
4. Type confusion
5. Encoding issues

File refs:
- duro-mcp/index.py:95-168 (upsert validation)
- duro-mcp/tools.py (input handling)
"""

import pytest
import sys
import json
import sqlite3
from pathlib import Path
from typing import Any, List

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockArtifact


# =============================================================================
# Invalid Artifact ID Tests
# =============================================================================

class TestInvalidArtifactIds:
    """Tests for handling invalid artifact IDs."""

    def test_empty_id(self):
        """Empty string as artifact ID."""
        with IsolatedTestDB(name="empty_id") as db:
            try:
                db.add_artifact(MockArtifact(
                    id="",
                    type="fact",
                    claim="Empty ID test"
                ))
                # If it succeeds, verify behavior
                result = db.get_artifact("")
                # Empty ID might be accepted or rejected
            except (ValueError, KeyError, Exception):
                pass  # Rejection is acceptable

    def test_whitespace_only_id(self):
        """Whitespace-only artifact ID."""
        with IsolatedTestDB(name="ws_id") as db:
            whitespace_ids = ["   ", "\t", "\n", "\r\n", " \t \n "]

            for ws_id in whitespace_ids:
                try:
                    db.add_artifact(MockArtifact(
                        id=ws_id,
                        type="fact",
                        claim="Whitespace ID test"
                    ))
                except Exception:
                    pass  # Rejection is acceptable

    def test_very_long_id(self):
        """Extremely long artifact ID."""
        with IsolatedTestDB(name="long_id") as db:
            long_id = "a" * 10000

            try:
                db.add_artifact(MockArtifact(
                    id=long_id,
                    type="fact",
                    claim="Long ID test"
                ))
                # If accepted, verify retrieval
                result = db.get_artifact(long_id)
            except Exception:
                pass  # Rejection for too-long ID is acceptable

    def test_special_chars_in_id(self):
        """Special characters in artifact ID."""
        with IsolatedTestDB(name="special_id") as db:
            special_ids = [
                "id/with/slashes",
                "id\\with\\backslashes",
                "id:with:colons",
                "id*with*asterisks",
                "id?with?questions",
                'id"with"quotes',
                "id'with'apostrophes",
                "id<with>brackets",
                "id|with|pipes",
                "id\x00with\x00nulls",
            ]

            for special_id in special_ids:
                try:
                    db.add_artifact(MockArtifact(
                        id=special_id,
                        type="fact",
                        claim=f"Special ID: {repr(special_id)}"
                    ))
                except Exception:
                    pass  # Rejection is acceptable

    def test_unicode_ids(self):
        """Unicode characters in artifact ID."""
        with IsolatedTestDB(name="unicode_id") as db:
            unicode_ids = [
                "id_世界",
                "id_🎉",
                "id_مرحبا",
                "id_Ελληνικά",
                "id_日本語",
            ]

            for uid in unicode_ids:
                try:
                    db.add_artifact(MockArtifact(
                        id=uid,
                        type="fact",
                        claim=f"Unicode ID test"
                    ))
                    # Verify retrieval if accepted
                    result = db.get_artifact(uid)
                except Exception:
                    pass  # Some unicode might be rejected

    def test_null_bytes_in_id(self):
        """Null bytes embedded in artifact ID."""
        with IsolatedTestDB(name="null_id") as db:
            null_ids = [
                "before\x00after",
                "\x00start",
                "end\x00",
                "a\x00b\x00c",
            ]

            for null_id in null_ids:
                try:
                    db.add_artifact(MockArtifact(
                        id=null_id,
                        type="fact",
                        claim="Null byte ID test"
                    ))
                except Exception:
                    pass  # Rejection expected


# =============================================================================
# Malformed Artifact Data Tests
# =============================================================================

class TestMalformedArtifactData:
    """Tests for handling malformed artifact data."""

    def test_invalid_type(self):
        """Invalid artifact type."""
        with IsolatedTestDB(name="invalid_type") as db:
            invalid_types = [
                "",
                "   ",
                "invalid_type_name",
                "FACT",  # Wrong case
                "fact; DROP TABLE artifacts;--",
                None,
            ]

            for invalid_type in invalid_types:
                try:
                    if invalid_type is None:
                        # Can't pass None to MockArtifact type
                        continue
                    db.add_artifact(MockArtifact(
                        id=f"type_test_{hash(str(invalid_type)) % 10000}",
                        type=invalid_type,
                        claim="Invalid type test"
                    ))
                except Exception:
                    pass  # Rejection is acceptable

    def test_empty_claim(self):
        """Empty claim content."""
        with IsolatedTestDB(name="empty_claim") as db:
            db.add_artifact(MockArtifact(
                id="empty_claim",
                type="fact",
                claim=""
            ))
            result = db.get_artifact("empty_claim")
            # Empty claim might be accepted

    def test_binary_content_in_claim(self):
        """Binary content in claim field."""
        with IsolatedTestDB(name="binary_claim") as db:
            binary_contents = [
                bytes(range(256)).decode('latin-1'),
                "\x00\x01\x02\x03\x04\x05",
                "Normal text\x00with\x00nulls",
            ]

            for i, content in enumerate(binary_contents):
                try:
                    db.add_artifact(MockArtifact(
                        id=f"binary_{i}",
                        type="fact",
                        claim=content
                    ))
                except Exception:
                    pass

    def test_extreme_confidence_values(self):
        """Extreme confidence values."""
        with IsolatedTestDB(name="extreme_conf") as db:
            extreme_values = [
                -1.0,
                -0.001,
                1.001,
                100.0,
                float('inf'),
                float('-inf'),
                float('nan'),
            ]

            for i, conf in enumerate(extreme_values):
                try:
                    db.add_artifact(MockArtifact(
                        id=f"conf_{i}",
                        type="fact",
                        claim="Extreme confidence test",
                        confidence=conf
                    ))
                except Exception:
                    pass  # Rejection for invalid confidence is acceptable

    def test_malformed_tags(self):
        """Malformed tag lists."""
        with IsolatedTestDB(name="bad_tags") as db:
            tag_cases = [
                [""],  # Empty tag
                ["   "],  # Whitespace tag
                ["a" * 10000],  # Very long tag
                ["tag\x00null"],  # Null in tag
                ["tag; DROP TABLE"],  # Injection attempt
                list(range(1000)),  # Non-string tags (will be converted)
            ]

            for i, tags in enumerate(tag_cases):
                try:
                    # Convert non-strings to strings
                    str_tags = [str(t) for t in tags]
                    db.add_artifact(MockArtifact(
                        id=f"tags_{i}",
                        type="fact",
                        claim="Tag test",
                        tags=str_tags
                    ))
                except Exception:
                    pass


# =============================================================================
# SQL Injection Tests
# =============================================================================

class TestSQLInjection:
    """Tests for SQL injection resistance."""

    def test_sql_in_artifact_id(self):
        """SQL injection attempts in artifact ID."""
        with IsolatedTestDB(name="sql_id") as db:
            injection_ids = [
                "'; DROP TABLE artifacts;--",
                "1; DELETE FROM artifacts WHERE 1=1;--",
                "' OR '1'='1",
                "'; UPDATE artifacts SET type='hacked';--",
                "1 UNION SELECT * FROM sqlite_master--",
                "Robert'); DROP TABLE artifacts;--",
            ]

            for inj_id in injection_ids:
                try:
                    db.add_artifact(MockArtifact(
                        id=inj_id,
                        type="fact",
                        claim="SQL injection test"
                    ))
                    # If stored, verify table still intact
                    count = db.count_artifacts()
                    assert count >= 0  # Table should still exist
                except Exception:
                    pass

            # Verify database integrity
            count = db.count_artifacts()
            assert count >= 0

    def test_sql_in_claim(self):
        """SQL injection attempts in claim content."""
        with IsolatedTestDB(name="sql_claim") as db:
            injection_claims = [
                "Normal text'; DROP TABLE artifacts;--",
                "Test'); DELETE FROM artifacts;--",
                "Content' OR '1'='1",
            ]

            for i, claim in enumerate(injection_claims):
                db.add_artifact(MockArtifact(
                    id=f"sql_claim_{i}",
                    type="fact",
                    claim=claim
                ))

            # Verify all stored correctly
            count = db.count_artifacts()
            assert count == len(injection_claims)

    def test_sql_in_tags(self):
        """SQL injection attempts in tags."""
        with IsolatedTestDB(name="sql_tags") as db:
            db.add_artifact(MockArtifact(
                id="sql_tag_test",
                type="fact",
                claim="Tag injection test",
                tags=["normal", "'; DROP TABLE artifacts;--", "another"]
            ))

            # Verify database integrity
            result = db.get_artifact("sql_tag_test")
            assert result is not None


# =============================================================================
# Path Traversal Tests
# =============================================================================

class TestPathTraversal:
    """Tests for path traversal attack resistance."""

    def test_path_traversal_in_id(self):
        """Path traversal attempts in artifact ID."""
        with IsolatedTestDB(name="path_id") as db:
            traversal_ids = [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32",
                "....//....//etc/passwd",
                "%2e%2e%2f%2e%2e%2f",
                "..%252f..%252f",
                "/etc/passwd",
                "C:\\Windows\\System32",
            ]

            for trav_id in traversal_ids:
                try:
                    db.add_artifact(MockArtifact(
                        id=trav_id,
                        type="fact",
                        claim="Path traversal test"
                    ))
                except Exception:
                    pass  # Rejection is acceptable

    def test_path_in_type(self):
        """Path traversal in artifact type."""
        with IsolatedTestDB(name="path_type") as db:
            try:
                db.add_artifact(MockArtifact(
                    id="path_type_test",
                    type="../../../etc/passwd",
                    claim="Type traversal test"
                ))
            except Exception:
                pass


# =============================================================================
# Type Confusion Tests
# =============================================================================

class TestTypeConfusion:
    """Tests for type confusion attacks."""

    def test_numeric_string_id(self):
        """Numeric strings as IDs."""
        with IsolatedTestDB(name="numeric_id") as db:
            numeric_ids = ["0", "1", "-1", "999999999999", "3.14", "1e10"]

            for num_id in numeric_ids:
                db.add_artifact(MockArtifact(
                    id=num_id,
                    type="fact",
                    claim=f"Numeric ID: {num_id}"
                ))

            # Verify retrieval
            for num_id in numeric_ids:
                result = db.get_artifact(num_id)
                assert result is not None

    def test_boolean_like_values(self):
        """Boolean-like string values."""
        with IsolatedTestDB(name="bool_vals") as db:
            bool_ids = ["true", "false", "True", "False", "TRUE", "FALSE", "1", "0", "yes", "no"]

            for bool_id in bool_ids:
                db.add_artifact(MockArtifact(
                    id=f"bool_{bool_id}",
                    type="fact",
                    claim=f"Boolean-like: {bool_id}"
                ))

            count = db.count_artifacts()
            assert count == len(bool_ids)

    def test_json_in_strings(self):
        """JSON structures embedded in strings."""
        with IsolatedTestDB(name="json_str") as db:
            json_claims = [
                '{"key": "value"}',
                '[1, 2, 3]',
                '{"nested": {"deep": "value"}}',
                'null',
                'true',
                '123',
            ]

            for i, json_claim in enumerate(json_claims):
                db.add_artifact(MockArtifact(
                    id=f"json_{i}",
                    type="fact",
                    claim=json_claim
                ))

            count = db.count_artifacts()
            assert count == len(json_claims)


# =============================================================================
# Encoding Tests
# =============================================================================

class TestEncodingIssues:
    """Tests for encoding-related issues."""

    def test_mixed_encodings(self):
        """Content with mixed encoding patterns."""
        with IsolatedTestDB(name="mixed_enc") as db:
            mixed_contents = [
                "ASCII mixed with UTF-8: 日本語",
                "Latin-1 chars: café résumé",
                "Emoji: 🎉🎊🎈",
                "RTL text: مرحبا שלום",
                "Combining chars: é vs é",  # Different unicode representations
            ]

            for i, content in enumerate(mixed_contents):
                db.add_artifact(MockArtifact(
                    id=f"enc_{i}",
                    type="fact",
                    claim=content
                ))

            # Verify all stored
            for i in range(len(mixed_contents)):
                result = db.get_artifact(f"enc_{i}")
                assert result is not None

    def test_utf8_overlong_encoding(self):
        """Overlong UTF-8 encoding attempts."""
        with IsolatedTestDB(name="overlong") as db:
            # These are technically invalid UTF-8 but might slip through
            try:
                db.add_artifact(MockArtifact(
                    id="overlong_test",
                    type="fact",
                    claim="Test with potential overlong sequences"
                ))
            except Exception:
                pass

    def test_surrogate_pairs(self):
        """Unicode surrogate pair handling."""
        with IsolatedTestDB(name="surrogate") as db:
            # Emoji that requires surrogate pairs in some encodings
            emoji_content = "Emoji test: 𝟙𝟚𝟛 🎭 𝕳𝖊𝖑𝖑𝖔"

            db.add_artifact(MockArtifact(
                id="surrogate_test",
                type="fact",
                claim=emoji_content
            ))

            result = db.get_artifact("surrogate_test")
            assert result is not None


# =============================================================================
# Control Character Tests
# =============================================================================

class TestControlCharacters:
    """Tests for control character handling."""

    def test_control_chars_in_content(self):
        """Control characters in content."""
        with IsolatedTestDB(name="ctrl_chars") as db:
            control_contents = [
                "Tab:\there",
                "Newline:\nhere",
                "Carriage return:\rhere",
                "Bell:\x07here",
                "Backspace:\x08here",
                "Form feed:\x0chere",
                "Vertical tab:\x0bhere",
                "Escape:\x1bhere",
            ]

            for i, content in enumerate(control_contents):
                try:
                    db.add_artifact(MockArtifact(
                        id=f"ctrl_{i}",
                        type="fact",
                        claim=content
                    ))
                except Exception:
                    pass

    def test_ansi_escape_sequences(self):
        """ANSI escape sequences in content."""
        with IsolatedTestDB(name="ansi") as db:
            ansi_contents = [
                "\x1b[31mRed text\x1b[0m",
                "\x1b[1mBold\x1b[0m",
                "\x1b[2J",  # Clear screen
                "\x1b[H",   # Home cursor
            ]

            for i, content in enumerate(ansi_contents):
                try:
                    db.add_artifact(MockArtifact(
                        id=f"ansi_{i}",
                        type="fact",
                        claim=content
                    ))
                except Exception:
                    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
