"""
Tests for accessibility_verifier skill.

Tests cover:
- Color contrast calculations
- Contrast checking (AA/AAA)
- HTML parsing (alt text, headings, ARIA)
- CSS parsing (font sizes, focus indicators)
- JSX parsing (onClick, tabIndex)
- Touch target sizing
- Edge cases
"""

import pytest
import sys
from pathlib import Path

# Add skills to path
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "verification"))

from accessibility_verifier import (
    run,
    calculate_contrast_ratio,
    check_contrast,
    hex_to_rgb,
    rgb_to_luminance,
    suggest_accessible_color,
    analyze_html,
    analyze_css,
    analyze_jsx,
    A11yFinding,
    Severity,
    DEFAULT_CONFIG,
    CONTRAST_REQUIREMENTS,
    SKILL_META,
)


class TestSkillMetadata:
    """Test skill metadata is properly defined."""

    def test_has_required_fields(self):
        assert "name" in SKILL_META
        assert "description" in SKILL_META
        assert "tier" in SKILL_META
        assert "version" in SKILL_META

    def test_name_matches(self):
        assert SKILL_META["name"] == "accessibility_verifier"


class TestColorConversion:
    """Test color conversion utilities."""

    def test_hex_to_rgb_full(self):
        assert hex_to_rgb("#ffffff") == (255, 255, 255)
        assert hex_to_rgb("#000000") == (0, 0, 0)
        assert hex_to_rgb("#ff0000") == (255, 0, 0)

    def test_hex_to_rgb_shorthand(self):
        assert hex_to_rgb("#fff") == (255, 255, 255)
        assert hex_to_rgb("#000") == (0, 0, 0)
        assert hex_to_rgb("#f00") == (255, 0, 0)

    def test_hex_to_rgb_no_hash(self):
        assert hex_to_rgb("ffffff") == (255, 255, 255)

    def test_hex_to_rgb_invalid(self):
        with pytest.raises(ValueError):
            hex_to_rgb("#gg0000")


class TestLuminance:
    """Test luminance calculations."""

    def test_white_luminance(self):
        lum = rgb_to_luminance(255, 255, 255)
        assert abs(lum - 1.0) < 0.01

    def test_black_luminance(self):
        lum = rgb_to_luminance(0, 0, 0)
        assert abs(lum - 0.0) < 0.01

    def test_gray_luminance(self):
        lum = rgb_to_luminance(128, 128, 128)
        assert 0.2 < lum < 0.3  # Mid-gray


class TestContrastRatio:
    """Test contrast ratio calculations."""

    def test_black_on_white(self):
        ratio = calculate_contrast_ratio("#000000", "#ffffff")
        assert abs(ratio - 21.0) < 0.1  # Maximum contrast

    def test_white_on_black(self):
        ratio = calculate_contrast_ratio("#ffffff", "#000000")
        assert abs(ratio - 21.0) < 0.1  # Order shouldn't matter

    def test_same_color(self):
        ratio = calculate_contrast_ratio("#666666", "#666666")
        assert abs(ratio - 1.0) < 0.01  # No contrast

    def test_low_contrast(self):
        ratio = calculate_contrast_ratio("#777777", "#999999")
        assert ratio < 3.0  # Low contrast


class TestContrastChecking:
    """Test WCAG contrast checking."""

    def test_contrast_pass_aa(self):
        # Black on white should pass
        passes, ratio, required = check_contrast("#000000", "#ffffff", False, "AA")
        assert passes is True
        assert ratio >= 4.5

    def test_contrast_fail_aa(self):
        # Light gray on white should fail
        passes, ratio, required = check_contrast("#999999", "#ffffff", False, "AA")
        assert passes is False
        assert required == 4.5

    def test_contrast_pass_aaa(self):
        # Black on white should pass AAA
        passes, ratio, required = check_contrast("#000000", "#ffffff", False, "AAA")
        assert passes is True
        assert required == 7.0

    def test_contrast_large_text_aa(self):
        # Large text has lower requirement (3:1)
        passes, ratio, required = check_contrast("#767676", "#ffffff", True, "AA")
        assert required == 3.0
        # #767676 on white is about 4.5:1, should pass for large text
        assert passes is True


class TestColorSuggestion:
    """Test accessible color suggestions."""

    def test_suggest_darker(self):
        suggestion = suggest_accessible_color("#999999", "#ffffff", 4.5)
        assert suggestion is not None
        assert suggestion.startswith("#")

    def test_suggested_color_passes(self):
        suggestion = suggest_accessible_color("#999999", "#ffffff", 4.5)
        if suggestion:
            passes, _, _ = check_contrast(suggestion, "#ffffff", False, "AA")
            assert passes is True


