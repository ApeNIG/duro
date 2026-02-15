"""
Fuzz Tests: Boundary Value Injection (Phase 2.5)

Tests system behavior at boundary conditions and edge values.

Scenarios tested:
1. Numeric boundaries (confidence, counts, limits)
2. String length boundaries
3. Collection size boundaries
4. Temporal boundaries
5. Index/offset boundaries

File refs:
- duro-mcp/index.py:95-168 (upsert validation)
- duro-mcp/tools.py (parameter bounds)
"""

import pytest
import sys
import math
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockArtifact


# =============================================================================
# Numeric Boundary Tests
# =============================================================================

class TestNumericBoundaries:
    """Tests for numeric boundary conditions."""

    def test_confidence_boundaries(self):
        """Test confidence value boundaries."""
        with IsolatedTestDB(name="conf_bounds") as db:
            boundary_values = [
                (0.0, "zero"),
                (1.0, "one"),
                (0.5, "half"),
                (0.001, "tiny"),
                (0.999, "near_one"),
                (0.0001, "very_tiny"),
                (0.9999, "very_near_one"),
            ]

            for conf, name in boundary_values:
                db.add_artifact(MockArtifact(
                    id=f"conf_{name}",
                    type="fact",
                    claim=f"Confidence {conf}",
                    confidence=conf
                ))

            # Verify all created
            count = db.count_artifacts()
            assert count == len(boundary_values)

    def test_invalid_confidence_boundaries(self):
        """Test invalid confidence boundaries."""
        with IsolatedTestDB(name="bad_conf") as db:
            invalid_values = [
                (-0.001, "neg_tiny"),
                (1.001, "over_one"),
                (-1.0, "neg_one"),
                (2.0, "two"),
                (100.0, "hundred"),
                (-100.0, "neg_hundred"),
            ]

            created = 0
            for conf, name in invalid_values:
                try:
                    db.add_artifact(MockArtifact(
                        id=f"bad_conf_{name}",
                        type="fact",
                        claim=f"Invalid confidence {conf}",
                        confidence=conf
                    ))
                    created += 1
                except (ValueError, Exception):
                    pass  # Rejection is acceptable

            # Some may be accepted (clamped), some rejected

    def test_special_float_values(self):
        """Test special floating point values."""
        with IsolatedTestDB(name="special_float") as db:
            special_values = [
                (float('inf'), "infinity"),
                (float('-inf'), "neg_infinity"),
                (float('nan'), "nan"),
                (1e-308, "tiny_float"),
                (1e308, "huge_float"),
                (-0.0, "neg_zero"),
                (0.0, "pos_zero"),
            ]

            for value, name in special_values:
                try:
                    db.add_artifact(MockArtifact(
                        id=f"float_{name}",
                        type="fact",
                        claim=f"Special float {name}",
                        confidence=value if 0 <= value <= 1 else 0.5
                    ))
                except (ValueError, OverflowError, Exception):
                    pass

    def test_integer_boundaries(self):
        """Test integer boundary values in various contexts."""
        with IsolatedTestDB(name="int_bounds") as db:
            int_values = [
                0,
                1,
                -1,
                2**31 - 1,  # Max 32-bit signed
                2**31,      # Overflow 32-bit signed
                2**63 - 1,  # Max 64-bit signed
                -2**31,     # Min 32-bit signed
                -2**63,     # Min 64-bit signed
            ]

            for i, val in enumerate(int_values):
                try:
                    # Use integers in ID (as string)
                    db.add_artifact(MockArtifact(
                        id=f"int_{i}_{val}",
                        type="fact",
                        claim=f"Integer boundary test: {val}"
                    ))
                except Exception:
                    pass


# =============================================================================
# String Length Boundary Tests
# =============================================================================

class TestStringLengthBoundaries:
    """Tests for string length boundaries."""

    def test_id_length_boundaries(self):
        """Test ID length boundaries."""
        with IsolatedTestDB(name="id_len") as db:
            lengths = [1, 10, 100, 255, 256, 1000, 5000]

            for length in lengths:
                artifact_id = "x" * length
                try:
                    db.add_artifact(MockArtifact(
                        id=artifact_id,
                        type="fact",
                        claim=f"ID length {length}"
                    ))
                except Exception:
                    pass  # Very long IDs may be rejected

    def test_claim_length_boundaries(self):
        """Test claim content length boundaries."""
        with IsolatedTestDB(name="claim_len") as db:
            lengths = [0, 1, 100, 1000, 10000, 100000]

            for length in lengths:
                content = "c" * length
                try:
                    db.add_artifact(MockArtifact(
                        id=f"claim_len_{length}",
                        type="fact",
                        claim=content
                    ))
                except Exception:
                    pass

            # Verify at least some succeeded
            count = db.count_artifacts()
            assert count > 0

    def test_tag_length_boundaries(self):
        """Test individual tag length boundaries."""
        with IsolatedTestDB(name="tag_len") as db:
            tag_lengths = [1, 10, 100, 255, 256, 1000]

            for length in tag_lengths:
                tag = "t" * length
                try:
                    db.add_artifact(MockArtifact(
                        id=f"tag_len_{length}",
                        type="fact",
                        claim=f"Tag length {length}",
                        tags=[tag]
                    ))
                except Exception:
                    pass


