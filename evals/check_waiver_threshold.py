#!/usr/bin/env python3
"""Check waiver threshold locally.

Same logic as CI workflow step.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Config
WARN = 5
FAIL = 10
WINDOW_DAYS = 7

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
    print("WAIVER THRESHOLD CHECK")
    print("=" * 50)

    if not SCOREBOARD.exists():
        print(f"\n[waivers] {SCOREBOARD} not found")
        print("[waivers] Assuming 0 waivers (fresh install)")
        print("\nStatus: PASS (no scoreboard)")
        return 0

    with open(SCOREBOARD, "r", encoding="utf-8") as f:
        data = json.load(f)

    recent = data.get("recent", []) or []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)

    # Count waivers in window
    count = 0
    in_window = []
    for item in recent:
        ts = parse_ts(item.get("ts"))
        if ts and ts >= cutoff:
            count += 1
            in_window.append(item)

    print(f"\nScoreboard: {SCOREBOARD}")
    print(f"Window: last {WINDOW_DAYS} days")
    print(f"Total waivers (all time): {data.get('total_waivers', 0)}")
    print(f"Waivers in window: {count}")
    print(f"Thresholds: warn > {WARN}, fail > {FAIL}")

    if in_window:
        print(f"\nRecent waivers ({len(in_window)}):")
        for item in in_window[:10]:  # Show at most 10
            rule = item.get("rule", "?")
            reason = item.get("reason", "?")[:40]
            ts = item.get("ts", "?")[:10]
            print(f"  - [{ts}] {rule}: {reason}...")

    print()
    if count > FAIL:
        print(f"Status: FAIL (>{FAIL} waivers)")
        return 1
    elif count > WARN:
        print(f"Status: WARN (>{WARN} waivers)")
        return 0  # Don't fail locally on warn
    else:
        print("Status: PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
