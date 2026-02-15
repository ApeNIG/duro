#!/usr/bin/env python3
"""Test clustering functions with synthetic data."""

import sys
from datetime import datetime, timedelta, timezone
from generate_waiver_dashboard import (
    tokenize_reason, command_fingerprint, jaccard, cluster_waivers,
    render_clusters, get_cluster_warnings
)


def test_tokenize_reason():
    """Test reason tokenization."""
    print("\n[Test] tokenize_reason")

    # Basic tokenization
    tokens = tokenize_reason("Force pushing rebased feature branch for testing")
    print(f"  Input: 'Force pushing rebased feature branch for testing'")
    print(f"  Tokens: {tokens}")
    assert "force" in tokens
    assert "pushing" in tokens
    assert "rebased" in tokens
    assert "for" not in tokens  # stopword
    assert "the" not in tokens  # stopword
    print("  PASS")


def test_command_fingerprint():
    """Test command fingerprinting."""
    print("\n[Test] command_fingerprint")

    fp = command_fingerprint("git push --force origin main", n_tokens=4)
    print(f"  Input: 'git push --force origin main'")
    print(f"  Fingerprint (4 tokens): '{fp}'")
    assert fp == "git push --force origin"
    print("  PASS")


def test_jaccard():
    """Test Jaccard similarity."""
    print("\n[Test] jaccard")

    a = {"git", "push", "force", "origin"}
    b = {"git", "push", "force", "main"}
    sim = jaccard(a, b)
    print(f"  Set A: {a}")
    print(f"  Set B: {b}")
    print(f"  Jaccard: {sim:.2f}")
    assert 0.5 < sim < 0.8  # 3 overlap / 5 union = 0.6
    print("  PASS")


def test_cluster_waivers():
    """Test waiver clustering with synthetic data."""
    print("\n[Test] cluster_waivers")

    now = datetime.now(timezone.utc)

    # Create synthetic waivers - 5 similar ones for destructive_bash_commands
    recent = [
        {
            "ts": (now - timedelta(hours=i)).isoformat(),
            "rule": "destructive_bash_commands",
            "reason": f"Force pushing rebased branch for testing variant {i}",
            "command_preview": "git push --force origin main"
        }
        for i in range(5)
    ]

    # Add a few unrelated waivers
    recent.append({
        "ts": (now - timedelta(hours=10)).isoformat(),
        "rule": "path_sandbox",
        "reason": "Need to write to system config for debugging",
        "command_preview": "echo test > /etc/something"
    })

    print(f"  Input: {len(recent)} waivers")
    print(f"    - 5x destructive_bash_commands (similar)")
    print(f"    - 1x path_sandbox (different)")

    clusters = cluster_waivers(recent, window_days=7)
    print(f"  Clusters found: {len(clusters)}")

    for c in clusters:
        print(f"    - {c['kind']}: {c['key']} ({c['count']} waivers)")
        print(f"      Top terms: {c['top_reason_terms']}")

    # Should find at least 1 cluster (rule_burst for destructive_bash_commands)
    assert len(clusters) >= 1
    assert any(c["key"] == "destructive_bash_commands" for c in clusters)
    print("  PASS")


def test_cluster_warnings():
    """Test CI warning generation."""
    print("\n[Test] get_cluster_warnings")

    clusters = [
        {"kind": "rule_burst", "key": "destructive_bash_commands", "count": 6},
        {"kind": "command_repeat", "key": "git push --force", "count": 3},  # Below threshold
    ]

    warnings = get_cluster_warnings(clusters)
    print(f"  Input: 2 clusters (count 6, count 3)")
    print(f"  Warnings: {len(warnings)}")
    for w in warnings:
        print(f"    - {w}")

    assert len(warnings) == 1  # Only count >= 5 triggers warning
    assert "destructive_bash_commands" in warnings[0]
    print("  PASS")


def test_render_clusters():
    """Test cluster rendering."""
    print("\n[Test] render_clusters")

    now = datetime.now(timezone.utc)
    clusters = [
        {
            "kind": "rule_burst",
            "key": "destructive_bash_commands",
            "count": 5,
            "start": now - timedelta(days=2),
            "end": now,
            "sample_cmd": "git push --force origin main",
            "top_reason_terms": ["force", "pushing", "rebased", "testing"],
            "suggestion": "Rule may be too strict",
            "items": []
        }
    ]

    lines = render_clusters(clusters)
    content = "\n".join(lines)
    print(f"  Output lines: {len(lines)}")
    print("  Content preview:")
    for line in lines[:10]:
        print(f"    {line}")

    assert "## Clusters (Last 7 Days)" in content
    assert "Rule Burst" in content
    assert "destructive_bash_commands" in content
    print("  PASS")


def main():
    print("=" * 60)
    print("CLUSTERING TESTS")
    print("=" * 60)

    test_tokenize_reason()
    test_command_fingerprint()
    test_jaccard()
    test_cluster_waivers()
    test_cluster_warnings()
    test_render_clusters()

    print("\n" + "=" * 60)
    print("ALL CLUSTERING TESTS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