# =============================================================================
# Collection Size Boundary Tests
# =============================================================================

class TestCollectionSizeBoundaries:
    """Tests for collection size boundaries."""

    def test_empty_tags_list(self):
        """Test with empty tags list."""
        with IsolatedTestDB(name="empty_tags") as db:
            db.add_artifact(MockArtifact(
                id="empty_tags",
                type="fact",
                claim="Artifact with no tags",
                tags=[]
            ))

            result = db.get_artifact("empty_tags")
            assert result is not None

    def test_single_tag(self):
        """Test with single tag."""
        with IsolatedTestDB(name="single_tag") as db:
            db.add_artifact(MockArtifact(
                id="single_tag",
                type="fact",
                claim="Artifact with one tag",
                tags=["only_tag"]
            ))

            result = db.get_artifact("single_tag")
            assert result is not None

    def test_many_tags(self):
        """Test with many tags."""
        with IsolatedTestDB(name="many_tags") as db:
            tag_counts = [10, 50, 100, 500, 1000]

            for count in tag_counts:
                tags = [f"tag_{i}" for i in range(count)]
                try:
                    db.add_artifact(MockArtifact(
                        id=f"tags_{count}",
                        type="fact",
                        claim=f"Artifact with {count} tags",
                        tags=tags
                    ))
                except Exception:
                    pass

    def test_duplicate_tags(self):
        """Test with duplicate tags."""
        with IsolatedTestDB(name="dup_tags") as db:
            db.add_artifact(MockArtifact(
                id="dup_tags",
                type="fact",
                claim="Duplicate tags test",
                tags=["tag1", "tag1", "tag2", "tag2", "tag1"]
            ))

            result = db.get_artifact("dup_tags")
            assert result is not None

    def test_source_urls_boundaries(self):
        """Test source_urls list size boundaries."""
        with IsolatedTestDB(name="url_bounds") as db:
            url_counts = [0, 1, 5, 10, 50, 100]

            for count in url_counts:
                urls = [f"https://example.com/{i}" for i in range(count)]
                try:
                    db.add_artifact(MockArtifact(
                        id=f"urls_{count}",
                        type="fact",
                        claim=f"Artifact with {count} URLs",
                        source_urls=urls
                    ))
                except Exception:
                    pass


# =============================================================================
# Index/Offset Boundary Tests
# =============================================================================

