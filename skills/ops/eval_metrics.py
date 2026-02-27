"""
Skill: eval_metrics
Description: Compute eval metrics for decisions, episodes, and evaluations.
             Tracks reopen rate, revert rate, validation status, and confidence distribution.

This skill computes governance metrics from Duro's artifact database:
1. Decision metrics (total, by status, review rate, reopen rate)
2. Episode metrics (total, by result, duration distribution)
3. Evaluation metrics (grade distribution, rubric scores)
4. Key rates for governance health

Usage:
    python eval_metrics.py [--store] [--json]

    --store: Store the computed metrics as a fact in Duro
    --json: Output raw JSON instead of formatted report
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

# Add duro-mcp to path for imports
DURO_MCP_PATH = Path.home() / "duro-mcp"
sys.path.insert(0, str(DURO_MCP_PATH))

# Memory paths
MEMORY_DIR = Path.home() / ".agent" / "memory"
DB_PATH = MEMORY_DIR / "index.db"

# Smoke test tags to exclude
SMOKE_TEST_TAGS = {"smoke-test", "decision-auto-outcome", "decision-outcome", "auto-outcome", "generated", "test"}


def compute_metrics():
    """Compute all eval metrics from the artifact database."""
    try:
        from artifacts import ArtifactStore
        store = ArtifactStore(MEMORY_DIR, DB_PATH)
    except ImportError as e:
        return {"error": f"Failed to import ArtifactStore: {e}"}

    metrics = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "decisions": compute_decision_metrics(store),
        "episodes": compute_episode_metrics(store),
        "evaluations": compute_evaluation_metrics(store),
        "rates": {},
        "health": []
    }

    # Compute key rates
    d = metrics["decisions"]
    if d["total"] > 0:
        metrics["rates"]["decision_review_rate"] = round(d["validation_events"] / d["total"], 3)
        metrics["rates"]["unverified_rate"] = round(d["by_status"].get("unverified", 0) / d["total"], 3)

    if d["validation_events"] > 0:
        metrics["rates"]["reopen_rate"] = round(d["by_status"].get("reversed", 0) / d["validation_events"], 3)
    else:
        metrics["rates"]["reopen_rate"] = 0.0

    # Health indicators
    if metrics["rates"].get("unverified_rate", 0) > 0.8:
        metrics["health"].append("HIGH unverified rate - close decision feedback loops")
    if d.get("unreviewed_count", 0) > 5:
        metrics["health"].append(f"{d['unreviewed_count']} decisions need review")
    if metrics["rates"].get("reopen_rate", 0) > 0.3:
        metrics["health"].append("HIGH reopen rate - decisions are being reversed frequently")

    return metrics


def compute_decision_metrics(store):
    """Compute decision-specific metrics."""
    decisions = store.query(artifact_type="decision", limit=1000)
    validations = store.query(artifact_type="decision_validation", limit=1000)

    total = len(decisions)
    smoke_test_count = 0
    by_status = defaultdict(int)
    by_tag = defaultdict(int)
    unreviewed_count = 0
    real_decisions = []

    for d in decisions:
        tags = set(d.get("tags", []))

        # Check if smoke test
        if tags & SMOKE_TEST_TAGS:
            smoke_test_count += 1
            continue

        real_decisions.append(d)

        # Get full artifact for status
        artifact = store.get_artifact(d["id"])
        if artifact:
            data = artifact.get("data") or {}
            outcome = data.get("outcome") or {}
            status = outcome.get("status", "unverified") if isinstance(outcome, dict) else "unverified"
            by_status[status] += 1

            if status == "unverified":
                unreviewed_count += 1

        for tag in tags:
            by_tag[tag] += 1

    return {
        "total": total,
        "smoke_test_count": smoke_test_count,
        "real_decisions": len(real_decisions),
        "by_status": dict(by_status),
        "validation_events": len(validations),
        "unreviewed_count": unreviewed_count,
        "top_tags": dict(sorted(by_tag.items(), key=lambda x: -x[1])[:10])
    }


def compute_episode_metrics(store):
    """Compute episode-specific metrics."""
    episodes = store.query(artifact_type="episode", limit=1000)

    total = len(episodes)
    smoke_test_count = 0
    by_result = defaultdict(int)
    durations = []
    real_episodes = []

    for e in episodes:
        goal = e.get("goal", "") or ""

        # Check if smoke test by goal
        if "smoke test" in goal.lower() or "smoke-test" in goal.lower():
            smoke_test_count += 1
            continue

        real_episodes.append(e)

        # Get full artifact
        artifact = store.get_artifact(e["id"])
        if artifact:
            data = artifact.get("data") or {}
            result = data.get("result", "unknown") if isinstance(data, dict) else "unknown"
            by_result[result] += 1

            duration = data.get("duration_mins", 0) if isinstance(data, dict) else 0
            if duration and duration > 0:
                durations.append(duration)

    avg_duration = sum(durations) / len(durations) if durations else 0

    return {
        "total": total,
        "smoke_test_count": smoke_test_count,
        "real_episodes": len(real_episodes),
        "by_result": dict(by_result),
        "avg_duration_mins": round(avg_duration, 2),
        "duration_count": len(durations)
    }


def compute_evaluation_metrics(store):
    """Compute evaluation-specific metrics."""
    evaluations = store.query(artifact_type="evaluation", limit=1000)

    total = len(evaluations)
    by_grade = defaultdict(int)
    outcome_scores = []

    for e in evaluations:
        artifact = store.get_artifact(e["id"])
        if artifact:
            data = artifact.get("data") or {}
            grade = data.get("grade", "unknown") if isinstance(data, dict) else "unknown"
            by_grade[grade] += 1

            rubric = data.get("rubric") or {} if isinstance(data, dict) else {}
            outcome = rubric.get("outcome_quality") or {} if isinstance(rubric, dict) else {}
            if isinstance(outcome, dict) and "score" in outcome:
                outcome_scores.append(outcome["score"])

    avg_outcome = sum(outcome_scores) / len(outcome_scores) if outcome_scores else 0

    return {
        "total": total,
        "by_grade": dict(by_grade),
        "avg_outcome_score": round(avg_outcome, 2),
        "scored_count": len(outcome_scores)
    }


def format_report(metrics):
    """Format metrics as a human-readable report."""
    lines = []
    lines.append("=" * 50)
    lines.append("DURO EVAL METRICS REPORT")
    lines.append("=" * 50)
    lines.append(f"Computed: {metrics['computed_at']}")
    lines.append("")

    # Decisions
    d = metrics["decisions"]
    lines.append("## DECISIONS")
    lines.append(f"  Total: {d['total']} ({d['real_decisions']} real, {d['smoke_test_count']} smoke-test)")
    lines.append(f"  By status:")
    for status, count in d.get("by_status", {}).items():
        lines.append(f"    - {status}: {count}")
    lines.append(f"  Validation events: {d['validation_events']}")
    lines.append(f"  Needing review: {d['unreviewed_count']}")
    lines.append("")

    # Episodes
    e = metrics["episodes"]
    lines.append("## EPISODES")
    lines.append(f"  Total: {e['total']} ({e['real_episodes']} real, {e['smoke_test_count']} smoke-test)")
    lines.append(f"  By result:")
    for result, count in e.get("by_result", {}).items():
        lines.append(f"    - {result}: {count}")
    lines.append(f"  Avg duration: {e['avg_duration_mins']} mins")
    lines.append("")

    # Evaluations
    ev = metrics["evaluations"]
    lines.append("## EVALUATIONS")
    lines.append(f"  Total: {ev['total']}")
    lines.append(f"  By grade:")
    for grade, count in sorted(ev.get("by_grade", {}).items()):
        lines.append(f"    - {grade}: {count}")
    lines.append(f"  Avg outcome score: {ev['avg_outcome_score']}/5")
    lines.append("")

    # Key rates
    r = metrics["rates"]
    lines.append("## KEY RATES")
    lines.append(f"  Decision review rate: {r.get('decision_review_rate', 0)*100:.1f}%")
    lines.append(f"  Unverified rate: {r.get('unverified_rate', 0)*100:.1f}%")
    lines.append(f"  Reopen rate: {r.get('reopen_rate', 0)*100:.1f}%")
    lines.append("")

    # Health
    if metrics["health"]:
        lines.append("## HEALTH WARNINGS")
        for warning in metrics["health"]:
            lines.append(f"  [!] {warning}")
        lines.append("")

    lines.append("=" * 50)
    return "\n".join(lines)


def store_metrics(metrics):
    """Store metrics as a fact in Duro."""
    try:
        from artifacts import ArtifactStore
        store = ArtifactStore(MEMORY_DIR, DB_PATH)

        d = metrics["decisions"]
        r = metrics["rates"]

        claim = (
            f"Duro Eval Metrics ({metrics['computed_at'][:10]}): "
            f"{d['total']} decisions ({d['real_decisions']} real), "
            f"{d['by_status'].get('unverified', 0)} unverified, "
            f"{d['by_status'].get('validated', 0)} validated, "
            f"{d['by_status'].get('reversed', 0)} reversed. "
            f"Review rate: {r.get('decision_review_rate', 0)*100:.1f}%. "
            f"Unverified rate: {r.get('unverified_rate', 0)*100:.1f}%. "
            f"Reopen rate: {r.get('reopen_rate', 0)*100:.1f}%."
        )

        artifact_id = store.store_fact(
            claim=claim,
            source_urls=[],
            snippet=json.dumps(metrics, indent=2)[:2000],
            confidence=0.9,
            evidence_type="inference",
            provenance="tool_output",
            tags=["eval-metrics", "governance", "tracking", metrics['computed_at'][:10]],
            sensitivity="internal",
            workflow="eval_metrics_skill"
        )
        return artifact_id

    except Exception as e:
        return f"Error storing: {e}"


def run_eval_metrics(store_result=False, json_output=False):
    """Run the eval metrics computation."""
    metrics = compute_metrics()

    if "error" in metrics:
        print(f"[ERROR] {metrics['error']}")
        return False

    if json_output:
        print(json.dumps(metrics, indent=2))
    else:
        print(format_report(metrics))

    if store_result:
        artifact_id = store_metrics(metrics)
        print(f"\n[STORED] Metrics saved as: {artifact_id}")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute Duro eval metrics")
    parser.add_argument("--store", action="store_true",
                       help="Store metrics as a fact in Duro")
    parser.add_argument("--json", action="store_true",
                       help="Output raw JSON instead of formatted report")
    args = parser.parse_args()

    success = run_eval_metrics(store_result=args.store, json_output=args.json)
    sys.exit(0 if success else 1)
