"""
Resolution Stats Invariant Tests

These are guardrail assertions that prevent regression into fake confidence.
Run with: python test_resolution_invariants.py

Invariants:
1. If tailwind_color_classes == 0 -> health == "unknown" AND resolved_pct is None
2. If resolved_pct is None -> health == "unknown"
3. If health != "unknown" -> resolved_pct is not None
4. health_metric must be present and non-empty
"""

import sys
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "design"))
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from design_to_code_verifier import ResolutionStats, _format_resolution_stats


def test_zero_color_classes_means_unknown():
    """If we saw no color classes, health must be unknown and resolved_pct must be None."""
    stats = ResolutionStats(tailwind_color_classes=0)
    result = _format_resolution_stats(stats)

    assert result["health"] == "unknown", \
        f"Expected health='unknown' when color_classes=0, got '{result['health']}'"
    assert result["resolved_pct"] is None, \
        f"Expected resolved_pct=None when color_classes=0, got {result['resolved_pct']}"
    print("[PASS] Zero color classes -> unknown + None")


def test_null_pct_implies_unknown():
    """If resolved_pct is None, health must be unknown."""
    stats = ResolutionStats(tailwind_color_classes=0)
    result = _format_resolution_stats(stats)

    if result["resolved_pct"] is None:
        assert result["health"] == "unknown", \
            f"resolved_pct=None but health='{result['health']}' (should be 'unknown')"
    print("[PASS] None resolved_pct -> unknown health")


def test_known_health_has_pct():
    """If health is not unknown, resolved_pct must be a real number."""
    for color_classes in [1, 10, 100]:
        for resolved in [0, 5, 10, 50, 100]:
            if resolved > color_classes:
                continue
            stats = ResolutionStats(
                tailwind_color_classes=color_classes,
                tailwind_color_resolved=resolved
            )
            result = _format_resolution_stats(stats)

            if result["health"] != "unknown":
                assert result["resolved_pct"] is not None, \
                    f"health='{result['health']}' but resolved_pct is None"
                assert isinstance(result["resolved_pct"], (int, float)), \
                    f"resolved_pct should be numeric, got {type(result['resolved_pct'])}"
    print("[PASS] Known health -> numeric resolved_pct")


def test_health_metric_present():
    """health_metric must always be present and non-empty."""
    # Test with zero classes
    stats_zero = ResolutionStats(tailwind_color_classes=0)
    result_zero = _format_resolution_stats(stats_zero)

    assert "health_metric" in result_zero, "health_metric missing from result"
    assert result_zero["health_metric"], "health_metric is empty"

    # Test with some classes
    stats_some = ResolutionStats(tailwind_color_classes=10, tailwind_color_resolved=8)
    result_some = _format_resolution_stats(stats_some)

    assert "health_metric" in result_some, "health_metric missing from result"
    assert result_some["health_metric"], "health_metric is empty"

    print("[PASS] health_metric always present and non-empty")


def test_health_grades_correct():
    """Health grades must follow the defined thresholds."""
    test_cases = [
        # (color_classes, resolved, expected_health)
        (100, 100, "excellent"),  # 100%
        (100, 80, "excellent"),   # 80% (boundary)
        (100, 79, "good"),        # 79%
        (100, 50, "good"),        # 50% (boundary)
        (100, 49, "degraded"),    # 49%
        (100, 20, "degraded"),    # 20% (boundary)
        (100, 19, "blind"),       # 19%
        (100, 0, "blind"),        # 0%
    ]

    for color_classes, resolved, expected in test_cases:
        stats = ResolutionStats(
            tailwind_color_classes=color_classes,
            tailwind_color_resolved=resolved
        )
        result = _format_resolution_stats(stats)

        assert result["health"] == expected, \
            f"Expected health='{expected}' for {resolved}/{color_classes}, got '{result['health']}'"

    print("[PASS] Health grade thresholds correct")


def test_by_source_is_plain_dict():
    """by_source must be a plain dict for JSON serialization."""
    stats = ResolutionStats(tailwind_color_classes=10, tailwind_color_resolved=5)
    result = _format_resolution_stats(stats)

    assert isinstance(result["by_source"], dict), \
        f"by_source should be dict, got {type(result['by_source'])}"
    assert type(result["by_source"]) is dict, \
        f"by_source should be plain dict, not {type(result['by_source']).__name__}"

    print("[PASS] by_source is plain dict")


def test_note_appears_when_needed():
    """Note should appear for unknown and blind states."""
    # Unknown state
    stats_unknown = ResolutionStats(tailwind_color_classes=0)
    result_unknown = _format_resolution_stats(stats_unknown)
    assert "note" in result_unknown, "note missing for unknown state"

    # Blind state
    stats_blind = ResolutionStats(tailwind_color_classes=100, tailwind_color_resolved=5)
    result_blind = _format_resolution_stats(stats_blind)
    assert "note" in result_blind, "note missing for blind state"

    # Excellent state - no note needed
    stats_excellent = ResolutionStats(tailwind_color_classes=100, tailwind_color_resolved=90)
    result_excellent = _format_resolution_stats(stats_excellent)
    assert "note" not in result_excellent, "note should not appear for excellent state"

    print("[PASS] Note appears only when needed")


def run_all_tests():
    """Run all invariant tests."""
    print("=" * 50)
    print("Resolution Stats Invariant Tests")
    print("=" * 50)
    print()

    tests = [
        test_zero_color_classes_means_unknown,
        test_null_pct_implies_unknown,
        test_known_health_has_pct,
        test_health_metric_present,
        test_health_grades_correct,
        test_by_source_is_plain_dict,
        test_note_appears_when_needed,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: ERROR - {e}")
            failed += 1

    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
