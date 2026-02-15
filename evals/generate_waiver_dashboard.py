#!/usr/bin/env python3
"""Generate waiver dashboard from scoreboard data.

Reads metrics/waiver_scoreboard.json and outputs metrics/WAIVERS_DASHBOARD.md
with trend visualization, risk flags, and recent waiver details.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

# Config
WARN_THRESHOLD = 5
FAIL_THRESHOLD = 10
WINDOW_DAYS = 7
TREND_DAYS = 14
BURST_THRESHOLD = 3  # Same rule X times in 24h = risk flag
BURST_WINDOW_HOURS = 24

# Paths
SCRIPT_DIR = Path(__file__).parent
METRICS_DIR = SCRIPT_DIR.parent / 'metrics'
SCOREBOARD_PATH = METRICS_DIR / 'waiver_scoreboard.json'
DASHBOARD_PATH = METRICS_DIR / 'WAIVERS_DASHBOARD.md'


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


def get_status_badge(count: int) -> str:
    """Return status based on waiver count."""
    if count > FAIL_THRESHOLD:
        return "FAIL"
    elif count > WARN_THRESHOLD:
        return "WARN"
    else:
        return "PASS"


def ascii_bar(value: int, max_value: int, width: int = 20) -> str:
    """Generate ASCII bar chart."""
    if max_value == 0:
        return ""
    filled = int((value / max_value) * width)
    return "#" * filled + "-" * (width - filled)


def detect_rule_bursts(recent: list, now: datetime) -> list:
    """Detect same rule repeated 3+ times within 24h."""
    bursts = []
    cutoff = now - timedelta(hours=BURST_WINDOW_HOURS)

    # Group by rule within burst window
    rule_occurrences = defaultdict(list)
    for item in recent:
        ts = parse_ts(item.get("ts"))
        if ts and ts >= cutoff:
            rule_id = item.get("rule", "unknown")
            rule_occurrences[rule_id].append(item)

    # Find bursts
    for rule_id, items in rule_occurrences.items():
        if len(items) >= BURST_THRESHOLD:
            bursts.append({
                "rule": rule_id,
                "count": len(items),
                "window_hours": BURST_WINDOW_HOURS,
                "reasons": [i.get("reason", "?")[:40] for i in items[:3]],
                "commands": [i.get("command_preview", "?")[:40] for i in items[:3]]
            })

    return bursts


def generate_dashboard(data: dict, now: datetime) -> str:
    """Generate markdown dashboard content."""
    lines = []

    # Header
    lines.append("# Waiver Dashboard")
    lines.append("")
    lines.append(f"*Generated: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC*")
    lines.append("")

    # --- Last 7 Days Summary ---
    recent = data.get("recent", []) or []
    cutoff_7d = now - timedelta(days=WINDOW_DAYS)
    count_7d = sum(1 for item in recent if parse_ts(item.get("ts")) and parse_ts(item.get("ts")) >= cutoff_7d)
    status = get_status_badge(count_7d)

    lines.append("## Last 7 Days")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Waivers | **{count_7d}** |")
    lines.append(f"| Status | **{status}** |")
    lines.append(f"| Threshold | warn > {WARN_THRESHOLD}, fail > {FAIL_THRESHOLD} |")
    lines.append("")

    # --- Top Rules ---
    by_rule = data.get("by_rule", {})
    by_rule_7d = defaultdict(int)
    for item in recent:
        ts = parse_ts(item.get("ts"))
        if ts and ts >= cutoff_7d:
            rule = item.get("rule", "unknown")
            by_rule_7d[rule] += 1

    lines.append("## Top Rules")
    lines.append("")
    if by_rule or by_rule_7d:
        lines.append("| Rule | 7d | All-time |")
        lines.append("|------|----:|--------:|")
        all_rules = set(by_rule.keys()) | set(by_rule_7d.keys())
        sorted_rules = sorted(all_rules, key=lambda r: by_rule_7d.get(r, 0), reverse=True)
        for rule in sorted_rules[:10]:
            lines.append(f"| `{rule}` | {by_rule_7d.get(rule, 0)} | {by_rule.get(rule, 0)} |")
    else:
        lines.append("*No waivers recorded*")
    lines.append("")

    # --- Daily Trend (last 14 days) ---
    lines.append("## Daily Trend (Last 14 Days)")
    lines.append("")
    by_day = data.get("by_day", {})

    # Build last 14 days
    daily_counts = []
    for i in range(TREND_DAYS - 1, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        count = by_day.get(day, 0)
        daily_counts.append((day, count))

    max_count = max((c for _, c in daily_counts), default=1) or 1

    lines.append("```")
    for day, count in daily_counts:
        bar = ascii_bar(count, max_count, 20)
        short_day = day[5:]  # MM-DD
        lines.append(f"{short_day} | {bar} {count}")
    lines.append("```")
    lines.append("")

    # --- Recent Waivers ---
    lines.append("## Recent Waivers (Last 10)")
    lines.append("")
    if recent:
        lines.append("| Timestamp | Rule | Reason | Command |")
        lines.append("|-----------|------|--------|---------|")
        for item in recent[:10]:
            ts = item.get("ts", "?")[:19].replace("T", " ")
            rule = item.get("rule", "?")
            reason = item.get("reason", "?")[:35]
            if len(item.get("reason", "")) > 35:
                reason += "..."
            cmd = item.get("command_preview", "?")[:30]
            if len(item.get("command_preview", "")) > 30:
                cmd += "..."
            lines.append(f"| {ts} | `{rule}` | {reason} | `{cmd}` |")
    else:
        lines.append("*No recent waivers*")
    lines.append("")

    # --- Risk Flags ---
    bursts = detect_rule_bursts(recent, now)
    lines.append("## Risk Flags")
    lines.append("")

    if bursts:
        for burst in bursts:
            lines.append(f"### Rule Burst: `{burst['rule']}` x{burst['count']} in {burst['window_hours']}h")
            lines.append("")
            lines.append("**Sample reasons:**")
            for reason in burst["reasons"]:
                lines.append(f"- {reason}...")
            lines.append("")
            lines.append("**Sample commands:**")
            for cmd in burst["commands"]:
                lines.append(f"- `{cmd}...`")
            lines.append("")
            lines.append("**Recommended action:** Investigate if rule is too strict or workflow needs safe alternative.")
            lines.append("")
    else:
        lines.append("*No risk flags detected*")
    lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append("")
    lines.append("*Dashboard generated by `evals/generate_waiver_dashboard.py`*")

    return "\n".join(lines)


def main():
    """Generate waiver dashboard."""
    print("=" * 50)
    print("WAIVER DASHBOARD GENERATOR")
    print("=" * 50)

    # Ensure metrics directory exists
    METRICS_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)

    if not SCOREBOARD_PATH.exists():
        print(f"\n[dashboard] {SCOREBOARD_PATH} not found")
        print("[dashboard] Creating empty dashboard")
        data = {"recent": [], "by_rule": {}, "by_day": {}, "total_waivers": 0}
    else:
        with open(SCOREBOARD_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"\n[dashboard] Loaded {SCOREBOARD_PATH}")
        print(f"[dashboard] Total waivers: {data.get('total_waivers', 0)}")

    # Generate dashboard
    content = generate_dashboard(data, now)

    # Write dashboard
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[dashboard] Written to {DASHBOARD_PATH}")
    print(f"[dashboard] Size: {len(content)} bytes")

    # Print summary
    recent = data.get("recent", []) or []
    cutoff_7d = now - timedelta(days=WINDOW_DAYS)
    count_7d = sum(1 for item in recent if parse_ts(item.get("ts")) and parse_ts(item.get("ts")) >= cutoff_7d)
    status = get_status_badge(count_7d)

    print(f"\n[dashboard] Last 7 days: {count_7d} waivers ({status})")

    bursts = detect_rule_bursts(recent, now)
    if bursts:
        print(f"[dashboard] Risk flags: {len(bursts)} rule burst(s) detected")
    else:
        print("[dashboard] Risk flags: None")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
