"""
Skill: promote_learnings
Description: Promote learnings from daily logs to indexed facts
Version: 1.0.0
Tier: memory

This skill bridges the gap between fast capture (duro_save_learning -> markdown logs)
and indexed retrieval (structured facts with embeddings).

Flow:
1. Parse memory/YYYY-MM-DD.md for learning blocks
2. Extract category and content
3. Check if already promoted (via marker or dedup)
4. Store as fact with proper tags
5. Mark as promoted in log

Usage:
    python promote_learnings.py                    # Promote from today's log
    python promote_learnings.py 2026-02-15         # Promote from specific date
    python promote_learnings.py --all              # Promote from all logs
"""

import re
import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

# Path setup
MEMORY_DIR = Path(__file__).parent.parent.parent / "memory"


@dataclass
class ExtractedLearning:
    """A learning extracted from a log file."""
    timestamp: str
    category: str
    content: str
    source_file: str
    line_number: int
    content_hash: str  # For dedup

    @property
    def tags(self) -> List[str]:
        """Generate tags from category."""
        base_tags = [self.category.lower().replace(" ", "-")]
        # Add common tags based on category
        tag_map = {
            "technical": ["engineering", "implementation"],
            "architecture": ["design", "system-design"],
            "process": ["workflow", "methodology"],
            "system design": ["architecture", "patterns"],
            "testing": ["quality", "verification"],
            "zero lies mode": ["verification", "honesty", "telemetry"],
        }
        extra = tag_map.get(self.category.lower(), [])
        return base_tags + extra


def parse_log_file(log_path: Path) -> List[ExtractedLearning]:
    """Parse a memory log file and extract learnings."""
    learnings = []

    if not log_path.exists():
        return learnings

    content = log_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Look for learning headers: ### [HH:MM] Learnings
        if line.startswith("### [") and "Learnings" in line:
            # Extract timestamp
            match = re.match(r"### \[(\d{2}:\d{2})\] Learnings", line)
            if not match:
                i += 1
                continue
            timestamp = match.group(1)

            # Next line should be **Learning (Category):** content
            if i + 1 < len(lines):
                learning_line = lines[i + 1]

                # Parse: **Learning (Category):** content
                learn_match = re.match(
                    r"\*\*Learning \(([^)]+)\):\*\*\s*(.+)",
                    learning_line
                )

                if learn_match:
                    category = learn_match.group(1)
                    content = learn_match.group(2).strip()

                    # Content might continue on next lines (until next ### or blank)
                    j = i + 2
                    while j < len(lines) and lines[j] and not lines[j].startswith("###"):
                        content += " " + lines[j].strip()
                        j += 1

                    # Create hash for dedup
                    content_hash = hashlib.md5(content.encode()).hexdigest()[:12]

                    learnings.append(ExtractedLearning(
                        timestamp=timestamp,
                        category=category,
                        content=content,
                        source_file=str(log_path),
                        line_number=i + 1,
                        content_hash=content_hash
                    ))

                    i = j
                    continue

        i += 1

    return learnings


def check_already_promoted(learning: ExtractedLearning, existing_facts: List[Dict]) -> bool:
    """Check if a learning has already been promoted to a fact."""
    # Check by content hash in tags
    for fact in existing_facts:
        tags = fact.get("tags", [])
        if f"hash:{learning.content_hash}" in tags:
            return True
        # Also check content similarity (first 100 chars)
        claim = fact.get("claim", "")
        if claim and learning.content[:100].lower() in claim.lower():
            return True
    return False


def promote_to_fact(
    learning: ExtractedLearning,
    store_fact_func,
    dry_run: bool = False
) -> Optional[str]:
    """Promote a learning to a structured fact."""

    tags = learning.tags + [
        f"hash:{learning.content_hash}",
        f"promoted-from:{Path(learning.source_file).stem}",
        "auto-promoted"
    ]

    if dry_run:
        print(f"  [DRY RUN] Would promote: {learning.content[:60]}...")
        print(f"            Tags: {tags}")
        return None

    result = store_fact_func(
        claim=learning.content,
        confidence=0.8,  # Learnings are experiential, not verified
        provenance="user",  # Came from user session
        tags=tags,
        workflow="promote_learnings"
    )

    return result.get("artifact_id") if isinstance(result, dict) else None


