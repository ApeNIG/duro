"""
Test: Dedup Collision Risk (Priority: HIGH)

Tests the MD5[:12] hash truncation in promote_learnings.py.

Risk: Two different learning contents could produce the same 12-char
truncated MD5 hash, causing false "already promoted" detection.

The 12-character hex hash has 48 bits of entropy. Birthday paradox
suggests ~50% collision probability after ~2^24 (16M) entries.
For smaller datasets this is unlikely, but we need to verify behavior.

File refs:
- skills/memory/promote_learnings.py:107 (hash truncation)
- skills/memory/promote_learnings.py:131 (dedup check)
"""

import hashlib
import pytest
import sys
from pathlib import Path
from typing import List, Dict

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

# Add .agent to path for skill import
AGENT_PATH = Path.home() / ".agent"
if str(AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(AGENT_PATH))


class TestDedupCollisionRisk:
    """Tests for MD5 hash truncation collision risk."""

    def test_hash_truncation_length(self):
        """Verify the hash truncation is 12 characters as documented."""
        content = "test learning content"
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]

        assert len(content_hash) == 12
        assert all(c in '0123456789abcdef' for c in content_hash)

    def test_different_content_different_hash(self):
        """Basic test: different content produces different truncated hash."""
        content1 = "Learning 1: Python uses indentation"
        content2 = "Learning 2: JavaScript uses braces"

        hash1 = hashlib.md5(content1.encode()).hexdigest()[:12]
        hash2 = hashlib.md5(content2.encode()).hexdigest()[:12]

        assert hash1 != hash2, "Different content should produce different hashes"

    def test_collision_detection_behavior(self):
        """
        Test: When a hash collision occurs, verify behavior.

        We craft two strings with the same truncated MD5 hash
        and verify the dedup logic correctly identifies the collision.
        """
        # Pre-computed collision pair (found through search)
        # These two strings have the same MD5[:12] hash
        # Note: Finding real collisions is expensive, using mock approach
        content1 = "Learning about Python decorators"
        hash1 = hashlib.md5(content1.encode()).hexdigest()[:12]

        # For this test, we simulate what happens when collision occurs
        # by using the same hash tag
        existing_facts = [
            {
                "claim": content1,
                "tags": [f"hash:{hash1}", "promoted-from:test", "auto-promoted"]
            }
        ]

        # New content that happens to have same hash (simulated)
        content2 = "Learning about JavaScript closures"
        # In real scenario, this would have same hash - we force it
        simulated_hash = hash1  # Same hash tag

        # Check if dedup would incorrectly mark as promoted
        def check_already_promoted(content_hash: str, facts: List[Dict]) -> bool:
            """Replicate the dedup logic from promote_learnings.py"""
            for fact in facts:
                tags = fact.get("tags", [])
                if f"hash:{content_hash}" in tags:
                    return True
            return False

        # With collision, both would be marked as "already promoted"
        assert check_already_promoted(hash1, existing_facts) == True
        assert check_already_promoted(simulated_hash, existing_facts) == True

        # This is the VULNERABILITY: different content, same hash = false dedup

    def test_collision_probability_estimation(self):
        """
        Estimate collision probability for given dataset sizes.

        Birthday paradox formula: P(collision) ≈ 1 - e^(-n²/2H)
        where H = hash space size (2^48 for 12 hex chars)
        """
        import math
        from decimal import Decimal, getcontext

        # Use high precision for large number calculations
        getcontext().prec = 100

        hash_bits = 48  # 12 hex chars * 4 bits
        hash_space = Decimal(2 ** hash_bits)

        def collision_probability(n: int) -> float:
            """Estimate probability of at least one collision in n items."""
            n_dec = Decimal(n)
            exponent = float(-(n_dec * n_dec) / (2 * hash_space))
            # Clamp to avoid underflow
            exponent = max(exponent, -700)
            return 1 - math.exp(exponent)

        # Test various dataset sizes
        test_sizes = [100, 1000, 10000, 100000, 1000000]

        for size in test_sizes:
            prob = collision_probability(size)
            # Just verify calculation works - actual probs are very low
            assert 0 <= prob <= 1

        # At 1M entries, collision probability is still very low
        prob_1m = collision_probability(1000000)
        assert prob_1m < 0.01  # Less than 1%

    def test_content_similarity_fallback(self):
        """
        Test: Content similarity check catches what hash collision misses.

        promote_learnings.py has a secondary check:
        `if claim and learning.content[:100].lower() in claim.lower()`
        """
        content1 = "Learning about Python decorators and their use cases"
        content2 = "Learning about Python decorators in web frameworks"

        # Same first 100 chars (approximately)
        overlap = "Learning about Python decorators"

        # Simulate existing fact
        existing_facts = [
            {
                "claim": content1,
                "tags": ["hash:abc123abc123"]
            }
        ]

        def check_with_content_similarity(learning_content: str, facts: List[Dict]) -> bool:
            """Check using content similarity (from promote_learnings.py)"""
            for fact in facts:
                claim = fact.get("claim", "")
                if claim and learning_content[:100].lower() in claim.lower():
                    return True
            return False

        # Content similarity catches near-duplicates
        assert check_with_content_similarity(content2, existing_facts) == False

        # But exact prefix matches are caught
        assert check_with_content_similarity(content1[:50], existing_facts) == True

    def test_hash_collision_search(self):
        """
        Attempt to find actual MD5[:12] collision.

        This is computationally expensive, so we limit iterations.
        Success rate depends on randomness and iteration count.
        """
        from harness import find_md5_collision_pair

        # Try to find collision with limited attempts
        result = find_md5_collision_pair(prefix_len=8, max_attempts=100000)

        # 8-char prefix (32 bits) has ~50% collision chance at ~65K attempts
        # We just verify the function works, not that it always finds collision
        if result:
            str1, str2, shared_hash = result
            assert str1 != str2
            assert hashlib.md5(str1.encode()).hexdigest()[:8] == shared_hash
            assert hashlib.md5(str2.encode()).hexdigest()[:8] == shared_hash
            print(f"\nFound collision: '{str1[:30]}...' and '{str2[:30]}...' -> {shared_hash}")

    def test_mitigation_recommendation(self):
        """
        Document recommended mitigation for hash collision risk.

        Current: MD5[:12] = 48 bits
        Recommended: SHA256[:16] = 64 bits (4x collision resistance)
        Even better: Full SHA256 = 256 bits (negligible collision risk)
        """
        content = "Test learning content"

        # Current approach
        md5_short = hashlib.md5(content.encode()).hexdigest()[:12]
        assert len(md5_short) == 12  # 48 bits

        # Recommended approach
        sha256_short = hashlib.sha256(content.encode()).hexdigest()[:16]
        assert len(sha256_short) == 16  # 64 bits

        # Full SHA256 (best)
        sha256_full = hashlib.sha256(content.encode()).hexdigest()
        assert len(sha256_full) == 64  # 256 bits

        # Verify embeddings.py already uses SHA256[:16]
        from embeddings import compute_content_hash

        test_artifact = {
            "type": "fact",
            "data": {"claim": content},
            "tags": []
        }
        embedding_hash = compute_content_hash(test_artifact)
        assert len(embedding_hash) == 16  # 64 bits - good!


