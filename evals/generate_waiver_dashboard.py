#!/usr/bin/env python3
"""Generate waiver dashboard from scoreboard data.

Reads metrics/waiver_scoreboard.json and outputs metrics/WAIVERS_DASHBOARD.md
with trend visualization, clustering analysis, risk flags, and recent waiver details.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

# Config - Count-based thresholds (legacy, kept for reference)
WARN_THRESHOLD = 5
FAIL_THRESHOLD = 10

# Config - Point-based thresholds (primary)
WARN_POINTS = 10  # ~4 high-risk waivers/week
FAIL_POINTS = 20  # ~7 high-risk waivers/week

WINDOW_DAYS = 7
TREND_DAYS = 14
BURST_THRESHOLD = 3  # Same rule X times in 24h = risk flag
BURST_WINDOW_HOURS = 24

# Clustering config
MIN_CLUSTER_SIZE = 3
REASON_SIMILARITY_THRESHOLD = 0.55
CLUSTER_WARNING_THRESHOLD = 5  # Emit CI warning if cluster count >= this
CLUSTER_POINTS_WARNING = 10  # Emit CI warning if cluster points >= this

# Default weights (used if not in scoreboard)
DEFAULT_WEIGHTS = {
    "destructive_bash_commands": 3,
    "path_sandbox": 3,
    "force_push": 3,
    "amend_pushed_commit": 2,
    "read_before_edit": 2,
    "_default": 1
}

# Stopwords for reason tokenization
STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is", "it",
    "this", "that", "i", "we", "you", "my", "our", "be", "as", "at", "by", "from",
    "so", "but", "if", "then", "than", "can", "will", "do", "did", "done", "was",
    "were", "been", "being", "have", "has", "had", "not", "no", "yes", "just",
    "need", "needs", "needed", "want", "wants", "wanted", "because", "since"
}

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


# Global weights dict - set by load_weights() or defaults
_weights = {}


def load_weights(data: dict) -> dict:
    """Load weights from scoreboard data or use defaults."""
    global _weights
    _weights = data.get("weights") or DEFAULT_WEIGHTS.copy()
    return _weights


def weight_for(rule_id: str) -> int:
    """Get point weight for a rule."""
    if not _weights:
        return DEFAULT_WEIGHTS.get(rule_id, DEFAULT_WEIGHTS.get("_default", 1))
    return int(_weights.get(rule_id, _weights.get("_default", 1)))


# =============================================================================
# CLUSTERING FUNCTIONS
# =============================================================================

def tokenize_reason(text: str) -> set:
    """Normalize and tokenize reason text for similarity comparison."""
    if not text:
        return set()
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    toks = [t for t in text.split() if len(t) >= 3 and t not in STOPWORDS]
    return set(toks[:60])  # Cap runaway text


def command_fingerprint(cmd: str, n_tokens: int = 6) -> str:
    """Get first N tokens of command as fingerprint."""
    if not cmd:
        return ""
    cmd = cmd.strip()
    cmd = re.sub(r"\s+", " ", cmd)
    parts = cmd.split(" ")
    return " ".join(parts[:n_tokens]).lower()


def jaccard(a: set, b: set) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def top_terms(group: list) -> list:
    """Extract top reason terms from a group of waivers."""
    freq = defaultdict(int)
    for g in group:
        for t in g.get("reason_tokens", set()):
            freq[t] += 1
    top = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    return [t for t, _ in top]


def cluster_waivers(recent: list, window_days: int = 7) -> list:
    """Cluster waivers by rule, command, and reason similarity.

    Returns list of clusters with:
    - kind: rule_burst | command_repeat | reason_similarity
    - key: identifier for the cluster
    - count: number of waivers
    - start/end: time window
    - sample_cmd: example command
    - top_reason_terms: common words in reasons
    - suggestion: recommended action
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    # Build enriched items list with points
    items = []
    for w in recent or []:
        ts = parse_ts(w.get("ts"))
        if ts and ts >= cutoff:
            rule = w.get("rule") or "unknown_rule"
            reason = w.get("reason") or ""
            cmd = w.get("command_preview") or ""
            items.append({
                "ts": ts,
                "rule": rule,
                "reason": reason,
                "reason_tokens": tokenize_reason(reason),
                "cmd": cmd,
                "cmd_fp": command_fingerprint(cmd),
                "points": weight_for(rule),
            })

    if not items:
        return []

    # Group by rule and command fingerprint
    by_rule = defaultdict(list)
    by_cmd = defaultdict(list)
    for it in items:
        by_rule[it["rule"]].append(it)
        if it["cmd_fp"]:
            by_cmd[it["cmd_fp"]].append(it)

    clusters = []
    seen_items = set()  # Track items already in clusters to avoid duplicates

    def add_cluster(kind: str, key: str, group: list, suggestion: str):
        if len(group) < MIN_CLUSTER_SIZE:
            return
        group = sorted(group, key=lambda x: x["ts"])
        total_points = sum(g.get("points", 1) for g in group)
        avg_points = total_points / len(group) if group else 0
        # Risk label based on average points per waiver
        if avg_points >= 2.5:
            risk_label = "HIGH"
        elif avg_points >= 1.5:
            risk_label = "MEDIUM"
        else:
            risk_label = "LOW"
        clusters.append({
            "kind": kind,
            "key": key,
            "count": len(group),
            "points": total_points,
            "avg_points": avg_points,
            "risk_label": risk_label,
            "start": group[0]["ts"],
            "end": group[-1]["ts"],
            "sample_cmd": next((g["cmd"] for g in group if g["cmd"]), ""),
            "top_reason_terms": top_terms(group),
            "suggestion": suggestion,
            "items": group[-5:],  # Keep last 5 for display
        })

    # 1) Rule burst clusters
    for rule, group in by_rule.items():
        if len(group) >= MIN_CLUSTER_SIZE:
            add_cluster(
                "rule_burst",
                rule,
                group,
                "Rule may be too strict, or workflow needs a safe alternative path"
            )

    # 2) Command repeat clusters
    for cmd_fp, group in by_cmd.items():
        if len(group) >= MIN_CLUSTER_SIZE:
            # Check if this overlaps significantly with a rule cluster
            rules_in_group = set(g["rule"] for g in group)
            if len(rules_in_group) > 1:
                # Multi-rule command repeat is interesting
                add_cluster(
                    "command_repeat",
                    cmd_fp,
                    group,
                    "Same command hitting multiple rules - consider a helper or whitelist"
                )

    # 3) Reason similarity clusters (greedy matching)
    used = set()
    for i in range(len(items)):
        if i in used:
            continue
        base = items[i]
        if not base["reason_tokens"]:
            continue
        group = [base]

        for j in range(i + 1, len(items)):
            if j in used:
                continue
            cand = items[j]
            if not cand["reason_tokens"]:
                continue
            # Only compare within same rule family to avoid nonsense matches
            if cand["rule"] != base["rule"]:
                continue
            if jaccard(base["reason_tokens"], cand["reason_tokens"]) >= REASON_SIMILARITY_THRESHOLD:
                group.append(cand)

        if len(group) >= MIN_CLUSTER_SIZE:
            for k, item in enumerate(items):
                if item in group:
                    used.add(k)
            add_cluster(
                "reason_similarity",
                f"{base['rule']}|similar_reasons",
                group,
                "Repeated justification pattern - may indicate recurring workflow gap"
            )

    # Sort clusters by count desc, then recency
    clusters.sort(key=lambda c: (-c["count"], -(c["end"].timestamp())))

    # Deduplicate overlapping clusters (keep highest count)
    # This is a simple approach - just return top unique ones
    return clusters[:10]