def run(
    args: Dict[str, Any],
    tools: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {
            date: str (optional) - specific date YYYY-MM-DD
            all: bool (optional) - process all log files
            dry_run: bool (optional) - preview without storing
        }
        tools: {
            duro_store_fact: callable
            duro_query_memory: callable
        }
        context: {}

    Returns:
        {success, promoted_count, skipped_count, learnings}
    """
    target_date = args.get("date")
    process_all = args.get("all", False)
    dry_run = args.get("dry_run", False)

    store_fact = tools.get("duro_store_fact")
    query_memory = tools.get("duro_query_memory")

    if not store_fact:
        return {"success": False, "error": "duro_store_fact tool required"}

    # Determine which log files to process
    if process_all:
        log_files = sorted(MEMORY_DIR.glob("*.md"))
    elif target_date:
        log_files = [MEMORY_DIR / f"{target_date}.md"]
    else:
        today = date.today().isoformat()
        log_files = [MEMORY_DIR / f"{today}.md"]

    # Get existing facts for dedup
    existing_facts = []
    if query_memory:
        try:
            result = query_memory(artifact_type="fact", limit=500)
            if isinstance(result, list):
                existing_facts = result
        except Exception:
            pass  # Continue without dedup

    # Process each log file
    promoted = []
    skipped = []
    errors = []

    for log_file in log_files:
        if not log_file.exists():
            continue

        learnings = parse_log_file(log_file)

        for learning in learnings:
            # Check if already promoted
            if check_already_promoted(learning, existing_facts):
                skipped.append({
                    "content": learning.content[:60] + "...",
                    "reason": "already_promoted"
                })
                continue

            # Promote
            try:
                fact_id = promote_to_fact(learning, store_fact, dry_run)
                promoted.append({
                    "content": learning.content[:60] + "...",
                    "category": learning.category,
                    "fact_id": fact_id,
                    "tags": learning.tags
                })
            except Exception as e:
                errors.append({
                    "content": learning.content[:60] + "...",
                    "error": str(e)
                })

    return {
        "success": len(errors) == 0,
        "dry_run": dry_run,
        "promoted_count": len(promoted),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "promoted": promoted,
        "skipped": skipped,
        "errors": errors
    }


# CLI for direct use
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Promote learnings from logs to facts")
    parser.add_argument("date", nargs="?", help="Date YYYY-MM-DD (default: today)")
    parser.add_argument("--all", action="store_true", help="Process all log files")
    parser.add_argument("--dry-run", action="store_true", help="Preview without storing")
    parser.add_argument("--list", action="store_true", help="Just list learnings, don't promote")

    args = parser.parse_args()

    # Determine target
    if args.all:
        log_files = sorted(MEMORY_DIR.glob("*.md"))
    elif args.date:
        log_files = [MEMORY_DIR / f"{args.date}.md"]
    else:
        today = date.today().isoformat()
        log_files = [MEMORY_DIR / f"{today}.md"]

    print("=" * 60)
    print("Promote Learnings to Indexed Facts")
    print("=" * 60)

    total_learnings = []
    for log_file in log_files:
        if not log_file.exists():
            print(f"\n[SKIP] {log_file.name} - not found")
            continue

        learnings = parse_log_file(log_file)
        if learnings:
            print(f"\n[FILE] {log_file.name} - {len(learnings)} learnings")
            for l in learnings:
                print(f"  [{l.timestamp}] ({l.category}) {l.content[:50]}...")
            total_learnings.extend(learnings)

    print(f"\n{'=' * 60}")
    print(f"Total: {len(total_learnings)} learnings found")

    if args.list:
        print("\n[LIST MODE] No changes made")
        sys.exit(0)

    if args.dry_run:
        print("\n[DRY RUN] Would promote these to facts (no MCP connection in CLI)")
    else:
        print("\n[NOTE] To actually promote, run via MCP with duro_store_fact tool")

    print("=" * 60)