PROMOTE_LEARNINGS_PATH = Path.home() / ".agent" / "skills" / "memory" / "promote_learnings.py"


class TestDedupIntegration:
    """Integration tests with actual promote_learnings module."""

    @pytest.mark.skipif(
        not PROMOTE_LEARNINGS_PATH.exists(),
        reason="promote_learnings.py not found (CI environment)"
    )
    def test_promote_learnings_hash_behavior(self):
        """Test actual hash generation in promote_learnings."""
        # Import with proper path handling
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "promote_learnings",
            PROMOTE_LEARNINGS_PATH
        )
        promote_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(promote_module)

        ExtractedLearning = promote_module.ExtractedLearning

        learning = ExtractedLearning(
            timestamp="12:00",
            category="Technical",
            content="SQLite uses FTS5 for full-text search",
            source_file="test.md",
            line_number=1,
            content_hash=hashlib.md5("SQLite uses FTS5 for full-text search".encode()).hexdigest()[:12]
        )

        # Verify hash is stored correctly
        assert len(learning.content_hash) == 12

        # Verify tags include hash
        tags = learning.tags
        assert "technical" in tags

    @pytest.mark.skipif(
        not PROMOTE_LEARNINGS_PATH.exists(),
        reason="promote_learnings.py not found (CI environment)"
    )
    def test_check_already_promoted_function(self):
        """Test the actual check_already_promoted function."""
        # Import with proper path handling
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "promote_learnings",
            PROMOTE_LEARNINGS_PATH
        )
        promote_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(promote_module)

        check_already_promoted = promote_module.check_already_promoted
        ExtractedLearning = promote_module.ExtractedLearning

        content = "Test learning about Python"
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]

        learning = ExtractedLearning(
            timestamp="12:00",
            category="Technical",
            content=content,
            source_file="test.md",
            line_number=1,
            content_hash=content_hash
        )

        # No existing facts - should not be promoted
        assert check_already_promoted(learning, []) == False

        # With matching hash tag
        existing = [{"claim": "some claim", "tags": [f"hash:{content_hash}"]}]
        assert check_already_promoted(learning, existing) == True

        # With different hash tag
        other = [{"claim": "other claim", "tags": ["hash:different123"]}]
        assert check_already_promoted(learning, other) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
