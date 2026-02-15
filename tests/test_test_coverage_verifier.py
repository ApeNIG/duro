"""
Tests for test_coverage_verifier skill.

Tests cover:
- Cobertura XML parsing
- LCOV format parsing
- JSON format parsing
- Threshold checking (pass/fail)
- Exclusion patterns
- Uncovered file ranking
- Regression detection
- Edge cases (empty, malformed)
"""

import pytest
import sys
from pathlib import Path

# Add skills to path
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "verification"))

from test_coverage_verifier import (
    run,
    parse_cobertura,
    parse_lcov,
    parse_json,
    detect_format,
    check_thresholds,
    check_regression,
    filter_files,
    CoverageFormat,
    FileCoverage,
    CoverageMetrics,
    DEFAULT_CONFIG,
    SKILL_META,
)


# === TEST FIXTURES ===

COBERTURA_XML = '''<?xml version="1.0" ?>
<coverage version="5.5" timestamp="1234567890" lines-valid="100" lines-covered="85" line-rate="0.85" branches-valid="20" branches-covered="16" branch-rate="0.80">
    <packages>
        <package name="src">
            <classes>
                <class name="main.py" filename="src/main.py" line-rate="0.90" branch-rate="0.80">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="1"/>
                        <line number="4" hits="1"/>
                        <line number="5" hits="1"/>
                        <line number="6" hits="1"/>
                        <line number="7" hits="1"/>
                        <line number="8" hits="1"/>
                        <line number="9" hits="1"/>
                        <line number="10" hits="0"/>
                    </lines>
                </class>
                <class name="utils.py" filename="src/utils.py" line-rate="0.70" branch-rate="0.60">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="1"/>
                        <line number="4" hits="1"/>
                        <line number="5" hits="1"/>
                        <line number="6" hits="1"/>
                        <line number="7" hits="1"/>
                        <line number="8" hits="0"/>
                        <line number="9" hits="0"/>
                        <line number="10" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>
'''

LCOV_CONTENT = '''TN:
SF:src/main.py
DA:1,1
DA:2,1
DA:3,1
DA:4,1
DA:5,0
FNF:2
FNH:2
LF:5
LH:4
end_of_record
SF:src/utils.py
DA:1,1
DA:2,1
DA:3,0
DA:4,0
FNF:1
FNH:1
LF:4
LH:2
end_of_record
'''

JSON_CONTENT = '''{
    "meta": {
        "version": "5.5"
    },
    "files": {
        "src/main.py": {
            "summary": {
                "covered_lines": 9,
                "num_statements": 10,
                "percent_covered": 90.0
            },
            "missing_lines": [10]
        },
        "src/utils.py": {
            "summary": {
                "covered_lines": 7,
                "num_statements": 10,
                "percent_covered": 70.0
            },
            "missing_lines": [8, 9, 10]
        }
    },
    "totals": {
        "percent_covered": 80.0
    }
}
'''


class TestSkillMetadata:
    """Test skill metadata is properly defined."""

    def test_has_required_fields(self):
        assert "name" in SKILL_META
        assert "description" in SKILL_META
        assert "tier" in SKILL_META
        assert "version" in SKILL_META

    def test_name_matches(self):
        assert SKILL_META["name"] == "test_coverage_verifier"


class TestFormatDetection:
    """Test coverage format detection."""

    def test_detect_cobertura(self):
        fmt = detect_format(COBERTURA_XML, "coverage.xml")
        assert fmt == CoverageFormat.COBERTURA

    def test_detect_lcov(self):
        fmt = detect_format(LCOV_CONTENT, "coverage.lcov")
        assert fmt == CoverageFormat.LCOV

    def test_detect_lcov_by_content(self):
        fmt = detect_format(LCOV_CONTENT, "report.txt")
        assert fmt == CoverageFormat.LCOV

    def test_detect_json(self):
        fmt = detect_format(JSON_CONTENT, "coverage.json")
        assert fmt == CoverageFormat.JSON

    def test_detect_json_by_content(self):
        fmt = detect_format(JSON_CONTENT, "report.txt")
        assert fmt == CoverageFormat.JSON