class TestHTMLAnalysis:
    """Test HTML accessibility analysis."""

    def test_alt_text_present(self):
        html = '<img src="photo.jpg" alt="A photo">'
        findings = analyze_html(html, "test.html", DEFAULT_CONFIG)
        alt_findings = [f for f in findings if f.rule_id == "missing_alt_text"]
        assert len(alt_findings) == 0

    def test_alt_text_missing(self):
        html = '<img src="photo.jpg">'
        findings = analyze_html(html, "test.html", DEFAULT_CONFIG)
        alt_findings = [f for f in findings if f.rule_id == "missing_alt_text"]
        assert len(alt_findings) == 1

    def test_alt_text_empty_decorative(self):
        html = '<img src="decoration.jpg" alt="">'
        findings = analyze_html(html, "test.html", DEFAULT_CONFIG)
        alt_findings = [f for f in findings if f.rule_id == "empty_alt_text"]
        assert len(alt_findings) == 1
        assert alt_findings[0].severity == Severity.INFO

    def test_heading_order_valid(self):
        html = '<h1>Title</h1><h2>Section</h2><h3>Subsection</h3>'
        findings = analyze_html(html, "test.html", DEFAULT_CONFIG)
        skip_findings = [f for f in findings if f.rule_id == "heading_skip"]
        assert len(skip_findings) == 0

    def test_heading_order_skip(self):
        html = '<h1>Title</h1><h3>Skipped h2</h3>'
        findings = analyze_html(html, "test.html", DEFAULT_CONFIG)
        skip_findings = [f for f in findings if f.rule_id == "heading_skip"]
        assert len(skip_findings) == 1

    def test_invalid_aria_role(self):
        html = '<div role="foobar">Content</div>'
        findings = analyze_html(html, "test.html", DEFAULT_CONFIG)
        aria_findings = [f for f in findings if f.rule_id == "invalid_aria_role"]
        assert len(aria_findings) == 1

    def test_valid_aria_role(self):
        html = '<div role="button">Click me</div>'
        findings = analyze_html(html, "test.html", DEFAULT_CONFIG)
        aria_findings = [f for f in findings if f.rule_id == "invalid_aria_role"]
        assert len(aria_findings) == 0

    def test_small_touch_target(self):
        html = '<button style="width: 30px; height: 30px">X</button>'
        findings = analyze_html(html, "test.html", DEFAULT_CONFIG)
        touch_findings = [f for f in findings if f.rule_id == "small_touch_target"]
        assert len(touch_findings) >= 1


class TestCSSAnalysis:
    """Test CSS accessibility analysis."""

    def test_font_size_pass(self):
        css = 'body { font-size: 16px; }'
        findings = analyze_css(css, "test.css", DEFAULT_CONFIG)
        size_findings = [f for f in findings if f.rule_id == "small_font_size"]
        assert len(size_findings) == 0

    def test_font_size_fail(self):
        css = '.tiny { font-size: 8px; }'
        findings = analyze_css(css, "test.css", DEFAULT_CONFIG)
        size_findings = [f for f in findings if f.rule_id == "small_font_size"]
        assert len(size_findings) == 1

    def test_focus_outline_removed(self):
        css = 'button { outline: none; }'
        findings = analyze_css(css, "test.css", DEFAULT_CONFIG)
        focus_findings = [f for f in findings if f.rule_id == "focus_outline_removed"]
        assert len(focus_findings) == 1

    def test_focus_outline_with_custom_focus(self):
        css = '''
        button { outline: none; }
        button:focus { box-shadow: 0 0 3px blue; }
        '''
        findings = analyze_css(css, "test.css", DEFAULT_CONFIG)
        focus_findings = [f for f in findings if f.rule_id == "focus_outline_removed"]
        assert len(focus_findings) == 0