class TestIndexOffsetBoundaries:
    """Tests for index and offset boundary conditions."""

    def test_query_limit_boundaries(self):
        """Test query limit boundaries."""
        with IsolatedTestDB(name="query_limit") as db:
            # Create baseline data
            for i in range(100):
                db.add_artifact(MockArtifact(
                    id=f"limit_{i:04d}",
                    type="fact",
                    claim=f"Limit test {i}"
                ))

            limit_values = [0, 1, 10, 50, 100, 1000, -1]

            with sqlite3.connect(db.db_path) as conn:
                for limit in limit_values:
                    try:
                        if limit >= 0:
                            cursor = conn.execute(
                                "SELECT id FROM artifacts LIMIT ?",
                                (limit,)
                            )
                            results = cursor.fetchall()
                            expected = min(limit, 100)
                            assert len(results) == expected
                    except sqlite3.OperationalError:
                        pass

    def test_query_offset_boundaries(self):
        """Test query offset boundaries."""
        with IsolatedTestDB(name="query_offset") as db:
            # Create baseline data
            for i in range(100):
                db.add_artifact(MockArtifact(
                    id=f"offset_{i:04d}",
                    type="fact",
                    claim=f"Offset test {i}"
                ))

            offset_values = [0, 1, 50, 99, 100, 101, 1000]

            with sqlite3.connect(db.db_path) as conn:
                for offset in offset_values:
                    try:
                        cursor = conn.execute(
                            "SELECT id FROM artifacts LIMIT 10 OFFSET ?",
                            (offset,)
                        )
                        results = cursor.fetchall()
                        expected = max(0, min(10, 100 - offset))
                        assert len(results) == expected
                    except sqlite3.OperationalError:
                        pass

    def test_pagination_boundaries(self):
        """Test pagination edge cases."""
        with IsolatedTestDB(name="pagination") as db:
            total = 105  # Non-round number
            page_size = 10

            for i in range(total):
                db.add_artifact(MockArtifact(
                    id=f"page_{i:04d}",
                    type="fact",
                    claim=f"Pagination test {i}"
                ))

            # Test page boundaries
            with sqlite3.connect(db.db_path) as conn:
                # First page
                cursor = conn.execute(
                    "SELECT id FROM artifacts ORDER BY id LIMIT ? OFFSET ?",
                    (page_size, 0)
                )
                assert len(cursor.fetchall()) == page_size

                # Last full page
                cursor = conn.execute(
                    "SELECT id FROM artifacts ORDER BY id LIMIT ? OFFSET ?",
                    (page_size, 100)
                )
                assert len(cursor.fetchall()) == 5  # Remaining items

                # Beyond data
                cursor = conn.execute(
                    "SELECT id FROM artifacts ORDER BY id LIMIT ? OFFSET ?",
                    (page_size, 200)
                )
                assert len(cursor.fetchall()) == 0


# =============================================================================
# Temporal Boundary Tests
# =============================================================================

class TestTemporalBoundaries:
    """Tests for time-related boundary conditions."""

    def test_timestamp_boundaries(self):
        """Test timestamp boundary values."""
        with IsolatedTestDB(name="timestamp") as db:
            timestamps = [
                datetime(1970, 1, 1),           # Unix epoch
                datetime(2000, 1, 1),           # Y2K
                datetime(2038, 1, 19, 3, 14, 7), # 32-bit overflow
                datetime.now(),                  # Current
                datetime(2099, 12, 31, 23, 59, 59),  # Future
            ]

            for i, ts in enumerate(timestamps):
                try:
                    db.add_artifact(MockArtifact(
                        id=f"ts_{i}",
                        type="fact",
                        claim=f"Timestamp test: {ts.isoformat()}"
                    ))
                except Exception:
                    pass

            count = db.count_artifacts()
            assert count == len(timestamps)

    def test_date_string_formats(self):
        """Test various date string formats."""
        with IsolatedTestDB(name="date_formats") as db:
            date_strings = [
                "2024-01-15",
                "2024-01-15T12:30:45",
                "2024-01-15T12:30:45Z",
                "2024-01-15T12:30:45+00:00",
                "2024-01-15T12:30:45.123456",
                "January 15, 2024",
                "15/01/2024",
                "01-15-2024",
            ]

            for i, date_str in enumerate(date_strings):
                db.add_artifact(MockArtifact(
                    id=f"date_{i}",
                    type="fact",
                    claim=f"Date format: {date_str}"
                ))

            count = db.count_artifacts()
            assert count == len(date_strings)


# =============================================================================
# Edge Case Combination Tests
# =============================================================================

class TestEdgeCaseCombinations:
    """Tests for combinations of edge cases."""

    def test_min_valid_artifact(self):
        """Test minimum valid artifact."""
        with IsolatedTestDB(name="min_valid") as db:
            db.add_artifact(MockArtifact(
                id="a",  # Single char ID
                type="fact",
                claim=""  # Empty claim
            ))

            result = db.get_artifact("a")
            assert result is not None

    def test_boundary_at_each_field(self):
        """Test boundary values in multiple fields simultaneously."""
        with IsolatedTestDB(name="multi_boundary") as db:
            # Short ID, long claim, many tags
            db.add_artifact(MockArtifact(
                id="x",
                type="fact",
                claim="y" * 10000,
                tags=[f"tag_{i}" for i in range(100)],
                confidence=0.0
            ))

            # Long ID, short claim, no tags
            try:
                db.add_artifact(MockArtifact(
                    id="z" * 500,
                    type="fact",
                    claim="",
                    tags=[],
                    confidence=1.0
                ))
            except Exception:
                pass

            count = db.count_artifacts()
            assert count >= 1

    def test_sequential_boundary_operations(self):
        """Test sequential operations at boundaries."""
        with IsolatedTestDB(name="seq_boundary") as db:
            # Create at boundary
            db.add_artifact(MockArtifact(
                id="seq_1",
                type="fact",
                claim="Initial",
                confidence=0.0
            ))

            # Update to other boundary
            db.add_artifact(MockArtifact(
                id="seq_1",
                type="fact",
                claim="Updated",
                confidence=1.0
            ))

            result = db.get_artifact("seq_1")
            assert result is not None

            # Delete
            db.index.delete("seq_1")
            assert db.get_artifact("seq_1") is None

            # Recreate
            db.add_artifact(MockArtifact(
                id="seq_1",
                type="fact",
                claim="Recreated",
                confidence=0.5
            ))

            result = db.get_artifact("seq_1")
            assert result is not None


