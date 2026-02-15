"""
Test: design_to_code_verifier skill
Run: python test_design_to_code_verifier.py
"""

import os
import sys

# Add parent to path for import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from design_to_code_verifier import (
    normalize_color,
    normalize_spacing,
    colors_match,
    extract_design_tokens,
    scan_code_for_tokens,
    compare_tokens,
    TokenType,
    DriftSeverity
)


def test_normalize_color():
    """Test color normalization."""
    # Hex colors
    assert normalize_color("#8B5CF6") == "#8b5cf6", "Lowercase hex"
    assert normalize_color("#fff") == "#ffffff", "Expand shorthand"

    # CSS variables
    assert normalize_color("var(--color-primary)") == "var(--color-primary)", "CSS var"

    # Pencil variables
    assert normalize_color("$--primary") == "$--primary", "Pencil var"

    # RGB
    assert normalize_color("rgb(139, 92, 246)") == "#8b5cf6", "RGB to hex"

    print("PASS: test_normalize_color")


def test_normalize_spacing():
    """Test spacing normalization."""
    assert normalize_spacing(16) == [16, 16, 16, 16], "Single value"
    assert normalize_spacing([16, 24]) == [16, 24, 16, 24], "Two values"
    assert normalize_spacing([12, 24, 12, 24]) == [12, 24, 12, 24], "Four values"

    print("PASS: test_normalize_spacing")


def test_colors_match():
    """Test color matching."""
    # Direct match
    assert colors_match("#8B5CF6", "#8b5cf6"), "Case insensitive hex"

    # Variable mapping
    assert colors_match("$--primary", "var(--color-primary)"), "Variable mapping"

    # Non-match
    assert not colors_match("#8B5CF6", "#14B8A6"), "Different colors"

    print("PASS: test_colors_match")


def test_extract_design_tokens():
    """Test design token extraction."""
    node = {
        "id": "btn1",
        "name": "Button/Primary",
        "type": "frame",
        "fill": "#8B5CF6",
        "padding": [12, 24],
        "cornerRadius": 8,
        "children": [
            {
                "id": "label",
                "name": "label",
                "type": "text",
                "fill": "#FFFFFF",
                "fontSize": 14,
                "fontFamily": "Inter",
                "fontWeight": "500"
            }
        ]
    }

    tokens = extract_design_tokens(node)

    # Should have tokens for: fill, padding, cornerRadius, text fill, fontSize, fontFamily, fontWeight
    assert len(tokens) >= 6, f"Expected at least 6 tokens, got {len(tokens)}"

    # Check specific tokens
    token_types = [t.token_type for t in tokens]
    assert TokenType.COLOR in token_types, "Should have color token"
    assert TokenType.PADDING in token_types, "Should have padding token"
    assert TokenType.BORDER_RADIUS in token_types, "Should have border radius token"
    assert TokenType.FONT_SIZE in token_types, "Should have font size token"

    print("PASS: test_extract_design_tokens")


def test_scan_code_for_tokens():
    """Test code scanning."""
    code = '''
    export function Button() {
      return (
        <button className="bg-[#8B5CF6] text-white px-6 py-3 rounded-[8px] text-[14px] font-medium">
          Click me
        </button>
      );
    }
    '''

    tokens = scan_code_for_tokens(code, "Button.tsx")

    assert len(tokens) > 0, "Should find tokens"

    # Check for specific patterns
    token_values = [t.value for t in tokens]
    assert any("#8B5CF6" in v for v in token_values), "Should find hex color"
    assert any("rounded-[8px]" in v for v in token_values), "Should find border radius"

    print("PASS: test_scan_code_for_tokens")


def test_compare_tokens():
    """Test token comparison and drift detection."""
    design_tokens = [
        type('DesignToken', (), {
            'token_type': TokenType.COLOR,
            'value': '#8B5CF6',
            'node_id': 'btn1',
            'node_name': 'Button',
            'path': 'Button/Primary'
        })(),
        type('DesignToken', (), {
            'token_type': TokenType.FONT_SIZE,
            'value': 14,
            'node_id': 'label',
            'node_name': 'label',
            'path': 'Button/Primary/label'
        })(),
    ]

    # Matching code tokens
    code_tokens = [
        type('CodeToken', (), {
            'token_type': TokenType.COLOR,
            'value': '#8b5cf6',
            'file_path': 'Button.tsx',
            'line_number': 5,
            'context': 'bg-[#8b5cf6]'
        })(),
        type('CodeToken', (), {
            'token_type': TokenType.FONT_SIZE,
            'value': 'text-[14px]',
            'file_path': 'Button.tsx',
            'line_number': 5,
            'context': 'text-[14px]'
        })(),
    ]

    drifts = compare_tokens(design_tokens, code_tokens, "Button")

    # Colors should match, so no drift for colors
    color_drifts = [d for d in drifts if d.token_type == TokenType.COLOR]
    assert len(color_drifts) == 0, f"Expected no color drift, got {len(color_drifts)}"

    print("PASS: test_compare_tokens")


def test_severity_levels():
    """Test drift severity classification."""
    assert DriftSeverity.CRITICAL.value == "critical"
    assert DriftSeverity.ERROR.value == "error"
    assert DriftSeverity.WARNING.value == "warning"
    assert DriftSeverity.INFO.value == "info"

    print("PASS: test_severity_levels")


if __name__ == "__main__":
    print("Testing design_to_code_verifier skill...")
    print("-" * 40)

    try:
        test_normalize_color()
        test_normalize_spacing()
        test_colors_match()
        test_extract_design_tokens()
        test_scan_code_for_tokens()
        test_compare_tokens()
        test_severity_levels()
        print("-" * 40)
        print("ALL TESTS PASSED")
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