def render_clusters(clusters: list) -> list:
    """Render clusters section as markdown lines."""
    lines = []
    lines.append("## Clusters (Last 7 Days)")
    lines.append("")

    if not clusters:
        lines.append("*No significant clusters detected*")
        lines.append("")
        return lines

    for i, cluster in enumerate(clusters[:5], 1):
        kind = cluster["kind"]
        key = cluster["key"]
        count = cluster["count"]
        points = cluster.get("points", count)
        risk_label = cluster.get("risk_label", "UNKNOWN")
        start = cluster["start"].strftime("%Y-%m-%d")
        end = cluster["end"].strftime("%Y-%m-%d")

        # Kind label
        kind_label = {
            "rule_burst": "Rule Burst",
            "command_repeat": "Command Repeat",
            "reason_similarity": "Similar Reasons"
        }.get(kind, kind)

        lines.append(f"### {i}) {kind_label} -- `{key}` ({count} waivers, {points} pts, {risk_label})")
        lines.append("")
        lines.append(f"- **Window:** {start} -> {end}")
        lines.append(f"- **Risk:** {risk_label} ({points} points from {count} waivers)")

        if cluster["sample_cmd"]:
            cmd_preview = cluster["sample_cmd"][:60]
            if len(cluster["sample_cmd"]) > 60:
                cmd_preview += "..."
            lines.append(f"- **Sample command:** `{cmd_preview}`")

        if cluster["top_reason_terms"]:
            terms = ", ".join(cluster["top_reason_terms"][:6])
            lines.append(f"- **Common reason terms:** {terms}")

        lines.append(f"- **Suggestion:** {cluster['suggestion']}")
        lines.append("")

    return lines