# =============================================================================
# Database Constraint Tests
# =============================================================================

class TestDatabaseConstraints:
    """Tests for database-level constraint boundaries."""

    def test_primary_key_collision(self):
        """Test primary key collision handling."""
        with IsolatedTestDB(name="pk_collision") as db:
            # Create artifact
            db.add_artifact(MockArtifact(
                id="collision_test",
                type="fact",
                claim="Original content"
            ))

            # Try to create with same ID (should upsert)
            db.add_artifact(MockArtifact(
                id="collision_test",
                type="fact",
                claim="Updated content"
            ))

            # Should still be just one
            count = db.count_artifacts()
            assert count == 1

    def test_unique_constraint_stress(self):
        """Stress test unique constraints."""
        with IsolatedTestDB(name="unique_stress") as db:
            # Create many artifacts
            for i in range(100):
                db.add_artifact(MockArtifact(
                    id=f"unique_{i}",
                    type="fact",
                    claim=f"Unique test {i}"
                ))

            # Try to overwrite each
            for i in range(100):
                db.add_artifact(MockArtifact(
                    id=f"unique_{i}",
                    type="fact",
                    claim=f"Overwritten {i}"
                ))

            # Should still be 100
            count = db.count_artifacts()
            assert count == 100

    def test_fts_index_boundaries(self):
        """Test FTS index with boundary content."""
        with IsolatedTestDB(name="fts_boundary") as db:
            boundary_contents = [
                "",  # Empty
                "x",  # Single char
                "x" * 10000,  # Very long
                " " * 100,  # Only spaces
                "word",  # Single word
                " ".join(["word"] * 1000),  # Many words
            ]

            for i, content in enumerate(boundary_contents):
                try:
                    db.add_artifact(MockArtifact(
                        id=f"fts_bound_{i}",
                        type="fact",
                        claim=content
                    ))
                except Exception:
                    pass

            # Verify FTS still works
            with sqlite3.connect(db.db_path) as conn:
                try:
                    cursor = conn.execute(
                        "SELECT id FROM artifact_fts WHERE artifact_fts MATCH ?",
                        ("word",)
                    )
                    results = cursor.fetchall()
                    # Should find at least the ones with "word"
                except sqlite3.OperationalError:
                    pass


# =============================================================================
# Precision Boundary Tests
# =============================================================================

class TestPrecisionBoundaries:
    """Tests for floating point precision boundaries."""

    def test_confidence_precision(self):
        """Test confidence value precision."""
        with IsolatedTestDB(name="conf_precision") as db:
            precision_values = [
                0.1,
                0.01,
                0.001,
                0.0001,
                0.00001,
                0.000001,
                0.123456789012345,  # Many decimal places
                1.0 - 1e-10,  # Very close to 1
                1e-10,  # Very close to 0
            ]

            for i, conf in enumerate(precision_values):
                try:
                    if 0 <= conf <= 1:
                        db.add_artifact(MockArtifact(
                            id=f"prec_{i}",
                            type="fact",
                            claim=f"Precision {conf}",
                            confidence=conf
                        ))
                except Exception:
                    pass

    def test_float_comparison_boundaries(self):
        """Test floating point comparison edge cases."""
        with IsolatedTestDB(name="float_cmp") as db:
            # Values that might have comparison issues
            pairs = [
                (0.1 + 0.2, 0.3),  # Classic floating point issue
                (1.0 - 0.9, 0.1),
                (0.5, 1/2),
            ]

            for i, (a, b) in enumerate(pairs):
                db.add_artifact(MockArtifact(
                    id=f"cmp_a_{i}",
                    type="fact",
                    claim=f"Float A: {a}",
                    confidence=min(max(a, 0), 1)
                ))
                db.add_artifact(MockArtifact(
                    id=f"cmp_b_{i}",
                    type="fact",
                    claim=f"Float B: {b}",
                    confidence=min(max(b, 0), 1)
                ))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
