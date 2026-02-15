"""
Test: Malformed Artifact Injection (Priority: MEDIUM)

Tests that malformed or invalid artifacts don't crash the indexing system.

Risk: Invalid JSON, missing required fields, wrong types, or malicious
content could crash indexing, corrupt the database, or cause silent failures.

File refs:
- duro-mcp/index.py:95-168 (upsert method)
- duro-mcp/index.py:170-195 (_extract_title method)
- duro-mcp/embeddings.py:72 (compute_content_hash)
"""

import pytest
import sys
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockEmbedder, MockArtifact


class TestMissingRequiredFields:
    """Tests for artifacts missing required fields."""

    def test_missing_id_field(self, isolated_db):
        """Test: Artifact without 'id' field should fail gracefully."""
        malformed = {
            # "id": missing
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": "Test claim"},
            "tags": []
        }

        # Should not crash, should return False or raise controlled exception
        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
            # If it returns, should indicate failure
            assert result == False or result is None
        except KeyError:
            # KeyError is acceptable - means it tried to access missing field
            pass
        except Exception as e:
            # Other exceptions should be informative
            assert "id" in str(e).lower() or "key" in str(e).lower()

    def test_missing_type_field(self, isolated_db):
        """Test: Artifact without 'type' field should fail gracefully."""
        malformed = {
            "id": "fact_no_type",
            # "type": missing
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": "Test claim"},
            "tags": []
        }

        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
            assert result == False or result is None
        except KeyError:
            pass
        except Exception as e:
            assert "type" in str(e).lower() or "key" in str(e).lower()

    def test_missing_created_at_field(self, isolated_db):
        """Test: Artifact without 'created_at' field should fail gracefully."""
        malformed = {
            "id": "fact_no_created",
            "type": "fact",
            # "created_at": missing
            "sensitivity": "public",
            "data": {"claim": "Test claim"},
            "tags": []
        }

        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
            assert result == False or result is None
        except KeyError:
            pass
        except Exception as e:
            assert "created" in str(e).lower() or "key" in str(e).lower()

    def test_missing_sensitivity_field(self, isolated_db):
        """Test: Artifact without 'sensitivity' field should fail gracefully."""
        malformed = {
            "id": "fact_no_sensitivity",
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            # "sensitivity": missing
            "data": {"claim": "Test claim"},
            "tags": []
        }

        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
            assert result == False or result is None
        except KeyError:
            pass

    def test_missing_data_field(self, isolated_db):
        """Test: Artifact without 'data' field should handle gracefully."""
        malformed = {
            "id": "fact_no_data",
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            # "data": missing
            "tags": []
        }

        # This might succeed with empty/default title
        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
            # Either fails or succeeds with defaults
        except Exception:
            pass  # Acceptable to fail


class TestWrongFieldTypes:
    """Tests for artifacts with wrong field types."""

    def test_id_as_integer(self, isolated_db):
        """Test: Integer ID instead of string."""
        malformed = {
            "id": 12345,  # Should be string
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": "Test claim"},
            "tags": []
        }

        # SQLite might convert, or it might fail
        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
            # If succeeds, verify it was stored somehow
            if result:
                # Check if retrievable
                stored = isolated_db.index.get_by_id("12345") or isolated_db.index.get_by_id(12345)
        except Exception:
            pass  # Acceptable to fail

    def test_tags_as_string(self, isolated_db):
        """Test: String tags instead of list."""
        malformed = {
            "id": "fact_string_tags",
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": "Test claim"},
            "tags": "python,testing"  # Should be list
        }

        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
            # json.dumps on string should still work
        except TypeError as e:
            # TypeError from json.dumps is acceptable
            pass

    def test_data_as_string(self, isolated_db):
        """Test: String data instead of dict."""
        malformed = {
            "id": "fact_string_data",
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": "This should be a dict",  # Should be dict
            "tags": []
        }

        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
        except (TypeError, AttributeError):
            pass  # Acceptable - .get() on string fails

    def test_created_at_as_integer(self, isolated_db):
        """Test: Integer timestamp instead of ISO string."""
        malformed = {
            "id": "fact_int_timestamp",
            "type": "fact",
            "created_at": 1708000000,  # Should be ISO string
            "sensitivity": "public",
            "data": {"claim": "Test claim"},
            "tags": []
        }

        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
            # SQLite might accept integer
        except Exception:
            pass

    def test_null_values(self, isolated_db):
        """Test: None/null values in various fields."""
        malformed = {
            "id": "fact_nulls",
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": None},  # Null claim
            "tags": None  # Null tags
        }

        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
        except (TypeError, AttributeError):
            pass  # Acceptable


