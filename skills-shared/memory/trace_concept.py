"""
Skill: trace_concept
Description: Track how a concept evolves over time across all artifact types
Version: 1.0.0
Tier: tested

Given a keyword or tag, builds a chronological narrative arc showing:
- First mention and origin context
- How confidence/understanding shifted over time
- Contradictions or reversals
- Current state (latest artifacts)
- Artifact type distribution (where does thinking happen?)

This is the "biography" of an idea inside Duro.

Flow:
1. Query artifacts by tag match + semantic search on the concept
2. Deduplicate and merge results
3. Sort chronologically
4. Detect phases (clusters in time), confidence shifts, contradictions
5. Build narrative arc with timeline + analysis

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function
"""

import re
import time
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


# Skill metadata
SKILL_META = {
    "name": "trace_concept",
    "description": "Track how a concept evolves over time across all artifact types",
    "tier": "tested",
    "version": "1.0.0",
    "author": "duro",
    "origin": "Reflective layer roadmap (Greg Eisenberg x Internet Vin podcast)",
    "validated": "2026-02-24",
    "triggers": ["trace", "concept", "evolution", "timeline", "history of", "arc"],
    "keywords": [
        "trace", "concept", "evolution", "timeline", "history", "arc",
        "narrative", "chronological", "first mention", "contradiction"
    ],
    "phase": "4.0",
}

DEFAULT_CONFIG = {
    "max_results": 50,          # Max artifacts to include in trace
    "max_semantic_results": 30,  # Max from semantic search
    "max_tag_results": 30,       # Max from tag query
    "phase_gap_days": 7,         # Days of silence to mark a new phase
}

REQUIRES = ["query_memory", "semantic_search"]

DEFAULT_TIMEOUT = 60


@dataclass
class TraceEvent:
    """A single event in a concept's timeline."""
    artifact_id: str
    artifact_type: str
    timestamp: str
    text: str
    tags: List[str]
    confidence: Optional[float] = None
    relevance_score: float = 0.0

    @property
    def datetime(self) -> Optional[datetime]:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f",
                     "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                     "%Y-%m-%d"):
            try:
                return datetime.strptime(self.timestamp[:26], fmt)
            except (ValueError, TypeError):
                continue
        return None


@dataclass
class Phase:
    """A cluster of activity around a concept."""
    start: str
    end: str
    event_count: int
    artifact_types: Dict[str, int]
    summary_event: Optional[TraceEvent] = None  # highest-relevance event
    label: str = ""


def extract_text(artifact: Dict) -> str:
    """Extract main text content from an artifact."""
    if "data" in artifact:
        data = artifact["data"]
        parts = []
        for key in ("message", "claim", "decision", "rationale", "title", "description"):
            val = data.get(key, "")
            if val:
                parts.append(str(val))
        return " ".join(parts) if parts else ""
    for key in ("message", "claim", "title", "decision"):
        val = artifact.get(key, "")
        if val:
            return str(val)
    return ""


def extract_confidence(artifact: Dict) -> Optional[float]:
    """Extract confidence score if present."""
    if "data" in artifact:
        conf = artifact["data"].get("confidence")
    else:
        conf = artifact.get("confidence")
    if conf is not None:
        try:
            return float(conf)
        except (ValueError, TypeError):
            pass
    return None


def extract_timestamp(artifact: Dict) -> str:
    """Extract the best timestamp from an artifact."""
    return (
        artifact.get("created_at", "") or
        artifact.get("timestamp", "") or
        (artifact.get("data", {}) or {}).get("created_at", "") or
        ""
    )


def extract_tags(artifact: Dict) -> List[str]:
    return artifact.get("tags", []) or []


def extract_type(artifact: Dict) -> str:
    return artifact.get("artifact_type", artifact.get("type", "unknown"))


def concept_relevance(text: str, concept: str) -> float:
    """Score how relevant an artifact's text is to the concept (0-1)."""
    text_lower = text.lower()
    concept_lower = concept.lower()
    concept_words = concept_lower.split()

    score = 0.0

    # Exact phrase match (strongest signal)
    if concept_lower in text_lower:
        score += 0.5

    # Individual word matches
    word_hits = sum(1 for w in concept_words if w in text_lower)
    if concept_words:
        score += 0.3 * (word_hits / len(concept_words))

    # Title/first-sentence prominence
    first_100 = text_lower[:100]
    if concept_lower in first_100:
        score += 0.2

    return min(1.0, score)


