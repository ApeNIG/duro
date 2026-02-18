"""
Dual Direction Design Skill
===========================

Implements the autonomous design workflow:
1. Create TWO distinct design directions in Pencil
2. Self-evaluate using structured criteria
3. Blend best elements into final design
4. Return decision for implementation

This skill doesn't require user approval during mockup phase.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum

class DesignCriterion(Enum):
    VISUAL_CLARITY = "visual_clarity"
    HIERARCHY = "hierarchy"
    USER_FLOW = "user_flow"
    BRAND_ALIGNMENT = "brand_alignment"
    TECHNICAL_FEASIBILITY = "technical_feasibility"
    CONSISTENCY = "consistency"
    ACCESSIBILITY = "accessibility"
    MOBILE_RESPONSIVENESS = "mobile_responsiveness"

@dataclass
class DesignDirection:
    """Represents a single design direction"""
    name: str
    description: str
    pen_file: str
    screen_ids: List[str]
    style_approach: str  # e.g., "minimal", "bold", "playful", "corporate"
    key_characteristics: List[str]

@dataclass
class DesignEvaluation:
    """Evaluation of a design direction"""
    direction: DesignDirection
    scores: Dict[DesignCriterion, int]  # 1-5 scale
    strengths: List[str]
    weaknesses: List[str]
    total_score: int

@dataclass
class DesignDecision:
    """Final design decision after evaluation"""
    winner: str  # "direction_a", "direction_b", or "blend"
    blend_elements: Dict[str, str]  # Which elements from which direction
    final_mockup_id: str
    rationale: str

# Evaluation weights (can be adjusted per project type)
DEFAULT_WEIGHTS = {
    DesignCriterion.VISUAL_CLARITY: 1.5,
    DesignCriterion.HIERARCHY: 1.2,
    DesignCriterion.USER_FLOW: 1.5,
    DesignCriterion.BRAND_ALIGNMENT: 1.0,
    DesignCriterion.TECHNICAL_FEASIBILITY: 1.3,
    DesignCriterion.CONSISTENCY: 1.1,
    DesignCriterion.ACCESSIBILITY: 1.0,
    DesignCriterion.MOBILE_RESPONSIVENESS: 1.2,
}

# Project type presets
PROJECT_WEIGHTS = {
    "saas_dashboard": {
        DesignCriterion.VISUAL_CLARITY: 1.8,
        DesignCriterion.HIERARCHY: 1.5,
        DesignCriterion.USER_FLOW: 1.5,
        DesignCriterion.TECHNICAL_FEASIBILITY: 1.3,
    },
    "landing_page": {
        DesignCriterion.VISUAL_CLARITY: 1.2,
        DesignCriterion.HIERARCHY: 1.3,
        DesignCriterion.BRAND_ALIGNMENT: 1.8,
        DesignCriterion.MOBILE_RESPONSIVENESS: 1.5,
    },
    "mobile_app": {
        DesignCriterion.USER_FLOW: 1.8,
        DesignCriterion.ACCESSIBILITY: 1.5,
        DesignCriterion.MOBILE_RESPONSIVENESS: 2.0,
    },
    "sports_tracker": {  # For MSJ-type apps
        DesignCriterion.VISUAL_CLARITY: 1.6,
        DesignCriterion.USER_FLOW: 1.5,
        DesignCriterion.MOBILE_RESPONSIVENESS: 1.8,
        DesignCriterion.ACCESSIBILITY: 1.2,
    },
}

def calculate_weighted_score(
    evaluation: DesignEvaluation,
    project_type: str = "default"
) -> float:
    """Calculate weighted score for a design direction"""
    weights = PROJECT_WEIGHTS.get(project_type, DEFAULT_WEIGHTS)

    total = 0.0
    weight_sum = 0.0

    for criterion, score in evaluation.scores.items():
        weight = weights.get(criterion, 1.0)
        total += score * weight
        weight_sum += weight

    return total / weight_sum if weight_sum > 0 else 0.0

def decide_winner(
    eval_a: DesignEvaluation,
    eval_b: DesignEvaluation,
    project_type: str = "default",
    blend_threshold: float = 0.15  # If scores within 15%, suggest blend
) -> DesignDecision:
    """Decide between two design directions"""
    score_a = calculate_weighted_score(eval_a, project_type)
    score_b = calculate_weighted_score(eval_b, project_type)

    diff = abs(score_a - score_b) / max(score_a, score_b)

    if diff <= blend_threshold:
        # Too close - blend the best of both
        blend_elements = {}

        # Take best elements from each
        for criterion in DesignCriterion:
            if criterion in eval_a.scores and criterion in eval_b.scores:
                if eval_a.scores[criterion] > eval_b.scores[criterion]:
                    blend_elements[criterion.value] = "direction_a"
                else:
                    blend_elements[criterion.value] = "direction_b"

        return DesignDecision(
            winner="blend",
            blend_elements=blend_elements,
            final_mockup_id="",  # To be created
            rationale=f"Scores within {blend_threshold*100}% - blending best elements from both"
        )
    elif score_a > score_b:
        return DesignDecision(
            winner="direction_a",
            blend_elements={},
            final_mockup_id=eval_a.direction.screen_ids[0] if eval_a.direction.screen_ids else "",
            rationale=f"Direction A scored {score_a:.2f} vs {score_b:.2f}"
        )
    else:
        return DesignDecision(
            winner="direction_b",
            blend_elements={},
            final_mockup_id=eval_b.direction.screen_ids[0] if eval_b.direction.screen_ids else "",
            rationale=f"Direction B scored {score_b:.2f} vs {score_a:.2f}"
        )

# Design direction templates for quick starts
DIRECTION_TEMPLATES = {
    "minimal_clean": {
        "style_approach": "minimal",
        "key_characteristics": [
            "Lots of whitespace",
            "Single accent color",
            "System fonts or clean sans-serif",
            "Subtle shadows and borders",
            "Card-based layouts",
        ],
        "color_approach": "Neutral base with single accent",
        "typography": "Clean, readable, minimal weights",
    },
    "bold_vibrant": {
        "style_approach": "bold",
        "key_characteristics": [
            "Strong color contrasts",
            "Gradient accents",
            "Bold typography",
            "Rounded corners",
            "Playful micro-interactions",
        ],
        "color_approach": "Vibrant primary with complementary accents",
        "typography": "Bold headings, varied weights",
    },
    "dark_premium": {
        "style_approach": "premium",
        "key_characteristics": [
            "Dark backgrounds",
            "Subtle gradients",
            "Gold/silver accents",
            "Thin borders",
            "Sophisticated typography",
        ],
        "color_approach": "Dark base with metallic accents",
        "typography": "Elegant, potentially serif headings",
    },
    "playful_sports": {
        "style_approach": "playful",
        "key_characteristics": [
            "Dynamic angles",
            "Athletic color palette",
            "Progress indicators",
            "Achievement badges",
            "Energy-focused imagery",
        ],
        "color_approach": "Energetic colors with good contrast",
        "typography": "Bold, impactful headings",
    },
}

def suggest_direction_pair(project_type: str) -> tuple:
    """Suggest two contrasting direction templates for a project type"""
    suggestions = {
        "saas_dashboard": ("minimal_clean", "dark_premium"),
        "landing_page": ("bold_vibrant", "minimal_clean"),
        "mobile_app": ("minimal_clean", "bold_vibrant"),
        "sports_tracker": ("playful_sports", "minimal_clean"),
        "default": ("minimal_clean", "bold_vibrant"),
    }
    return suggestions.get(project_type, suggestions["default"])

# Skill metadata for Duro
SKILL_META = {
    "name": "dual_direction_design",
    "description": "Create two design directions, evaluate, and blend into optimal solution",
    "tier": "tested",
    "version": "1.0.1",
    "author": "duro",
    "triggers": ["design", "mockup", "UI", "UX", "new screen", "new page"],
    "requires": ["mcp__pencil__*"],
    "outputs": ["DesignDecision", "final_mockup_id"],
    "validated": "2026-02-18",
    "note": "Library skill - provides functions, not run() entry point",
}