class TestJSXAnalysis:
    """Test JSX/React accessibility analysis."""

    def test_img_with_alt(self):
        jsx = '<img src="photo.jpg" alt="A photo" />'
        findings = analyze_jsx(jsx, "test.tsx", DEFAULT_CONFIG)
        alt_findings = [f for f in findings if f.rule_id == "missing_alt_text"]
        assert len(alt_findings) == 0

    def test_img_without_alt(self):
        jsx = '<img src="photo.jpg" />'
        findings = analyze_jsx(jsx, "test.tsx", DEFAULT_CONFIG)
        alt_findings = [f for f in findings if f.rule_id == "missing_alt_text"]
        assert len(alt_findings) == 1

    def test_onclick_on_button(self):
        jsx = '<button onClick={handleClick}>Click</button>'
        findings = analyze_jsx(jsx, "test.tsx", DEFAULT_CONFIG)
        click_findings = [f for f in findings if f.rule_id == "click_without_keyboard"]
        assert len(click_findings) == 0  # button handles keyboard

    def test_onclick_on_div_without_keyboard(self):
        jsx = '<div onClick={handleClick}>Click me</div>'
        findings = analyze_jsx(jsx, "test.tsx", DEFAULT_CONFIG)
        click_findings = [f for f in findings if f.rule_id == "click_without_keyboard"]
        assert len(click_findings) == 1

    def test_onclick_with_onkeydown(self):
        jsx = '<div onClick={handleClick} onKeyDown={handleKey}>Click me</div>'
        findings = analyze_jsx(jsx, "test.tsx", DEFAULT_CONFIG)
        click_findings = [f for f in findings if f.rule_id == "click_without_keyboard"]
        assert len(click_findings) == 0

    def test_positive_tabindex(self):
        jsx = '<div tabIndex={5}>Focused</div>'
        findings = analyze_jsx(jsx, "test.tsx", DEFAULT_CONFIG)
        tab_findings = [f for f in findings if f.rule_id == "positive_tabindex"]
        assert len(tab_findings) == 1

    def test_zero_tabindex(self):
        jsx = '<div tabIndex={0}>Focused</div>'
        findings = analyze_jsx(jsx, "test.tsx", DEFAULT_CONFIG)
        tab_findings = [f for f in findings if f.rule_id == "positive_tabindex"]
        assert len(tab_findings) == 0


class TestRunFunction:
    """Test the main run() function."""

    def test_run_html_pass(self):
        html = '<html><body><img src="x.jpg" alt="photo"><h1>Title</h1></body></html>'
        mock_tools = {"read_file": lambda p: html}

        result = run(
            {"files": ["test.html"]},
            mock_tools,
            {}
        )

        assert result["success"] is True
        assert result["wcag_level"] == "AA"
        assert "summary" in result

    def test_run_with_direct_colors(self):
        mock_tools = {}

        result = run(
            {
                "colors": [
                    {"foreground": "#999999", "background": "#ffffff"},
                ]
            },
            mock_tools,
            {}
        )

        assert result["success"] is True
        # Should have contrast finding
        contrast_findings = [f for f in result["findings"] if f["rule_id"] == "color_contrast"]
        assert len(contrast_findings) >= 1

    def test_run_passing_colors(self):
        mock_tools = {}

        result = run(
            {
                "colors": [
                    {"foreground": "#000000", "background": "#ffffff"},
                ]
            },
            mock_tools,
            {}
        )

        assert result["success"] is True
        assert result["passed"] is True

    def test_run_css_analysis(self):
        css = '.small { font-size: 8px; }'
        mock_tools = {"read_file": lambda p: css}

        result = run(
            {"files": ["test.css"]},
            mock_tools,
            {}
        )

        assert result["success"] is True
        assert result["files_analyzed"] == 1

    def test_run_with_config_override(self):
        css = '.normal { font-size: 10px; }'
        mock_tools = {"read_file": lambda p: css}

        result = run(
            {
                "files": ["test.css"],
                "config": {"min_font_size": 8}  # Lower threshold
            },
            mock_tools,
            {}
        )

        # 10px should pass with 8px minimum
        size_findings = [f for f in result["findings"] if f["rule_id"] == "small_font_size"]
        assert len(size_findings) == 0


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_html(self):
        findings = analyze_html("", "test.html", DEFAULT_CONFIG)
        assert isinstance(findings, list)

    def test_malformed_html(self):
        html = '<div><img src="x.jpg"'  # Unclosed
        findings = analyze_html(html, "test.html", DEFAULT_CONFIG)
        # Should handle gracefully
        assert isinstance(findings, list)

    def test_invalid_color(self):
        ratio = calculate_contrast_ratio("invalid", "#ffffff")
        assert ratio == 0.0

    def test_file_read_error(self):
        def failing_read(p):
            raise IOError("File not found")

        result = run(
            {"files": ["missing.html"]},
            {"read_file": failing_read},
            {}
        )

        assert result["success"] is True  # Skill succeeded, file failed
        error_findings = [f for f in result["findings"] if f["rule_id"] == "read_error"]
        assert len(error_findings) >= 1


class TestWCAGCriteria:
    """Test WCAG criteria mapping."""

    def test_contrast_criterion(self):
        result = run(
            {
                "colors": [
                    {"foreground": "#999999", "background": "#ffffff"},
                ]
            },
            {},
            {}
        )

        finding = result["findings"][0]
        assert finding["wcag_criterion"] == "1.4.3"

    def test_alt_text_criterion(self):
        html = '<img src="x.jpg">'
        findings = analyze_html(html, "test.html", DEFAULT_CONFIG)
        assert findings[0].wcag_criterion == "1.1.1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