def detect_phases(
    events: List[TraceEvent],
    gap_days: int = 7
) -> List[Phase]:
    """
    Group events into phases separated by gaps of silence.
    A phase is a cluster of activity around the concept.
    """
    if not events:
        return []

    phases = []
    current_events = [events[0]]

    for i in range(1, len(events)):
        prev_dt = events[i - 1].datetime
        curr_dt = events[i].datetime

        if prev_dt and curr_dt:
            gap = (curr_dt - prev_dt).days
        else:
            gap = 0

        if gap > gap_days:
            # Close current phase
            phases.append(_build_phase(current_events))
            current_events = [events[i]]
        else:
            current_events.append(events[i])

    # Close final phase
    if current_events:
        phases.append(_build_phase(current_events))

    # Label phases
    for i, phase in enumerate(phases, 1):
        phase.label = f"Phase {i}"

    return phases


def _build_phase(events: List[TraceEvent]) -> Phase:
    """Build a Phase from a group of events."""
    type_counts = defaultdict(int)
    best_event = events[0]
    for e in events:
        type_counts[extract_type({"artifact_type": e.artifact_type})] += 1
        if e.relevance_score > best_event.relevance_score:
            best_event = e

    return Phase(
        start=events[0].timestamp,
        end=events[-1].timestamp,
        event_count=len(events),
        artifact_types=dict(type_counts),
        summary_event=best_event,
    )


def detect_confidence_shifts(events: List[TraceEvent]) -> List[Dict]:
    """Find significant confidence changes over time."""
    shifts = []
    conf_events = [(e, e.confidence) for e in events if e.confidence is not None]

    if len(conf_events) < 2:
        return shifts

    for i in range(1, len(conf_events)):
        prev_e, prev_c = conf_events[i - 1]
        curr_e, curr_c = conf_events[i]
        delta = curr_c - prev_c

        if abs(delta) >= 0.15:  # Significant shift
            direction = "increased" if delta > 0 else "decreased"
            shifts.append({
                "from_id": prev_e.artifact_id,
                "to_id": curr_e.artifact_id,
                "from_confidence": round(prev_c, 2),
                "to_confidence": round(curr_c, 2),
                "delta": round(delta, 2),
                "direction": direction,
                "from_date": prev_e.timestamp[:10],
                "to_date": curr_e.timestamp[:10],
            })

    return shifts


def detect_contradictions(events: List[TraceEvent], concept: str) -> List[Dict]:
    """
    Detect potential contradictions — artifacts that contain negation
    or reversal language near the concept.
    """
    contradiction_signals = [
        r'\bnot\b', r'\bno longer\b', r'\bactually\b', r'\binstead\b',
        r'\bwrong\b', r'\bmistake\b', r'\brevert', r'\bundo\b',
        r'\bcontrar', r'\bopposite\b', r'\boverrid', r'\breplac',
        r'\bdeprecated?\b', r'\babandoned?\b', r'\bdropped?\b',
    ]

    contradictions = []
    concept_lower = concept.lower()

    for event in events:
        text_lower = event.text.lower()
        if concept_lower not in text_lower:
            continue

        # Check for contradiction signals near the concept
        hits = []
        for pattern in contradiction_signals:
            if re.search(pattern, text_lower):
                hits.append(pattern.strip(r'\b'))

        if hits:
            contradictions.append({
                "artifact_id": event.artifact_id,
                "artifact_type": event.artifact_type,
                "date": event.timestamp[:10],
                "text": event.text[:200],
                "signals": hits[:3],
            })

    return contradictions