def get_cluster_warnings(clusters: list) -> list:
    """Get CI warning messages for large or high-risk clusters."""
    warnings = []
    for cluster in clusters:
        count = cluster["count"]
        points = cluster.get("points", count)
        risk_label = cluster.get("risk_label", "")
        # Warn if count >= 5 OR points >= 10
        if count >= CLUSTER_WARNING_THRESHOLD or points >= CLUSTER_POINTS_WARNING:
            kind = cluster["kind"]
            key = cluster["key"]
            warnings.append(
                f"Cluster detected: {kind} '{key}' ({count} waivers, {points} pts, {risk_label})"
            )
    return warnings


def get_status_badge_points(points: int) -> str:
    """Return status based on waiver points (primary)."""
    if points > FAIL_POINTS:
        return "FAIL"
    elif points > WARN_POINTS:
        return "WARN"
    else:
        return "PASS"


def get_status_badge(count: int) -> str:
    """Return status based on waiver count (legacy)."""
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
    # Load weights from data (or use defaults)
    load_weights(data)

    lines = []

    # Header
    lines.append("# Waiver Dashboard")
    lines.append("")
    lines.append(f"*Generated: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC*")
    lines.append("")

    # --- Last 7 Days Summary ---
    recent = data.get("recent", []) or []
    cutoff_7d = now - timedelta(days=WINDOW_DAYS)

    # Calculate both count and points
    count_7d = 0
    points_7d = 0
    for item in recent:
        ts = parse_ts(item.get("ts"))
        if ts and ts >= cutoff_7d:
            count_7d += 1
            points_7d += weight_for(item.get("rule", ""))

    # Status based on points (primary metric)
    status = get_status_badge_points(points_7d)

    lines.append("## Last 7 Days")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Waivers | **{count_7d}** |")
    lines.append(f"| Points | **{points_7d}** |")
    lines.append(f"| Status | **{status}** |")
    lines.append(f"| Threshold | warn > {WARN_POINTS} pts, fail > {FAIL_POINTS} pts |")
    lines.append("")

    # --- Top Rules ---
    by_rule = data.get("by_rule", {})
    by_rule_7d = defaultdict(int)
    by_rule_7d_points = defaultdict(int)
    for item in recent:
        ts = parse_ts(item.get("ts"))
        if ts and ts >= cutoff_7d:
            rule = item.get("rule", "unknown")
            by_rule_7d[rule] += 1
            by_rule_7d_points[rule] += weight_for(rule)

    lines.append("## Top Rules")
    lines.append("")
    if by_rule or by_rule_7d:
        lines.append("| Rule | Weight | 7d Count | 7d Pts | All-time |")
        lines.append("|------|-------:|--------:|-------:|--------:|")
        all_rules = set(by_rule.keys()) | set(by_rule_7d.keys())
        # Sort by 7d points desc, then by count
        sorted_rules = sorted(all_rules, key=lambda r: (by_rule_7d_points.get(r, 0), by_rule_7d.get(r, 0)), reverse=True)
        for rule in sorted_rules[:10]:
            w = weight_for(rule)
            lines.append(f"| `{rule}` | {w} | {by_rule_7d.get(rule, 0)} | {by_rule_7d_points.get(rule, 0)} | {by_rule.get(rule, 0)} |")
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

    # --- Clusters ---
    clusters = cluster_waivers(recent, WINDOW_DAYS)
    lines.extend(render_clusters(clusters))

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

    # Print summary with points
    recent = data.get("recent", []) or []
    cutoff_7d = now - timedelta(days=WINDOW_DAYS)

    count_7d = 0
    points_7d = 0
    for item in recent:
        ts = parse_ts(item.get("ts"))
        if ts and ts >= cutoff_7d:
            count_7d += 1
            points_7d += weight_for(item.get("rule", ""))

    status = get_status_badge_points(points_7d)

    print(f"\n[dashboard] Last 7 days: {count_7d} waivers, {points_7d} points ({status})")
    print(f"[dashboard] Thresholds: warn > {WARN_POINTS} pts, fail > {FAIL_POINTS} pts")

    # Clustering analysis
    clusters = cluster_waivers(recent, WINDOW_DAYS)
    if clusters:
        print(f"[dashboard] Clusters detected: {len(clusters)}")
        for c in clusters[:3]:
            pts = c.get('points', c['count'])
            risk = c.get('risk_label', '')
            print(f"  - {c['kind']}: {c['key']} ({c['count']} waivers, {pts} pts, {risk})")
    else:
        print("[dashboard] Clusters: None")

    # Emit CI warnings for large clusters (GitHub Actions annotation format)
    warnings = get_cluster_warnings(clusters)
    for warning in warnings:
        print(f"::warning::{warning}")

    # Risk flags (24h bursts)
    bursts = detect_rule_bursts(recent, now)
    if bursts:
        print(f"[dashboard] Risk flags: {len(bursts)} rule burst(s) in 24h")
    else:
        print("[dashboard] Risk flags: None")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