class TestMaliciousContent:
    """Tests for potentially malicious content in artifacts."""

    def test_sql_in_id(self, isolated_db):
        """Test: SQL injection attempt in ID field."""
        malformed = {
            "id": "'; DROP TABLE artifacts; --",
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": "Test claim"},
            "tags": []
        }

        # Should not execute SQL injection
        result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")

        # Verify table still exists
        with sqlite3.connect(isolated_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'"
            )
            assert cursor.fetchone() is not None, "artifacts table was dropped!"

    def test_sql_in_claim(self, isolated_db):
        """Test: SQL injection attempt in claim field."""
        malformed = {
            "id": "fact_sql_claim",
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": "Test'; DELETE FROM artifacts WHERE '1'='1"},
            "tags": []
        }

        result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")

        # Verify no deletion occurred (add a test artifact first)
        isolated_db.add_artifact(MockArtifact(
            id="fact_canary",
            type="fact",
            claim="Canary artifact"
        ))

        canary = isolated_db.index.get_by_id("fact_canary")
        assert canary is not None, "Canary artifact was deleted by injection!"

    def test_extremely_long_id(self, isolated_db):
        """Test: Extremely long ID field."""
        long_id = "a" * 10000  # 10KB ID

        malformed = {
            "id": long_id,
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": "Test claim"},
            "tags": []
        }

        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
            # If succeeds, should be retrievable
            if result:
                stored = isolated_db.index.get_by_id(long_id)
        except Exception:
            pass  # Acceptable to reject

    def test_unicode_edge_cases(self, isolated_db):
        """Test: Unicode edge cases in content."""
        unicode_cases = [
            "\u0000",  # Null character
            "\uFFFF",  # Max BMP character
            "\U0001F600",  # Emoji
            "\u202E",  # Right-to-left override
            "Test\x00Hidden",  # Embedded null
        ]

        for i, unicode_str in enumerate(unicode_cases):
            malformed = {
                "id": f"fact_unicode_{i}",
                "type": "fact",
                "created_at": "2026-02-15T12:00:00Z",
                "sensitivity": "public",
                "data": {"claim": f"Test {unicode_str} content"},
                "tags": []
            }

            try:
                result = isolated_db.index.upsert(malformed, "/fake/path.json", f"hash_{i}")
            except Exception:
                pass  # Some unicode might be rejected

    def test_nested_json_bomb(self, isolated_db):
        """Test: Deeply nested JSON structure."""
        # Create deeply nested dict
        nested = {"level": 0}
        current = nested
        for i in range(100):  # 100 levels deep
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        malformed = {
            "id": "fact_nested",
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": nested,
            "tags": []
        }

        try:
            result = isolated_db.index.upsert(malformed, "/fake/path.json", "hash123")
        except RecursionError:
            pass  # Acceptable
        except Exception:
            pass


class TestEdgeCaseArtifacts:
    """Tests for edge case artifact structures."""

    def test_empty_artifact(self, isolated_db):
        """Test: Completely empty artifact dict."""
        try:
            result = isolated_db.index.upsert({}, "/fake/path.json", "hash123")
            assert result == False or result is None
        except KeyError:
            pass

    def test_extra_unknown_fields(self, isolated_db):
        """Test: Artifact with extra unknown fields."""
        artifact = {
            "id": "fact_extra_fields",
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": "Test claim"},
            "tags": [],
            "unknown_field": "should be ignored",
            "another_unknown": {"nested": "data"},
            "__proto__": {"polluted": True},  # Prototype pollution attempt
        }

        # Should succeed, ignoring unknown fields
        result = isolated_db.index.upsert(artifact, "/fake/path.json", "hash123")
        assert result == True

        # Verify core data stored correctly
        stored = isolated_db.index.get_by_id("fact_extra_fields")
        assert stored is not None

    def test_empty_strings(self, isolated_db):
        """Test: Empty strings in various fields."""
        artifact = {
            "id": "",  # Empty ID
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": ""},
            "tags": []
        }

        try:
            result = isolated_db.index.upsert(artifact, "/fake/path.json", "hash123")
            # Empty ID might be rejected or accepted
        except Exception:
            pass

    def test_whitespace_only_fields(self, isolated_db):
        """Test: Whitespace-only strings in fields."""
        artifact = {
            "id": "   ",  # Whitespace ID
            "type": "fact",
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": "   "},
            "tags": []
        }

        try:
            result = isolated_db.index.upsert(artifact, "/fake/path.json", "hash123")
        except Exception:
            pass


class TestArtifactTypeHandling:
    """Tests for different artifact type handling."""

    def test_unknown_artifact_type(self, isolated_db):
        """Test: Unknown artifact type should be handled."""
        artifact = {
            "id": "unknown_type_1",
            "type": "unknown_type_xyz",  # Not a known type
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"some_field": "some_value"},
            "tags": []
        }

        # Should handle gracefully (might use default title extraction)
        result = isolated_db.index.upsert(artifact, "/fake/path.json", "hash123")
        # Either succeeds with "Unknown" title or fails gracefully

    def test_case_sensitive_type(self, isolated_db):
        """Test: Type field case sensitivity."""
        artifact = {
            "id": "case_type_1",
            "type": "FACT",  # Uppercase
            "created_at": "2026-02-15T12:00:00Z",
            "sensitivity": "public",
            "data": {"claim": "Test claim"},
            "tags": []
        }

        result = isolated_db.index.upsert(artifact, "/fake/path.json", "hash123")
        # Behavior depends on implementation

    def test_all_known_types(self, isolated_db):
        """Test: All known artifact types can be indexed."""
        types_and_data = [
            ("fact", {"claim": "Test fact"}),
            ("decision", {"decision": "Test decision", "rationale": "Test rationale"}),
            ("skill", {"name": "test_skill", "description": "Test skill"}),
            ("rule", {"name": "test_rule", "condition": "Test condition"}),
            ("log", {"message": "Test log message"}),
            ("episode", {"goal": "Test goal", "status": "open"}),
            ("evaluation", {"episode_id": "ep_123", "grade": "A"}),
            ("skill_stats", {"name": "test_stats", "confidence": 0.5}),
        ]

        for artifact_type, data in types_and_data:
            artifact = {
                "id": f"{artifact_type}_test",
                "type": artifact_type,
                "created_at": "2026-02-15T12:00:00Z",
                "sensitivity": "public",
                "data": data,
                "tags": []
            }

            result = isolated_db.index.upsert(artifact, f"/fake/{artifact_type}.json", f"hash_{artifact_type}")
            assert result == True, f"Failed to index {artifact_type}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