def format_report(
    concept: str,
    events: List[TraceEvent],
    phases: List[Phase],
    confidence_shifts: List[Dict],
    contradictions: List[Dict],
    type_distribution: Dict[str, int],
) -> str:
    """Format the trace_concept report."""
    lines = []
    lines.append(f"## Concept Trace: \"{concept}\"")
    lines.append("")

    if not events:
        lines.append(f"No artifacts found related to \"{concept}\".")
        return "\n".join(lines)

    first = events[0]
    last = events[-1]

    lines.append(f"**Span:** {first.timestamp[:10]} → {last.timestamp[:10]}")
    lines.append(f"**Artifacts:** {len(events)} across {len(type_distribution)} types")
    lines.append(f"**Phases:** {len(phases)}")

    # Type distribution
    type_str = ", ".join(f"{k}: {v}" for k, v in sorted(type_distribution.items(), key=lambda x: -x[1]))
    lines.append(f"**Distribution:** {type_str}")
    lines.append("")

    # --- Origin ---
    lines.append("### Origin")
    lines.append(f"**First mention:** {first.timestamp[:10]} ({first.artifact_type})")
    truncated = first.text[:200] + "..." if len(first.text) > 200 else first.text
    lines.append(f"> {truncated}")
    lines.append("")

    # --- Phases ---
    if phases:
        lines.append("### Timeline")
        lines.append("")
        for phase in phases:
            type_str = ", ".join(f"{k}: {v}" for k, v in phase.artifact_types.items())
            lines.append(f"**{phase.label}** ({phase.start[:10]} → {phase.end[:10]}) — {phase.event_count} artifacts")
            lines.append(f"  Types: {type_str}")
            if phase.summary_event:
                summary = phase.summary_event.text[:150]
                if len(phase.summary_event.text) > 150:
                    summary += "..."
                lines.append(f"  Key: {summary}")
            lines.append("")

    # --- Confidence Shifts ---
    if confidence_shifts:
        lines.append("### Confidence Shifts")
        lines.append("")
        for shift in confidence_shifts:
            lines.append(
                f"- {shift['from_date']} → {shift['to_date']}: "
                f"**{shift['direction']}** from {shift['from_confidence']} to {shift['to_confidence']} "
                f"(Δ{shift['delta']:+.2f})"
            )
        lines.append("")

    # --- Contradictions ---
    if contradictions:
        lines.append("### Potential Contradictions / Reversals")
        lines.append("")
        for c in contradictions[:5]:
            lines.append(f"- **{c['date']}** ({c['artifact_type']}): {c['text'][:120]}...")
            lines.append(f"  Signals: {', '.join(c['signals'])}")
        lines.append("")

    # --- Current State ---
    lines.append("### Current State")
    recent = events[-3:] if len(events) >= 3 else events
    for e in reversed(recent):
        truncated = e.text[:150] + "..." if len(e.text) > 150 else e.text
        conf_str = f" (conf: {e.confidence})" if e.confidence is not None else ""
        lines.append(f"- **{e.timestamp[:10]}** [{e.artifact_type}]{conf_str}: {truncated}")
    lines.append("")

    return "\n".join(lines)


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            concept: str (required) - The keyword, tag, or phrase to trace
            max_results: int (default 50) - Max artifacts in trace
            phase_gap_days: int (default 7) - Days of silence to split phases
        }
        tools: {
            query_memory: callable
            semantic_search: callable
        }
        context: {run_id, timeout}

    Returns:
        {
            success: bool,
            report: str,
            events: List[dict],
            phases: List[dict],
            confidence_shifts: List[dict],
            contradictions: List[dict],
            type_distribution: dict,
            total_events: int,
            elapsed_seconds: float,
        }
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    concept = args.get("concept", "").strip()
    if not concept:
        return {"success": False, "error": "concept parameter is required"}

    max_results = args.get("max_results", DEFAULT_CONFIG["max_results"])
    max_semantic = args.get("max_semantic_results", DEFAULT_CONFIG["max_semantic_results"])
    max_tag = args.get("max_tag_results", DEFAULT_CONFIG["max_tag_results"])
    phase_gap = args.get("phase_gap_days", DEFAULT_CONFIG["phase_gap_days"])

    query_memory = tools.get("query_memory")
    semantic_search = tools.get("semantic_search")

    if not query_memory:
        return {"success": False, "error": "query_memory tool is required"}

    # ==============================
    # Step 1: Gather artifacts via tag + semantic search
    # ==============================
    seen_ids = set()
    raw_artifacts = []

    # 1a: Tag-based query across types
    scan_types = ["fact", "decision", "log", "episode", "evaluation", "incident_rca", "design_reference"]
    for art_type in scan_types:
        if time.time() - start_time >= timeout * 0.5:
            break
        try:
            result = query_memory(
                artifact_type=art_type,
                tags=[concept],
                limit=max_tag
            )
            items = []
            if isinstance(result, list):
                items = result
            elif isinstance(result, dict):
                items = result.get("results", result.get("artifacts", []))
            for item in items:
                art_id = item.get("id", "")
                if art_id and art_id not in seen_ids:
                    if "artifact_type" not in item:
                        item["artifact_type"] = art_type
                    seen_ids.add(art_id)
                    raw_artifacts.append(item)
        except Exception:
            continue

    # 1b: Semantic search (catches artifacts that reference the concept without tagging it)
    if semantic_search and time.time() - start_time < timeout * 0.7:
        try:
            result = semantic_search(query=concept, limit=max_semantic)
            items = []
            if isinstance(result, dict):
                items = result.get("results", [])
            elif isinstance(result, list):
                items = result
            for item in items:
                art_id = item.get("id", "")
                if art_id and art_id not in seen_ids:
                    seen_ids.add(art_id)
                    raw_artifacts.append(item)
        except Exception:
            pass

    if not raw_artifacts:
        return {
            "success": True,
            "report": f"No artifacts found related to \"{concept}\".",
            "events": [],
            "phases": [],
            "confidence_shifts": [],
            "contradictions": [],
            "type_distribution": {},
            "total_events": 0,
            "elapsed_seconds": round(time.time() - start_time, 2),
        }

    # ==============================
    # Step 2: Convert to TraceEvents, score relevance
    # ==============================
    events = []
    for art in raw_artifacts:
        text = extract_text(art)
        if not text or len(text.strip()) < 20:
            continue

        timestamp = extract_timestamp(art)
        if not timestamp:
            continue

        relevance = concept_relevance(text, concept)

        events.append(TraceEvent(
            artifact_id=art.get("id", "unknown"),
            artifact_type=extract_type(art),
            timestamp=timestamp,
            text=text,
            tags=extract_tags(art),
            confidence=extract_confidence(art),
            relevance_score=relevance,
        ))

    # Filter by minimum relevance (keep tag-matched even if low text relevance)
    concept_lower = concept.lower()
    events = [
        e for e in events
        if e.relevance_score >= 0.2 or concept_lower in " ".join(e.tags).lower()
    ]

    # Sort chronologically
    events.sort(key=lambda e: e.timestamp)

    # Cap at max_results (keep most relevant if over limit)
    if len(events) > max_results:
        events.sort(key=lambda e: -e.relevance_score)
        events = events[:max_results]
        events.sort(key=lambda e: e.timestamp)

    # ==============================
    # Step 3: Analysis
    # ==============================
    type_distribution = defaultdict(int)
    for e in events:
        type_distribution[e.artifact_type] += 1

    phases = detect_phases(events, gap_days=phase_gap)
    confidence_shifts = detect_confidence_shifts(events)
    contradictions = detect_contradictions(events, concept)

    # ==============================
    # Step 4: Report
    # ==============================
    report = format_report(
        concept, events, phases, confidence_shifts,
        contradictions, dict(type_distribution)
    )

    # Serialize for output
    events_output = [
        {
            "artifact_id": e.artifact_id,
            "artifact_type": e.artifact_type,
            "timestamp": e.timestamp,
            "text": e.text[:300],
            "confidence": e.confidence,
            "relevance": e.relevance_score,
        }
        for e in events
    ]

    phases_output = [
        {
            "label": p.label,
            "start": p.start,
            "end": p.end,
            "event_count": p.event_count,
            "artifact_types": p.artifact_types,
            "key_text": p.summary_event.text[:200] if p.summary_event else "",
        }
        for p in phases
    ]

    elapsed = round(time.time() - start_time, 2)

    return {
        "success": True,
        "report": report,
        "events": events_output,
        "phases": phases_output,
        "confidence_shifts": confidence_shifts,
        "contradictions": contradictions,
        "type_distribution": dict(type_distribution),
        "total_events": len(events),
        "elapsed_seconds": elapsed,
    }


# --- CLI Mode ---
if __name__ == "__main__":
    print("trace_concept Skill v1.0.0")
    print("=" * 50)
    print(f"Origin: {SKILL_META['origin']}")
    print()
    print("Usage: run({'concept': 'design philosophy'}, tools, ctx)")
    print()
    print("Output:")
    print("  - Chronological timeline with phases")
    print("  - First mention / origin context")
    print("  - Confidence shifts over time")
    print("  - Contradictions / reversals")
    print("  - Current state (most recent artifacts)")
    print("  - Artifact type distribution")
    print()
    print("Default config:")
    for k, v in DEFAULT_CONFIG.items():
        print(f"  {k}: {v}")
