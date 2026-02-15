#!/usr/bin/env python3
"""Enforcement Eval Runner - CI-verifiable enforcement tests.

Reads enforcement/*.yaml files and feeds fake tool calls into the hook,
asserting correct BLOCK/WARN/ALLOW decisions.

Usage:
    python enforcement_runner.py              # Run all enforcement evals
    python enforcement_runner.py --verbose    # With debug output
    python enforcement_runner.py --ci         # CI mode (exit code on failure)
"""

import os
import sys
import json
import subprocess
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Paths
SCRIPT_DIR = Path(__file__).parent
ENFORCEMENT_DIR = SCRIPT_DIR / 'enforcement'
HOME = Path.home()
HOOK_PATH = HOME / '.claude' / 'plugins' / 'cache' / 'claude-plugins-official' / 'hookify' / '96276205880a' / 'hooks' / 'pretooluse.py'

# Results storage
RESULTS_FILE = SCRIPT_DIR / 'enforcement_results.json'


class EnforcementRunner:
    """Run enforcement evals and verify hook behavior."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[Dict] = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def log(self, msg: str) -> None:
        """Log message if verbose."""
        if self.verbose:
            print(f"  {msg}")

    def run_hook(self, tool_name: str, tool_input: Dict) -> Tuple[str, Optional[str]]:
        """Run the hook with fake tool call input.

        Returns (decision, rule_name).
        """
        input_data = {
            "tool_name": tool_name,
            "tool_input": tool_input
        }

        try:
            result = subprocess.run(
                [sys.executable, str(HOOK_PATH)],
                input=json.dumps(input_data),
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, 'HOOKIFY_DEBUG': '0'}
            )

            if result.returncode != 0:
                self.log(f"Hook error: {result.stderr}")
                return 'error', None

            output = json.loads(result.stdout) if result.stdout.strip() else {}

            # Parse decision from output
            hook_output = output.get('hookSpecificOutput', {})
            permission = hook_output.get('permissionDecision', 'allow')

            # Map to our terminology
            if permission == 'deny':
                decision = 'blocked'
            elif 'WARNING' in output.get('systemMessage', ''):
                decision = 'warn'
            else:
                decision = 'allowed'

            # Extract rule name
            rule_name = None
            if 'systemMessage' in output:
                msg = output['systemMessage']
                if '**[' in msg and ']**' in msg:
                    rule_name = msg.split('**[')[1].split(']**')[0]

            return decision, rule_name

        except subprocess.TimeoutExpired:
            return 'timeout', None
        except json.JSONDecodeError as e:
            self.log(f"JSON decode error: {e}")
            return 'error', None
        except Exception as e:
            self.log(f"Exception: {e}")
            return 'error', None

    def run_test_case(self, eval_id: str, test_case: Dict) -> Dict:
        """Run a single test case."""
        test_id = test_case.get('id', 'unknown')
        description = test_case.get('description', '')
        expected = test_case.get('expected', 'blocked')
        command = test_case.get('command', '')

        self.log(f"  [{test_id}] {description}")

        # Build tool input
        if command:
            tool_name = 'Bash'
            tool_input = {'command': command}
        else:
            # Skip scenario-based tests for now
            return {
                'eval_id': eval_id,
                'test_id': test_id,
                'status': 'skipped',
                'reason': 'Scenario-based test not yet supported'
            }

        # Run hook
        actual, rule_name = self.run_hook(tool_name, tool_input)

        # Compare
        passed = (actual == expected)

        result = {
            'eval_id': eval_id,
            'test_id': test_id,
            'description': description,
            'command': command,
            'expected': expected,
            'actual': actual,
            'rule_matched': rule_name,
            'passed': passed
        }

        if passed:
            self.passed += 1
            self.log(f"    PASS: {actual}")
        else:
            self.failed += 1
            self.log(f"    FAIL: expected {expected}, got {actual}")

        return result

    def run_eval_file(self, yaml_path: Path) -> List[Dict]:
        """Run all test cases in an eval YAML file."""
        results = []

        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                eval_data = yaml.safe_load(f)
        except Exception as e:
            print(f"  Error loading {yaml_path}: {e}")
            return results

        eval_id = eval_data.get('id', yaml_path.stem)
        eval_name = eval_data.get('name', eval_id)
        test_cases = eval_data.get('test_cases', [])

        print(f"\n[{eval_name}] ({len(test_cases)} cases)")

        for test_case in test_cases:
            result = self.run_test_case(eval_id, test_case)
            results.append(result)

        return results

    def run_all(self) -> bool:
        """Run all enforcement evals.

        Returns True if all passed.
        """
        print("=" * 60)
        print("ENFORCEMENT EVAL RUNNER")
        print("=" * 60)

        # Verify hook exists
        if not HOOK_PATH.exists():
            print(f"ERROR: Hook not found at {HOOK_PATH}")
            return False

        # Find all enforcement yaml files
        yaml_files = sorted(ENFORCEMENT_DIR.glob('*.yaml'))

        if not yaml_files:
            print(f"No eval files found in {ENFORCEMENT_DIR}")
            return False

        print(f"Found {len(yaml_files)} enforcement evals")

        # Run each eval
        for yaml_path in yaml_files:
            results = self.run_eval_file(yaml_path)
            self.results.extend(results)

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        total = self.passed + self.failed + self.skipped
        print(f"  Total:   {total}")
        print(f"  Passed:  {self.passed}")
        print(f"  Failed:  {self.failed}")
        print(f"  Skipped: {self.skipped}")

        # Save results
        self.save_results()

        if self.failed > 0:
            print(f"\nFAILED TESTS:")
            for r in self.results:
                if not r.get('passed', True) and r.get('status') != 'skipped':
                    print(f"  - {r['eval_id']}/{r['test_id']}: expected {r['expected']}, got {r['actual']}")

        return self.failed == 0

    def save_results(self) -> None:
        """Save results to JSON file."""
        output = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total': self.passed + self.failed + self.skipped,
                'passed': self.passed,
                'failed': self.failed,
                'skipped': self.skipped
            },
            'results': self.results
        }

        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        print(f"\nResults saved to: {RESULTS_FILE}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Run enforcement evals')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--ci', action='store_true', help='CI mode (exit 1 on failure)')
    args = parser.parse_args()

    runner = EnforcementRunner(verbose=args.verbose)
    success = runner.run_all()

    if args.ci and not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
