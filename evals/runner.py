#!/usr/bin/env python3
"""
Duro Eval Runner - Execute evals and record results.

Usage:
    python runner.py                    # Run all evals
    python runner.py --eval eval_id     # Run specific eval
    python runner.py --category skills  # Run category
    python runner.py --dry-run          # Show what would run
    python runner.py --mock             # Run with mocked externals
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Try to import yaml, fall back to basic parsing if unavailable
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

EVALS_DIR = Path(__file__).parent
RESULTS_DIR = EVALS_DIR / "results"
SUITE_FILE = EVALS_DIR / "suite.json"
SCOREBOARD_FILE = EVALS_DIR / "SCOREBOARD.md"


def load_yaml(path: Path) -> dict:
    """Load YAML file, with fallback for missing yaml module."""
    if HAS_YAML:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    else:
        # Basic YAML-like parser for simple cases
        result = {}
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        # This is a fallback - recommend installing pyyaml
        print(f"Warning: pyyaml not installed, using basic parser for {path}")
        return {"_raw": content, "_parse_error": "Install pyyaml for full support"}


def load_suite() -> dict:
    """Load the eval suite configuration."""
    if not SUITE_FILE.exists():
        return {"evals": [], "version": "1.0"}
    with open(SUITE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_eval_definition(eval_entry: dict) -> dict:
    """Load a single eval definition from its YAML file."""
    eval_path = EVALS_DIR / eval_entry["file"]
    if not eval_path.exists():
        return {"error": f"Eval file not found: {eval_path}"}
    return load_yaml(eval_path)


def get_today_results_path() -> Path:
    """Get the path for today's results file."""
    today = datetime.now().strftime("%Y-%m-%d")
    return RESULTS_DIR / f"{today}.json"


def load_today_results() -> dict:
    """Load or create today's results file."""
    path = get_today_results_path()
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "summary": {"total_evals_run": 0, "passed": 0, "failed": 0, "skipped": 0, "flaky": 0},
        "results": [],
        "lessons_learned": [],
        "skills_used": [],
    }