class TestCoberturaParser:
    """Test Cobertura XML parsing."""

    def test_parse_files(self):
        files, metrics = parse_cobertura(COBERTURA_XML)
        assert len(files) == 2
        assert files[0].path == "src/main.py"
        assert files[1].path == "src/utils.py"

    def test_parse_line_coverage(self):
        files, metrics = parse_cobertura(COBERTURA_XML)
        main_file = next(f for f in files if "main" in f.path)
        assert main_file.line_coverage == 90.0
        assert main_file.lines_covered == 9
        assert main_file.lines_total == 10

    def test_parse_uncovered_lines(self):
        files, metrics = parse_cobertura(COBERTURA_XML)
        main_file = next(f for f in files if "main" in f.path)
        assert 10 in main_file.uncovered_lines

    def test_aggregate_metrics(self):
        files, metrics = parse_cobertura(COBERTURA_XML)
        assert metrics.line_coverage == 80.0  # 16/20 lines
        assert metrics.files_total == 2


class TestLcovParser:
    """Test LCOV format parsing."""

    def test_parse_files(self):
        files, metrics = parse_lcov(LCOV_CONTENT)
        assert len(files) == 2

    def test_parse_line_coverage(self):
        files, metrics = parse_lcov(LCOV_CONTENT)
        main_file = next(f for f in files if "main" in f.path)
        assert main_file.line_coverage == 80.0  # 4/5 lines
        assert main_file.lines_covered == 4
        assert main_file.lines_total == 5

    def test_parse_function_coverage(self):
        files, metrics = parse_lcov(LCOV_CONTENT)
        main_file = next(f for f in files if "main" in f.path)
        assert main_file.function_coverage == 100.0  # 2/2 functions


class TestJsonParser:
    """Test JSON format parsing."""

    def test_parse_files(self):
        files, metrics = parse_json(JSON_CONTENT)
        assert len(files) == 2

    def test_parse_line_coverage(self):
        files, metrics = parse_json(JSON_CONTENT)
        main_file = next(f for f in files if "main" in f.path)
        assert main_file.line_coverage == 90.0

    def test_parse_missing_lines(self):
        files, metrics = parse_json(JSON_CONTENT)
        utils_file = next(f for f in files if "utils" in f.path)
        assert 8 in utils_file.uncovered_lines

    def test_aggregate_coverage(self):
        files, metrics = parse_json(JSON_CONTENT)
        assert metrics.line_coverage == 80.0


class TestThresholdChecking:
    """Test threshold enforcement."""

    def test_threshold_pass(self):
        metrics = CoverageMetrics(
            line_coverage=85.0,
            branch_coverage=75.0,
            function_coverage=90.0,
            files_covered=10,
            files_total=10,
            lines_covered=850,
            lines_total=1000,
            branches_covered=75,
            branches_total=100,
            functions_covered=90,
            functions_total=100,
        )
        config = {
            "min_line_coverage": 80.0,
            "min_branch_coverage": 70.0,
            "min_function_coverage": 80.0,
        }
        failures = check_thresholds(metrics, config)
        assert len(failures) == 0

    def test_threshold_fail_line(self):
        metrics = CoverageMetrics(
            line_coverage=75.0,
            branch_coverage=80.0,
            function_coverage=90.0,
            files_covered=10,
            files_total=10,
            lines_covered=750,
            lines_total=1000,
            branches_covered=80,
            branches_total=100,
            functions_covered=90,
            functions_total=100,
        )
        config = {"min_line_coverage": 80.0}
        failures = check_thresholds(metrics, config)
        assert len(failures) == 1
        assert failures[0].metric == "line_coverage"
        assert failures[0].gap == 5.0

    def test_threshold_fail_multiple(self):
        metrics = CoverageMetrics(
            line_coverage=70.0,
            branch_coverage=60.0,
            function_coverage=70.0,
            files_covered=10,
            files_total=10,
            lines_covered=700,
            lines_total=1000,
            branches_covered=60,
            branches_total=100,
            functions_covered=70,
            functions_total=100,
        )
        config = {
            "min_line_coverage": 80.0,
            "min_branch_coverage": 70.0,
            "min_function_coverage": 80.0,
        }
        failures = check_thresholds(metrics, config)
        assert len(failures) == 3


class TestExclusionPatterns:
    """Test file exclusion."""

    def test_exclude_test_files(self):
        files = [
            FileCoverage(path="src/main.py", line_coverage=90, branch_coverage=None,
                        function_coverage=None, lines_covered=9, lines_total=10),
            FileCoverage(path="tests/test_main.py", line_coverage=100, branch_coverage=None,
                        function_coverage=None, lines_covered=10, lines_total=10),
        ]
        filtered = filter_files(files, ["**/test_*.py"])
        assert len(filtered) == 1
        assert "test_main" not in filtered[0].path

    def test_exclude_migrations(self):
        files = [
            FileCoverage(path="src/main.py", line_coverage=90, branch_coverage=None,
                        function_coverage=None, lines_covered=9, lines_total=10),
            FileCoverage(path="migrations/001_init.py", line_coverage=50, branch_coverage=None,
                        function_coverage=None, lines_covered=5, lines_total=10),
        ]
        filtered = filter_files(files, ["**/migrations/**"])
        assert len(filtered) == 1


