#!/usr/bin/env python3
"""Check waiver threshold locally (points-based).

Same logic as CI workflow step.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Config - Points-based thresholds
WARN_POINTS = 10  # ~4 high-risk waivers/week
FAIL_POINTS = 20  # ~7 high-risk waivers/week
WINDOW_DAYS = 7

# Default weights if not in scoreboard
DEFAULT_WEIGHTS = {
    "destructive_bash_commands": 3,
    "path_sandbox": 3,
    "force_push": 3,
    "amend_pushed_commit": 2,
    "read_before_edit": 2,
    "_default": 1
}

# Path
SCOREBOARD = Path.home() / '.agent' / 'metrics' / 'waiver_scoreboard.json'


def parse_ts(x: str):
    """Parse ISO timestamp to UTC datetime."""
    if not x:
        return None
    x = x.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(x)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def main():
    print("=" * 50)
    print("WAIVER THRESHOLD CHECK (Points-Based)")
    print("=" * 50)

    if not SCOREBOARD.exists():
        print(f"\n[waivers] {SCOREBOARD} not found")
        print("[waivers] Assuming 0 waivers (fresh install)")
        print("\nStatus: PASS (no scoreboard)")
        return 0

    with open(SCOREBOARD, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Load weights
    weights = data.get("weights") or DEFAULT_WEIGHTS

    def weight_for(rule_id: str) -> int:
        return int(weights.get(rule_id, weights.get("_default", 1)))

    recent = data.get("recent", []) or []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)

    # Count waivers and points in window
    count = 0
    points = 0
    in_window = []
    for item in recent:
        ts = parse_ts(item.get("ts"))
        if ts and ts >= cutoff:
            count += 1
            rule = item.get("rule", "")
            item_points = weight_for(rule)
            points += item_points
            in_window.append({**item, "points": item_points})

    print(f"\nScoreboard: {SCOREBOARD}")
    print(f"Window: last {WINDOW_DAYS} days")
    print(f"Total waivers (all time): {data.get('total_waivers', 0)}")
    print(f"Waivers in window: {count}")
    print(f"Points in window: {points}")
    print(f"Thresholds: warn > {WARN_POINTS} pts, fail > {FAIL_POINTS} pts")

    if in_window:
        print(f"\nRecent waivers ({len(in_window)}):")
        for item in in_window[:10]:  # Show at most 10
            rule = item.get("rule", "?")
            pts = item.get("points", 1)
            reason = item.get("reason", "?")[:35]
            ts = item.get("ts", "?")[:10]
            print(f"  - [{ts}] {rule} ({pts}pt): {reason}...")

    print()
    if points > FAIL_POINTS:
        print(f"Status: FAIL (>{FAIL_POINTS} points)")
        return 1
    elif points > WARN_POINTS:
        print(f"Status: WARN (>{WARN_POINTS} points)")
        return 0  # Don't fail locally on warn
    else:
        print("Status: PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