def save_results(results: dict) -> None:
    """Save results to today's file."""
    RESULTS_DIR.mkdir(exist_ok=True)
    path = get_today_results_path()

    # Update summary
    total = len(results["results"])
    passed = sum(1 for r in results["results"] if r.get("pass"))
    failed = sum(1 for r in results["results"] if not r.get("pass") and not r.get("skipped"))
    skipped = sum(1 for r in results["results"] if r.get("skipped"))
    flaky = sum(1 for r in results["results"] if r.get("flaky_triggered"))

    results["summary"] = {
        "total_evals_run": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "flaky": flaky,
        "pass_rate": passed / total if total > 0 else 0
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {path}")


class EvalRunner:
    """Execute evaluations and track results."""

    def __init__(self, mock_mode: bool = False, dry_run: bool = False, verbose: bool = False):
        self.mock_mode = mock_mode
        self.dry_run = dry_run
        self.verbose = verbose
        self.suite = load_suite()
        self.results = load_today_results()

    def log(self, msg: str) -> None:
        """Log message if verbose."""
        if self.verbose:
            print(f"  {msg}")

    def get_evals(self, eval_id: str = None, category: str = None) -> list:
        """Get evals to run, filtered by id or category."""
        evals = self.suite.get("evals", [])

        if eval_id:
            evals = [e for e in evals if e["id"] == eval_id]
        elif category:
            evals = [e for e in evals if e.get("category") == category]

        return evals

    def should_skip_flaky(self, eval_def: dict) -> bool:
        """Check if a flaky eval should be skipped in this run."""
        if not eval_def.get("flaky"):
            return False
        # In mock mode, run flaky evals with mocks
        if self.mock_mode:
            return False
        # Otherwise skip flaky evals unless explicitly requested
        return True

    def execute_skill(self, skill_path: str, inputs: dict, eval_def: dict) -> dict:
        """Execute a skill and return results."""
        if self.dry_run:
            return {"dry_run": True, "would_execute": skill_path, "inputs": inputs}

        start_time = time.time()
        result = {
            "executed": True,
            "pass": False,
            "time_seconds": 0,
            "outputs": {},
            "errors": [],
        }

        try:
            # Import and run the skill
            skill_full_path = Path(__file__).parent.parent / "skills" / skill_path

            if not skill_full_path.exists():
                result["errors"].append(f"Skill not found: {skill_full_path}")
                return result

            # For mock mode, simulate success
            if self.mock_mode:
                self.log(f"MOCK: Would execute {skill_path}")
                result["pass"] = True
                result["mock_mode"] = True
                result["time_seconds"] = 0.1
                return result

            # Real execution - import and run
            import importlib.util
            spec = importlib.util.spec_from_file_location("skill_module", skill_full_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Look for main/run/execute function
            run_fn = getattr(module, 'run', None) or getattr(module, 'main', None) or getattr(module, 'execute', None)

            if run_fn:
                output = run_fn(**inputs)
                result["outputs"] = output if isinstance(output, dict) else {"result": output}
                result["pass"] = True
            else:
                result["errors"].append("No run/main/execute function found in skill")

        except Exception as e:
            result["errors"].append(str(e))

        result["time_seconds"] = round(time.time() - start_time, 2)
        return result

    def validate_outputs(self, actual: dict, expected: list, eval_def: dict) -> dict:
        """Validate actual outputs against expected outputs."""
        validation = {"passed": True, "checks": []}

        for exp in expected:
            check = {"name": exp.get("name", "unknown"), "passed": False, "details": ""}
            exp_type = exp.get("type", "boolean")

            if exp_type == "boolean":
                # Check if a boolean condition is true
                check["passed"] = actual.get(exp["name"], False) == True
            elif exp_type == "constraint":
                # Check numeric constraint
                threshold = exp.get("threshold", 0)
                actual_val = actual.get(exp["name"], 0)
                check["passed"] = actual_val >= threshold
                check["details"] = f"actual={actual_val}, threshold={threshold}"
            elif exp_type == "exists":
                # Check if key exists
                check["passed"] = exp["name"] in actual

            validation["checks"].append(check)
            if not check["passed"]:
                validation["passed"] = False

        return validation

    def run_eval(self, eval_entry: dict) -> dict:
        """Run a single evaluation."""
        eval_id = eval_entry["id"]
        eval_name = eval_entry["name"]

        print(f"\n{'='*50}")
        print(f"Running: {eval_name} ({eval_id})")
        print(f"{'='*50}")

        # Load full definition
        eval_def = load_eval_definition(eval_entry)
        if "error" in eval_def:
            print(f"  ERROR: {eval_def['error']}")
            return {"eval_id": eval_id, "name": eval_name, "pass": False, "error": eval_def["error"]}

        # Check if flaky and should skip
        if self.should_skip_flaky(eval_def):
            print(f"  SKIPPED: Flaky eval (use --mock to run with mocks)")
            return {"eval_id": eval_id, "name": eval_name, "skipped": True, "reason": "flaky"}

        # Get skill to test
        skill_path = eval_def.get("skill_path") or eval_def.get("tests_skill")
        if not skill_path:
            print(f"  ERROR: No skill_path defined in eval")
            return {"eval_id": eval_id, "name": eval_name, "pass": False, "error": "No skill_path"}

        # Prepare inputs
        inputs = {}
        input_defs = eval_def.get("inputs", {})
        if isinstance(input_defs, dict):
            for key, val in input_defs.items():
                if isinstance(val, dict):
                    inputs[key] = val.get("default") or val.get("example")
                else:
                    inputs[key] = val

        # Execute with retry for flaky
        retry_count = eval_def.get("retry_count", 1) if eval_def.get("flaky") else 1
        last_result = None

        for attempt in range(retry_count):
            if attempt > 0:
                print(f"  Retry {attempt + 1}/{retry_count}...")
                time.sleep(1)  # Brief pause between retries

            exec_result = self.execute_skill(skill_path, inputs, eval_def)
            last_result = exec_result

            if exec_result.get("pass"):
                break

        # Build result record
        result = {
            "eval_id": eval_id,
            "name": eval_name,
            "pass": last_result.get("pass", False),
            "time_seconds": last_result.get("time_seconds", 0),
            "mock_mode": last_result.get("mock_mode", False),
            "dry_run": last_result.get("dry_run", False),
            "errors": last_result.get("errors", []),
            "flaky_triggered": retry_count > 1 and last_result.get("pass"),
            "timestamp": datetime.now().isoformat(),
        }

        # Report
        status = "PASS" if result["pass"] else "FAIL"
        if result.get("dry_run"):
            status = "DRY-RUN"
        elif result.get("mock_mode"):
            status = "PASS (mock)"

        print(f"  Status: {status}")
        print(f"  Time: {result['time_seconds']}s")
        if result["errors"]:
            print(f"  Errors: {result['errors']}")

        return result

    def run(self, eval_id: str = None, category: str = None) -> dict:
        """Run evals and return summary."""
        evals = self.get_evals(eval_id, category)

        if not evals:
            print("No evals found matching criteria")
            return {"total": 0, "passed": 0, "failed": 0}

        print(f"\nDuro Eval Runner")
        print(f"Mode: {'DRY-RUN' if self.dry_run else 'MOCK' if self.mock_mode else 'REAL'}")
        print(f"Evals to run: {len(evals)}")

        for eval_entry in evals:
            result = self.run_eval(eval_entry)
            self.results["results"].append(result)

        # Save results
        if not self.dry_run:
            save_results(self.results)

        # Print summary
        summary = self.results["summary"]
        print(f"\n{'='*50}")
        print("SUMMARY")
        print(f"{'='*50}")
        print(f"Total: {summary.get('total_evals_run', len(evals))}")
        print(f"Passed: {summary.get('passed', 0)}")
        print(f"Failed: {summary.get('failed', 0)}")
        print(f"Skipped: {summary.get('skipped', 0)}")
        if summary.get('flaky'):
            print(f"Flaky (passed on retry): {summary['flaky']}")

        return summary


def update_scoreboard(results_path: Path = None) -> None:
    """Update SCOREBOARD.md from recent results."""
    results_files = sorted(RESULTS_DIR.glob("*.json"), reverse=True)[:7]  # Last 7 days

    if not results_files:
        print("No results to generate scoreboard from")
        return

    # Load all results
    all_results = []
    for rf in results_files:
        with open(rf, 'r', encoding='utf-8') as f:
            all_results.append(json.load(f))

    latest = all_results[0]

    # Generate scoreboard markdown
    md = f"""# Duro Scoreboard

**Last updated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Period:** Last 7 days

---

## Overall Health

| Metric | Value | Trend |
|--------|-------|-------|
| Eval pass rate | {latest['summary'].get('pass_rate', 0)*100:.0f}% ({latest['summary'].get('passed', 0)}/{latest['summary'].get('total_evals_run', 0)}) | - |
| Evals run today | {latest['summary'].get('total_evals_run', 0)} | - |
| Flaky triggers | {latest['summary'].get('flaky', 0)} | - |

---

## Recent Results

| Date | Pass Rate | Passed | Failed | Skipped |
|------|-----------|--------|--------|---------|
"""

    for r in all_results[:7]:
        date = r.get("date", "unknown")
        s = r.get("summary", {})
        pr = s.get("pass_rate", 0) * 100
        md += f"| {date} | {pr:.0f}% | {s.get('passed', 0)} | {s.get('failed', 0)} | {s.get('skipped', 0)} |\n"

    md += """
---

## Eval Details (Today)

| Eval | Status | Time | Notes |
|------|--------|------|-------|
"""

    for result in latest.get("results", []):
        status = "PASS" if result.get("pass") else "SKIP" if result.get("skipped") else "FAIL"
        emoji = {"PASS": "ok", "FAIL": "X", "SKIP": "-"}.get(status, "?")
        time_s = result.get("time_seconds", 0)
        notes = ", ".join(result.get("errors", [])) or result.get("reason", "")
        md += f"| {result.get('name', result.get('eval_id'))} | {status} | {time_s}s | {notes[:50]} |\n"

    md += """
---

*Auto-generated by runner.py*
"""

    with open(SCOREBOARD_FILE, 'w', encoding='utf-8') as f:
        f.write(md)

    print(f"Scoreboard updated: {SCOREBOARD_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Duro Eval Runner")
    parser.add_argument("--eval", help="Run specific eval by ID")
    parser.add_argument("--category", help="Run evals in category (skills, fashanus, general)")
    parser.add_argument("--mock", action="store_true", help="Run with mocked external calls")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run without executing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--scoreboard", action="store_true", help="Update scoreboard only")

    args = parser.parse_args()

    if args.scoreboard:
        update_scoreboard()
        return

    runner = EvalRunner(
        mock_mode=args.mock,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    summary = runner.run(eval_id=args.eval, category=args.category)

    # Update scoreboard after run
    if not args.dry_run:
        update_scoreboard()

    # Exit code based on results
    if summary.get("failed", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
