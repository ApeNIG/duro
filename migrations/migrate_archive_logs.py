"""
Migration: Extract tasks and learnings from markdown archives and index as log artifacts.

This recovers 281 tasks and 367 learnings that were written to markdown but never indexed.

Usage:
    python migrations/migrate_archive_logs.py [--dry-run]
"""

import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from artifacts import ArtifactStore, generate_id

# Patterns to extract from markdown
TASK_PATTERN = re.compile(
    r'### \[(\d{2}:\d{2})\] Task Completed\n'
    r'\*\*Task:\*\* (.+?)\n'
    r'\*\*Outcome:\*\* (.+?)(?=\n\n|\n###|\Z)',
    re.DOTALL
)

LEARNING_PATTERN = re.compile(
    r'### \[(\d{2}:\d{2})\] Learnings\n'
    r'\*\*Learning \(([^)]+)\):\*\* (.+?)(?=\n\n|\n###|\Z)',
    re.DOTALL
)

# Alternative patterns (some logs use different format)
TASK_PATTERN_ALT = re.compile(
    r'- \[(\d{2}:\d{2})\] (.+?) → (.+?)(?=\n-|\n\n|\Z)',
    re.DOTALL
)


def parse_archive(filepath: Path) -> tuple[list, list]:
    """Parse a single archive file and extract tasks and learnings."""
    content = filepath.read_text(encoding='utf-8')
    date_str = filepath.stem  # e.g., "2026-02-15"

    tasks = []
    learnings = []

    # Extract tasks
    for match in TASK_PATTERN.finditer(content):
        time_str, task, outcome = match.groups()
        tasks.append({
            'date': date_str,
            'time': time_str,
            'task': task.strip(),
            'outcome': outcome.strip()
        })

    # Try alternative pattern if no matches
    if not tasks:
        for match in TASK_PATTERN_ALT.finditer(content):
            time_str, task, outcome = match.groups()
            tasks.append({
                'date': date_str,
                'time': time_str,
                'task': task.strip(),
                'outcome': outcome.strip()
            })

    # Extract learnings
    for match in LEARNING_PATTERN.finditer(content):
        time_str, category, learning = match.groups()
        learnings.append({
            'date': date_str,
            'time': time_str,
            'category': category.strip(),
            'learning': learning.strip()
        })

    return tasks, learnings


def create_log_artifact(store: ArtifactStore, entry: dict, entry_type: str) -> tuple[bool, str]:
    """Create a log artifact from an extracted entry."""

    # Create timestamp from date + time
    date_str = entry['date']
    time_str = entry['time']
    timestamp = f"{date_str}T{time_str}:00Z"

    if entry_type == 'task':
        success, artifact_id, path = store.store_log(
            event_type="task_complete",
            message=f"{entry['task']}: {entry['outcome']}",
            task=entry['task'],
            outcome=entry['outcome'],
            tags=['migrated', 'archive-recovery'],
            workflow="migration"
        )
        # Update created_at to original time
        if success:
            update_artifact_timestamp(path, timestamp)
        return success, artifact_id

    elif entry_type == 'learning':
        success, artifact_id, path = store.store_log(
            event_type="learning",
            message=entry['learning'],
            tags=['migrated', 'archive-recovery', entry['category']],
            workflow="migration"
        )
        # Update created_at to original time
        if success:
            update_artifact_timestamp(path, timestamp)
        return success, artifact_id

    return False, ""


def update_artifact_timestamp(filepath: str, timestamp: str):
    """Update the created_at timestamp in an artifact file."""
    try:
        path = Path(filepath)
        if path.exists():
            artifact = json.loads(path.read_text(encoding='utf-8'))
            artifact['created_at'] = timestamp
            artifact['tags'] = artifact.get('tags', []) + ['timestamp-corrected']
            path.write_text(json.dumps(artifact, indent=2), encoding='utf-8')
    except Exception as e:
        print(f"  Warning: Could not update timestamp: {e}")


def run_migration(dry_run: bool = False):
    """Run the migration."""
    print("=" * 60)
    print("MIGRATION: Archive Logs to Indexed Artifacts")
    print("=" * 60)

    archive_dir = Path.home() / '.agent/memory/archive'

    if not archive_dir.exists():
        print(f"ERROR: Archive directory not found: {archive_dir}")
        return False

    # Collect all entries
    all_tasks = []
    all_learnings = []

    print(f"\nScanning archives in {archive_dir}...")
    for archive_file in sorted(archive_dir.glob('*.md')):
        tasks, learnings = parse_archive(archive_file)
        all_tasks.extend(tasks)
        all_learnings.extend(learnings)
        print(f"  {archive_file.name}: {len(tasks)} tasks, {len(learnings)} learnings")

    print(f"\nTotal found: {len(all_tasks)} tasks, {len(all_learnings)} learnings")

    if dry_run:
        print("\n[DRY RUN] Would create the following artifacts:")
        print(f"  - {len(all_tasks)} task_complete logs")
        print(f"  - {len(all_learnings)} learning logs")
        print("\nRun without --dry-run to execute.")
        return True

    # Initialize artifact store with correct arguments
    config_path = Path.home() / '.agent'
    memory_dir = config_path / 'memory'
    db_path = memory_dir / 'artifacts.db'
    store = ArtifactStore(memory_dir, db_path)

    # Create artifacts
    print("\nCreating artifacts...")

    task_success = 0
    task_fail = 0
    for entry in all_tasks:
        success, artifact_id = create_log_artifact(store, entry, 'task')
        if success:
            task_success += 1
        else:
            task_fail += 1
            print(f"  FAIL: {entry['task'][:50]}...")

    learning_success = 0
    learning_fail = 0
    for entry in all_learnings:
        success, artifact_id = create_log_artifact(store, entry, 'learning')
        if success:
            learning_success += 1
        else:
            learning_fail += 1
            print(f"  FAIL: {entry['learning'][:50]}...")

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Tasks:     {task_success} created, {task_fail} failed")
    print(f"Learnings: {learning_success} created, {learning_fail} failed")
    print(f"Total:     {task_success + learning_success} new artifacts")

    return task_fail == 0 and learning_fail == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate archive logs to indexed artifacts")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be done without doing it")
    args = parser.parse_args()

    success = run_migration(dry_run=args.dry_run)
    sys.exit(0 if success else 1)