class TestRegressionDetection:
    """Test coverage regression detection."""

    def test_no_regression(self):
        regression = check_regression(current=85.0, baseline=84.0, threshold=2.0)
        assert regression.detected is False
        assert regression.delta == 1.0

    def test_regression_detected(self):
        regression = check_regression(current=80.0, baseline=85.0, threshold=2.0)
        assert regression.detected is True
        assert regression.delta == -5.0

    def test_within_threshold(self):
        regression = check_regression(current=83.0, baseline=85.0, threshold=2.0)
        assert regression.detected is False  # 2% drop is within threshold

    def test_no_baseline(self):
        regression = check_regression(current=85.0, baseline=None, threshold=2.0)
        assert regression.detected is False
        assert regression.baseline is None


class TestRunFunction:
    """Test the main run() function."""

    def test_run_cobertura_pass(self):
        mock_tools = {
            "read_file": lambda p: COBERTURA_XML,
        }
        result = run(
            {
                "report_path": "coverage.xml",
                "config": {"min_line_coverage": 75.0}
            },
            mock_tools,
            {}
        )
        assert result["success"] is True
        assert result["passed"] is True
        assert result["format"] == "cobertura"
        assert result["metrics"]["line_coverage"] == 80.0

    def test_run_threshold_fail(self):
        mock_tools = {
            "read_file": lambda p: COBERTURA_XML,
        }
        result = run(
            {
                "report_path": "coverage.xml",
                "config": {"min_line_coverage": 90.0}
            },
            mock_tools,
            {}
        )
        assert result["success"] is True
        assert result["passed"] is False
        assert len(result["failures"]) >= 1

    def test_run_with_baseline_regression(self):
        mock_tools = {
            "read_file": lambda p: COBERTURA_XML,
        }
        result = run(
            {
                "report_path": "coverage.xml",
                "baseline": 85.0,
                "config": {"min_line_coverage": 75.0, "regression_threshold": 2.0}
            },
            mock_tools,
            {}
        )
        assert result["regression"]["detected"] is True
        assert result["passed"] is False

    def test_run_lcov(self):
        mock_tools = {
            "read_file": lambda p: LCOV_CONTENT,
        }
        result = run(
            {
                "report_path": "coverage.lcov",
                "config": {"min_line_coverage": 50.0}
            },
            mock_tools,
            {}
        )
        assert result["success"] is True
        assert result["format"] == "lcov"

    def test_run_json(self):
        mock_tools = {
            "read_file": lambda p: JSON_CONTENT,
        }
        result = run(
            {
                "report_path": "coverage.json",
                "config": {"min_line_coverage": 75.0}
            },
            mock_tools,
            {}
        )
        assert result["success"] is True
        assert result["format"] == "json"


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_report(self):
        mock_tools = {
            "read_file": lambda p: "",
        }
        result = run({"report_path": "coverage.xml"}, mock_tools, {})
        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_malformed_xml(self):
        mock_tools = {
            "read_file": lambda p: "<coverage><broken>",
        }
        result = run({"report_path": "coverage.xml"}, mock_tools, {})
        assert result["success"] is False

    def test_file_not_found(self):
        mock_tools = {
            "read_file": lambda p: (_ for _ in ()).throw(FileNotFoundError("not found")),
        }
        result = run({"report_path": "missing.xml"}, mock_tools, {})
        assert result["success"] is False

    def test_zero_lines(self):
        xml = '''<?xml version="1.0" ?>
<coverage>
    <packages>
        <package name="empty">
            <classes>
                <class name="empty.py" filename="empty.py">
                    <lines></lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>
'''
        mock_tools = {"read_file": lambda p: xml}
        result = run({"report_path": "coverage.xml"}, mock_tools, {})
        assert result["success"] is True
        # Should handle gracefully with 0% or N/A


class TestUncoveredRanking:
    """Test uncovered file identification."""

    def test_uncovered_sorted_by_coverage(self):
        mock_tools = {
            "read_file": lambda p: COBERTURA_XML,
        }
        result = run(
            {
                "report_path": "coverage.xml",
                "config": {"report_uncovered_limit": 5}
            },
            mock_tools,
            {}
        )
        uncovered = result["uncovered"]
        assert len(uncovered) <= 5
        # Should be sorted ascending by coverage
        if len(uncovered) >= 2:
            assert uncovered[0]["line_coverage"] <= uncovered[1]["line_coverage"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
