"""
Product Visualize Skill - Pencil to Blender Pipeline (v2.0 with QA)

Extracts design specs from Pencil.dev designs and renders 3D product shots in Blender.

Workflow with QA Checkpoints:
1. Read Pencil design node with specs panel
2. [QA1] Validate design coherence - do elements form intended object?
3. Extract colors, materials, lighting specs
4. [QA2] Validate spec completeness - are all required specs present?
5. Generate Blender asset (.blend file)
6. [QA3] Auto-frame camera based on scene bounding box
7. Render with extracted settings
8. [QA4] Validate output - is subject fully visible?

Phase 3.3 - Product Visualization Pipeline with QA
"""

import os
import re
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


SKILL_META = {
    "name": "product_visualize",
    "description": "Pencil to Blender pipeline with QA checkpoints - extract design specs and render 3D product shots",
    "tier": "tested",
    "version": "2.0.0",
    "phase": "3.3",
    "keywords": [
        "pencil", "blender", "3d", "render", "product", "visualization",
        "design", "asset", "pipeline", "mug", "packaging", "qa", "validation"
    ],
    "requires_network": False,
    "timeout_seconds": 120,
    "expected_runtime_seconds": 30,
    "dependencies": ["blender"],
    "side_effects": ["writes_file", "runs_subprocess"],
}


DEFAULT_CONFIG = {
    "blender_path": r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    "output_dir": r"C:\Users\sibag\blender-output",
    "render_engine": "BLENDER_EEVEE",
    "render_width": 1280,
    "render_height": 720,
    "cycles_samples": 64,
    "timeout_seconds": 60,
    "camera_margin": 1.3,  # 30% margin around subject
    "min_render_size_kb": 10,  # Minimum valid render size
}


class QAStatus(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class QAResult:
    """Result from a QA checkpoint."""
    checkpoint: str
    status: QAStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint": self.checkpoint,
            "status": self.status.value,
            "message": self.message,
            "details": self.details
        }


@dataclass
class DesignSpecs:
    """Extracted design specifications from Pencil."""
    colors: Dict[str, Tuple[float, float, float, float]] = field(default_factory=dict)
    materials: Dict[str, Any] = field(default_factory=dict)
    lighting: Dict[str, Any] = field(default_factory=dict)
    product_name: str = "product"
    product_type: str = "generic"  # mug, house, box, etc.
    style: str = "minimal"
    dimensions: Dict[str, float] = field(default_factory=dict)  # width, height, depth

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RenderResult:
    """Result from product visualization."""
    success: bool
    asset_path: Optional[str] = None
    render_path: Optional[str] = None
    specs: Optional[DesignSpecs] = None
    error: Optional[str] = None
    blender_output: str = ""
    qa_results: List[QAResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "success": self.success,
            "asset_path": self.asset_path,
            "render_path": self.render_path,
            "error": self.error,
            "qa_results": [qa.to_dict() for qa in self.qa_results]
        }
        if self.specs:
            d["specs"] = self.specs.to_dict()
        return d

    def has_qa_failures(self) -> bool:
        return any(qa.status == QAStatus.FAIL for qa in self.qa_results)


# =============================================================================
# QA CHECKPOINT 1: Design Coherence Validation
# =============================================================================

PRODUCT_REQUIREMENTS = {
    "house": {
        "required_elements": ["walls", "roof", "door"],
        "optional_elements": ["windows", "chimney", "grass"],
        "spatial_rules": [
            ("roof", "above", "walls"),
            ("door", "on", "walls"),
            ("windows", "on", "walls"),
            ("chimney", "on", "roof"),
        ]
    },
    "mug": {
        "required_elements": ["body"],
        "optional_elements": ["handle", "contents", "lid"],
        "spatial_rules": [
            ("handle", "beside", "body"),
            ("contents", "inside", "body"),
        ]
    },
    "box": {
        "required_elements": ["body"],
        "optional_elements": ["lid", "label"],
        "spatial_rules": [
            ("lid", "above", "body"),
        ]
    },
    "generic": {
        "required_elements": [],
        "optional_elements": [],
        "spatial_rules": []
    }
}


def detect_product_type(node_data: Dict[str, Any]) -> str:
    """Detect product type from node name and children."""
    name = node_data.get("name", "").lower()

    if "house" in name or "home" in name or "cottage" in name:
        return "house"
    elif "mug" in name or "cup" in name or "coffee" in name:
        return "mug"
    elif "box" in name or "package" in name:
        return "box"

    # Check children names
    children = node_data.get("children", [])
    if isinstance(children, list):
        child_names = " ".join([
            c.get("name", "").lower() for c in children if isinstance(c, dict)
        ])
        if "roof" in child_names or "walls" in child_names:
            return "house"
        elif "handle" in child_names or "body" in child_names:
            return "mug"

    return "generic"


def qa1_design_coherence(node_data: Dict[str, Any], product_type: str) -> QAResult:
    """
    QA Checkpoint 1: Validate design elements form a coherent object.

    Checks:
    - Required elements are present
    - Elements have proper spatial relationships
    - Visual structure makes sense
    """
    requirements = PRODUCT_REQUIREMENTS.get(product_type, PRODUCT_REQUIREMENTS["generic"])
    issues = []
    warnings = []
    found_elements = set()

    children = node_data.get("children", [])
    if isinstance(children, str):
        children = []

    # Build element inventory with positions
    element_positions = {}
    for child in children:
        if not isinstance(child, dict):
            continue
        child_name = child.get("name", "").lower()

        # Track found elements
        for req_elem in requirements["required_elements"] + requirements["optional_elements"]:
            if req_elem in child_name:
                found_elements.add(req_elem)
                element_positions[req_elem] = {
                    "x": child.get("x", 0),
                    "y": child.get("y", 0),
                    "width": child.get("width", 0),
                    "height": child.get("height", 0),
                    "rotation": child.get("rotation", 0)
                }

    # Check required elements
    missing = set(requirements["required_elements"]) - found_elements
    if missing:
        issues.append(f"Missing required elements: {', '.join(missing)}")

    # Check spatial rules
    for elem1, relation, elem2 in requirements["spatial_rules"]:
        if elem1 not in element_positions or elem2 not in element_positions:
            continue

        pos1 = element_positions[elem1]
        pos2 = element_positions[elem2]

        if relation == "above":
            # elem1 should have smaller y (higher on screen) than elem2
            if pos1["y"] >= pos2["y"]:
                warnings.append(f"{elem1} should be above {elem2}")
        elif relation == "on":
            # elem1 should overlap with elem2
            overlap_x = (pos1["x"] < pos2["x"] + pos2["width"] and
                        pos1["x"] + pos1["width"] > pos2["x"])
            overlap_y = (pos1["y"] < pos2["y"] + pos2["height"] and
                        pos1["y"] + pos1["height"] > pos2["y"])
            if not (overlap_x and overlap_y):
                warnings.append(f"{elem1} should be positioned on {elem2}")

    # Special check for house roof
    if product_type == "house" and "roof" in found_elements:
        # Check if roof elements form a proper triangular shape
        roof_elements = [c for c in children if isinstance(c, dict) and "roof" in c.get("name", "").lower()]

        if len(roof_elements) == 2:
            # Two roof pieces - check if they're angled to form a peak
            rotations = [abs(r.get("rotation", 0)) for r in roof_elements]
            if not all(10 < r < 50 for r in rotations):
                warnings.append("Roof pieces may not form proper triangular shape - check rotation angles")

            # Check if they meet at a peak
            r1, r2 = roof_elements
            r1_center_x = r1.get("x", 0) + r1.get("width", 0) / 2
            r2_center_x = r2.get("x", 0) + r2.get("width", 0) / 2
            gap = abs(r1_center_x - r2_center_x)

            if gap > 200:  # Arbitrary threshold
                issues.append("Roof pieces are too far apart - they don't form a connected roof")
        elif len(roof_elements) == 1:
            # Single roof piece - check if it's a proper shape (triangle/path is valid)
            roof = roof_elements[0]
            roof_type = roof.get("type", "")
            roof_name = roof.get("name", "").lower()

            # A path or polygon with "triangle" in name is a valid single roof
            if roof_type in ["path", "polygon"] or "triangle" in roof_name:
                pass  # Valid triangular roof
            elif roof_type in ["frame", "rectangle"] and roof.get("rotation", 0) == 0:
                warnings.append("Single flat roof element - consider if this forms a complete roof shape")

    # Determine status
    if issues:
        return QAResult(
            checkpoint="QA1_DESIGN_COHERENCE",
            status=QAStatus.FAIL,
            message=f"Design coherence failed: {'; '.join(issues)}",
            details={
                "issues": issues,
                "warnings": warnings,
                "found_elements": list(found_elements),
                "product_type": product_type
            }
        )
    elif warnings:
        return QAResult(
            checkpoint="QA1_DESIGN_COHERENCE",
            status=QAStatus.WARN,
            message=f"Design has warnings: {'; '.join(warnings)}",
            details={
                "warnings": warnings,
                "found_elements": list(found_elements),
                "product_type": product_type
            }
        )
    else:
        return QAResult(
            checkpoint="QA1_DESIGN_COHERENCE",
            status=QAStatus.PASS,
            message=f"Design coherence validated for {product_type}",
            details={
                "found_elements": list(found_elements),
                "product_type": product_type
            }
        )


# =============================================================================
# QA CHECKPOINT 2: Spec Completeness Validation
# =============================================================================

def qa2_spec_completeness(specs: DesignSpecs, product_type: str) -> QAResult:
    """
    QA Checkpoint 2: Validate extracted specs are complete.

    Checks:
    - Required colors present
    - Materials have minimum properties
    - Lighting specs are usable
    """
    issues = []
    warnings = []

    # Check colors
    if not specs.colors:
        issues.append("No colors extracted from design")
    else:
        if "background" not in specs.colors:
            warnings.append("No background color - using default")

        # Product-specific color requirements
        if product_type == "house":
            house_colors = ["walls", "roof", "door"]
            missing_colors = [c for c in house_colors if not any(c in k for k in specs.colors.keys())]
            if missing_colors:
                warnings.append(f"Missing recommended colors for house: {missing_colors}")
        elif product_type == "mug":
            if not any("body" in k or "mug" in k for k in specs.colors.keys()):
                warnings.append("No body/mug color found")

    # Check materials
    if not specs.materials:
        warnings.append("No material specs - using defaults")
    elif "roughness" not in specs.materials:
        warnings.append("No roughness specified - using default 0.4")

    # Check lighting
    if not specs.lighting:
        warnings.append("No lighting specs - using default studio setup")

    # Check dimensions for proper camera framing
    if not specs.dimensions:
        warnings.append("No dimensions specified - will estimate from product type")

    # Determine status
    if issues:
        return QAResult(
            checkpoint="QA2_SPEC_COMPLETENESS",
            status=QAStatus.FAIL,
            message=f"Spec extraction failed: {'; '.join(issues)}",
            details={"issues": issues, "warnings": warnings}
        )
    elif warnings:
        return QAResult(
            checkpoint="QA2_SPEC_COMPLETENESS",
            status=QAStatus.WARN,
            message=f"Specs have gaps (using defaults): {'; '.join(warnings)}",
            details={"warnings": warnings, "colors_found": list(specs.colors.keys())}
        )
    else:
        return QAResult(
            checkpoint="QA2_SPEC_COMPLETENESS",
            status=QAStatus.PASS,
            message="All specs extracted successfully",
            details={"colors_found": list(specs.colors.keys())}
        )


# =============================================================================
# QA CHECKPOINT 3: Camera Auto-Framing (built into Blender script)
# =============================================================================

def get_product_dimensions(product_type: str, specs: DesignSpecs) -> Dict[str, float]:
    """Get estimated dimensions for camera framing based on product type."""

    # Use specs if available
    if specs.dimensions:
        return specs.dimensions

    # Default dimensions by product type (in Blender units)
    defaults = {
        "mug": {"width": 0.8, "height": 0.6, "depth": 0.8},
        "house": {"width": 2.0, "height": 2.5, "depth": 2.0},
        "box": {"width": 1.0, "height": 1.0, "depth": 1.0},
        "generic": {"width": 1.0, "height": 1.0, "depth": 1.0}
    }

    return defaults.get(product_type, defaults["generic"])


# =============================================================================
# QA CHECKPOINT 4: Output Validation
# =============================================================================

def qa4_output_validation(render_path: str, config: Dict[str, Any]) -> QAResult:
    """
    QA Checkpoint 4: Validate render output.

    Checks:
    - File exists
    - File has reasonable size (not empty/corrupted)
    - (Future: analyze image to check subject framing)
    """
    issues = []
    warnings = []

    render_file = Path(render_path)

    if not render_file.exists():
        return QAResult(
            checkpoint="QA4_OUTPUT_VALIDATION",
            status=QAStatus.FAIL,
            message="Render file was not created",
            details={"expected_path": render_path}
        )

    # Check file size
    file_size_kb = render_file.stat().st_size / 1024
    min_size = config.get("min_render_size_kb", 10)

    if file_size_kb < min_size:
        issues.append(f"Render file too small ({file_size_kb:.1f}KB) - may be corrupted")
    elif file_size_kb < 50:
        warnings.append(f"Render file is small ({file_size_kb:.1f}KB) - check quality")

    # Future: Could use PIL to analyze the image
    # - Check if subject is centered
    # - Check if subject is fully visible (not clipped)
    # - Check color distribution matches specs

    if issues:
        return QAResult(
            checkpoint="QA4_OUTPUT_VALIDATION",
            status=QAStatus.FAIL,
            message=f"Output validation failed: {'; '.join(issues)}",
            details={"file_size_kb": file_size_kb, "issues": issues}
        )
    elif warnings:
        return QAResult(
            checkpoint="QA4_OUTPUT_VALIDATION",
            status=QAStatus.WARN,
            message=f"Output has warnings: {'; '.join(warnings)}",
            details={"file_size_kb": file_size_kb, "warnings": warnings}
        )
    else:
        return QAResult(
            checkpoint="QA4_OUTPUT_VALIDATION",
            status=QAStatus.PASS,
            message=f"Render validated ({file_size_kb:.1f}KB)",
            details={"file_size_kb": file_size_kb}
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def hex_to_rgba(hex_color: str) -> Tuple[float, float, float, float]:
    """Convert hex color to RGBA tuple (0-1 range)."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        return (r, g, b, 1.0)
    return (0.5, 0.5, 0.5, 1.0)


def extract_specs_from_pencil_data(node_data: Dict[str, Any]) -> DesignSpecs:
    """Extract design specs from Pencil node data."""
    specs = DesignSpecs()

    # Detect product type
    specs.product_type = detect_product_type(node_data)

    # Extract product name from node name
    if "name" in node_data:
        specs.product_name = node_data["name"].lower().replace(" ", "_")

    children = node_data.get("children", [])
    if isinstance(children, str):
        children = []

    for child in children:
        if not isinstance(child, dict):
            continue

        child_name = child.get("name", "").lower()

        # Extract color swatches
        if "swatch" in child_name or "color" in child_name:
            fill = child.get("fill", "")
            if isinstance(fill, str) and fill.startswith("#"):
                specs.colors[child_name] = hex_to_rgba(fill)

        # Extract colors from named elements (walls, roof, etc.)
        fill = child.get("fill", "")
        if isinstance(fill, str) and fill.startswith("#"):
            # Store by element name
            elem_name = child_name.replace(" ", "_")
            specs.colors[elem_name] = hex_to_rgba(fill)

        # Look for specs panel
        if "specs" in child_name or "panel" in child_name:
            parse_specs_panel(child, specs)

    # Extract background color
    bg_fill = node_data.get("fill", "")
    if isinstance(bg_fill, str) and bg_fill.startswith("#"):
        specs.colors["background"] = hex_to_rgba(bg_fill)

    # Set dimensions based on product type
    specs.dimensions = get_product_dimensions(specs.product_type, specs)

    return specs


def parse_specs_panel(panel_node: Dict[str, Any], specs: DesignSpecs) -> None:
    """Parse specs panel for materials and lighting info."""
    panel_children = panel_node.get("children", [])
    if not isinstance(panel_children, list):
        return

    for panel_child in panel_children:
        if not isinstance(panel_child, dict):
            continue
        content = panel_child.get("content", "")
        if not isinstance(content, str):
            continue

        content_lower = content.lower()

        # Parse material specs
        if "roughness" in content_lower:
            match = re.search(r'(\d+\.?\d*)', content)
            if match:
                specs.materials["roughness"] = float(match.group(1))
        if "ceramic" in content_lower:
            specs.materials["type"] = "ceramic"
        if "matte" in content_lower:
            specs.materials["finish"] = "matte"
        if "wood" in content_lower:
            specs.materials["texture"] = "wood"
        if "plaster" in content_lower:
            specs.materials["type"] = "plaster"

        # Parse lighting specs
        if "soft" in content_lower:
            specs.lighting["key_type"] = "soft"
        if "warm" in content_lower:
            specs.lighting["color_temp"] = "warm"
        if "left" in content_lower:
            specs.lighting["key_direction"] = "left"
        if "right" in content_lower:
            specs.lighting["key_direction"] = "right"
        if "daylight" in content_lower:
            specs.lighting["type"] = "daylight"
        if "shadow" in content_lower:
            specs.lighting["ground_shadow"] = True


# =============================================================================
# BLENDER SCRIPT GENERATION (with QA3 auto-framing)
# =============================================================================

def generate_blender_script(
    specs: DesignSpecs,
    asset_path: str,
    render_path: str,
    config: Dict[str, Any]
) -> str:
    """Generate Blender Python script with auto-framing camera."""

    # Get colors with fallbacks
    bg_color = specs.colors.get("background", (0.98, 0.97, 0.96, 1.0))

    # Product-specific color mapping
    if specs.product_type == "house":
        wall_color = specs.colors.get("house_walls", specs.colors.get("walls", (1.0, 1.0, 1.0, 1.0)))
        roof_color = specs.colors.get("roof_left", specs.colors.get("roof", (0.55, 0.27, 0.07, 1.0)))
        door_color = specs.colors.get("door", (0.36, 0.25, 0.22, 1.0))
        window_color = specs.colors.get("window_left", specs.colors.get("windows", (0.53, 0.81, 0.92, 1.0)))
        grass_color = specs.colors.get("grass", (0.48, 0.70, 0.26, 1.0))
    else:
        # Mug/generic colors
        body_color = specs.colors.get("mug_body", specs.colors.get("swatch2", (1.0, 1.0, 1.0, 1.0)))
        accent_color = specs.colors.get("coffee", specs.colors.get("swatch3", (0.4, 0.25, 0.2, 1.0)))

    roughness = specs.materials.get("roughness", 0.4)
    render_engine = config.get("render_engine", DEFAULT_CONFIG["render_engine"])
    width = config.get("render_width", DEFAULT_CONFIG["render_width"])
    height = config.get("render_height", DEFAULT_CONFIG["render_height"])
    camera_margin = config.get("camera_margin", DEFAULT_CONFIG["camera_margin"])

    # Lighting based on specs
    key_x = -2.5 if specs.lighting.get("key_direction") == "left" else 2.5
    key_color = "(1.0, 0.95, 0.9)" if specs.lighting.get("color_temp") == "warm" else "(1.0, 1.0, 1.0)"
    key_size = 4 if specs.lighting.get("key_type") == "soft" else 2

    # Product dimensions for camera
    dims = specs.dimensions

    if specs.product_type == "house":
        script = generate_house_script(
            wall_color, roof_color, door_color, window_color, grass_color, bg_color,
            roughness, key_x, key_color, key_size, dims, camera_margin,
            render_engine, width, height, asset_path, render_path
        )
    else:
        script = generate_mug_script(
            body_color, accent_color, bg_color,
            roughness, key_x, key_color, key_size, dims, camera_margin,
            render_engine, width, height, asset_path, render_path
        )

    return script


def generate_house_script(
    wall_color, roof_color, door_color, window_color, grass_color, bg_color,
    roughness, key_x, key_color, key_size, dims, camera_margin,
    render_engine, width, height, asset_path, render_path
) -> str:
    """Generate Blender script for house product."""

    return f'''
import bpy
import math
from mathutils import Vector

# Clear scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# === CREATE HOUSE ASSET ===

# Walls (main body)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.5))
walls = bpy.context.active_object
walls.name = "House_Walls"
walls.scale = (1.2, 1.0, 0.8)
bpy.ops.object.transform_apply(scale=True)

# Wall material
wall_mat = bpy.data.materials.new(name="Wall_Material")
wall_mat.use_nodes = True
wall_bsdf = wall_mat.node_tree.nodes["Principled BSDF"]
wall_bsdf.inputs["Base Color"].default_value = {wall_color}
wall_bsdf.inputs["Roughness"].default_value = {roughness}
walls.data.materials.append(wall_mat)

# Roof (proper triangular prism)
bpy.ops.mesh.primitive_cone_add(
    vertices=4, radius1=1.0, depth=0.6,
    location=(0, 0, 1.2)
)
roof = bpy.context.active_object
roof.name = "House_Roof"
roof.rotation_euler = (0, 0, math.radians(45))
roof.scale = (1.4, 1.2, 1.0)
bpy.ops.object.transform_apply(rotation=True, scale=True)

# Roof material
roof_mat = bpy.data.materials.new(name="Roof_Material")
roof_mat.use_nodes = True
roof_bsdf = roof_mat.node_tree.nodes["Principled BSDF"]
roof_bsdf.inputs["Base Color"].default_value = {roof_color}
roof_bsdf.inputs["Roughness"].default_value = 0.7
roof.data.materials.append(roof_mat)

# Door
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.51, 0.35))
door = bpy.context.active_object
door.name = "House_Door"
door.scale = (0.25, 0.02, 0.5)
bpy.ops.object.transform_apply(scale=True)

door_mat = bpy.data.materials.new(name="Door_Material")
door_mat.use_nodes = True
door_bsdf = door_mat.node_tree.nodes["Principled BSDF"]
door_bsdf.inputs["Base Color"].default_value = {door_color}
door_bsdf.inputs["Roughness"].default_value = 0.5
door.data.materials.append(door_mat)

# Windows
window_mat = bpy.data.materials.new(name="Window_Material")
window_mat.use_nodes = True
window_bsdf = window_mat.node_tree.nodes["Principled BSDF"]
window_bsdf.inputs["Base Color"].default_value = {window_color}
window_bsdf.inputs["Roughness"].default_value = 0.1
window_bsdf.inputs["Alpha"].default_value = 0.7
window_mat.blend_method = 'BLEND'

# Left window
bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.4, -0.51, 0.6))
win_l = bpy.context.active_object
win_l.name = "Window_Left"
win_l.scale = (0.2, 0.02, 0.2)
bpy.ops.object.transform_apply(scale=True)
win_l.data.materials.append(window_mat)

# Right window
bpy.ops.mesh.primitive_cube_add(size=1, location=(0.4, -0.51, 0.6))
win_r = bpy.context.active_object
win_r.name = "Window_Right"
win_r.scale = (0.2, 0.02, 0.2)
bpy.ops.object.transform_apply(scale=True)
win_r.data.materials.append(window_mat)

# Chimney
bpy.ops.mesh.primitive_cube_add(size=1, location=(0.5, 0, 1.4))
chimney = bpy.context.active_object
chimney.name = "Chimney"
chimney.scale = (0.15, 0.15, 0.3)
bpy.ops.object.transform_apply(scale=True)
chimney.data.materials.append(roof_mat)

# Save asset
bpy.ops.wm.save_as_mainfile(filepath=r"{asset_path}")

# === QA3: AUTO-FRAME CAMERA ===

# Calculate scene bounding box
product_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH' and 'House' in obj.name or 'Window' in obj.name or 'Chimney' in obj.name or 'Door' in obj.name]

min_co = Vector((float('inf'), float('inf'), float('inf')))
max_co = Vector((float('-inf'), float('-inf'), float('-inf')))

for obj in product_objects:
    for v in obj.bound_box:
        world_v = obj.matrix_world @ Vector(v)
        min_co.x = min(min_co.x, world_v.x)
        min_co.y = min(min_co.y, world_v.y)
        min_co.z = min(min_co.z, world_v.z)
        max_co.x = max(max_co.x, world_v.x)
        max_co.y = max(max_co.y, world_v.y)
        max_co.z = max(max_co.z, world_v.z)

# Calculate center and size
center = (min_co + max_co) / 2
size = max_co - min_co
max_dim = max(size.x, size.y, size.z)

# Camera distance based on scene size with margin
camera_distance = max_dim * {camera_margin} * 1.8
camera_height = center.z + size.z * 0.3

# Add camera looking at center
bpy.ops.object.camera_add(
    location=(center.x + camera_distance * 0.7, center.y - camera_distance * 0.7, camera_height)
)
camera = bpy.context.active_object
camera.name = "Auto_Camera"

# Point camera at center
direction = center - camera.location
rot_quat = direction.to_track_quat('-Z', 'Y')
camera.rotation_euler = rot_quat.to_euler()

bpy.context.scene.camera = camera

# === RENDER ENVIRONMENT ===

# World background
world = bpy.data.worlds.new("RenderWorld")
bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes["Background"]
bg_node.inputs["Color"].default_value = {bg_color}

# Ground/grass
bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "Ground"
grass_mat = bpy.data.materials.new(name="Grass_Material")
grass_mat.use_nodes = True
grass_bsdf = grass_mat.node_tree.nodes["Principled BSDF"]
grass_bsdf.inputs["Base Color"].default_value = {grass_color}
grass_bsdf.inputs["Roughness"].default_value = 0.9
ground.data.materials.append(grass_mat)

# Key light (adjusted for scene size)
light_distance = max_dim * 2
bpy.ops.object.light_add(type='AREA', location=({key_x} * max_dim, -light_distance, center.z + max_dim))
key = bpy.context.active_object
key.data.energy = 200 * (max_dim ** 2)
key.data.size = {key_size} * max_dim
key.data.color = {key_color}

# Fill light
bpy.ops.object.light_add(type='AREA', location=(light_distance, light_distance * 0.5, center.z + max_dim * 0.5))
fill = bpy.context.active_object
fill.data.energy = 80 * (max_dim ** 2)
fill.data.size = 6 * max_dim

# Render settings
bpy.context.scene.render.engine = '{render_engine}'
bpy.context.scene.render.resolution_x = {width}
bpy.context.scene.render.resolution_y = {height}
bpy.context.scene.render.filepath = r"{render_path}"

# Render
bpy.ops.render.render(write_still=True)

print("RENDER_COMPLETE:", r"{render_path}")
print("ASSET_SAVED:", r"{asset_path}")
print("SCENE_CENTER:", center.x, center.y, center.z)
print("SCENE_SIZE:", size.x, size.y, size.z)
'''


def generate_mug_script(
    body_color, accent_color, bg_color,
    roughness, key_x, key_color, key_size, dims, camera_margin,
    render_engine, width, height, asset_path, render_path
) -> str:
    """Generate Blender script for mug product."""

    return f'''
import bpy
import math
from mathutils import Vector

# Clear scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# === CREATE MUG ASSET ===

# Mug body
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.35, depth=0.5, location=(0, 0, 0.25), vertices=64
)
body = bpy.context.active_object
body.name = "Mug_Body"

solidify = body.modifiers.new(name="Solidify", type='SOLIDIFY')
solidify.thickness = 0.03
solidify.offset = 1

# Body material
body_mat = bpy.data.materials.new(name="Body_Material")
body_mat.use_nodes = True
body_bsdf = body_mat.node_tree.nodes["Principled BSDF"]
body_bsdf.inputs["Base Color"].default_value = {body_color}
body_bsdf.inputs["Roughness"].default_value = {roughness}
body.data.materials.append(body_mat)

# Handle
bpy.ops.mesh.primitive_torus_add(
    major_radius=0.18, minor_radius=0.035,
    major_segments=48, minor_segments=24,
    location=(0.42, 0, 0.25),
    rotation=(0, math.radians(90), 0)
)
handle = bpy.context.active_object
handle.name = "Mug_Handle"
handle.data.materials.append(body_mat)

# Contents (coffee)
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.32, depth=0.02, location=(0, 0, 0.42), vertices=64
)
accent = bpy.context.active_object
accent.name = "Mug_Contents"

accent_mat = bpy.data.materials.new(name="Accent_Material")
accent_mat.use_nodes = True
accent_bsdf = accent_mat.node_tree.nodes["Principled BSDF"]
accent_bsdf.inputs["Base Color"].default_value = {accent_color}
accent_bsdf.inputs["Roughness"].default_value = 0.2
accent.data.materials.append(accent_mat)

# Apply modifiers
bpy.context.view_layer.objects.active = body
bpy.ops.object.modifier_apply(modifier="Solidify")

# Save asset
bpy.ops.wm.save_as_mainfile(filepath=r"{asset_path}")

# === QA3: AUTO-FRAME CAMERA ===

# Calculate scene bounding box
product_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH' and 'Mug' in obj.name]

min_co = Vector((float('inf'), float('inf'), float('inf')))
max_co = Vector((float('-inf'), float('-inf'), float('-inf')))

for obj in product_objects:
    for v in obj.bound_box:
        world_v = obj.matrix_world @ Vector(v)
        min_co.x = min(min_co.x, world_v.x)
        min_co.y = min(min_co.y, world_v.y)
        min_co.z = min(min_co.z, world_v.z)
        max_co.x = max(max_co.x, world_v.x)
        max_co.y = max(max_co.y, world_v.y)
        max_co.z = max(max_co.z, world_v.z)

# Calculate center and size
center = (min_co + max_co) / 2
size = max_co - min_co
max_dim = max(size.x, size.y, size.z)

# Camera distance with margin
camera_distance = max_dim * {camera_margin} * 2.0
camera_height = center.z + size.z * 0.2

# Add camera
bpy.ops.object.camera_add(
    location=(center.x + camera_distance * 0.6, center.y - camera_distance * 0.6, camera_height)
)
camera = bpy.context.active_object
camera.name = "Auto_Camera"

# Point at center
direction = center - camera.location
rot_quat = direction.to_track_quat('-Z', 'Y')
camera.rotation_euler = rot_quat.to_euler()

bpy.context.scene.camera = camera

# === RENDER ENVIRONMENT ===

# World background
world = bpy.data.worlds.new("RenderWorld")
bpy.context.scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes["Background"]
bg_node.inputs["Color"].default_value = {bg_color}

# Ground
bpy.ops.mesh.primitive_plane_add(size=5, location=(0, 0, 0))
ground = bpy.context.active_object
ground_mat = bpy.data.materials.new(name="Ground")
ground_mat.use_nodes = True
ground_bsdf = ground_mat.node_tree.nodes["Principled BSDF"]
ground_bsdf.inputs["Base Color"].default_value = {bg_color}
ground_bsdf.inputs["Roughness"].default_value = 0.9
ground.data.materials.append(ground_mat)

# Lighting scaled to scene
light_scale = max_dim * 2

bpy.ops.object.light_add(type='AREA', location=({key_x}, -light_scale * 0.5, light_scale))
key = bpy.context.active_object
key.data.energy = 150
key.data.size = {key_size}
key.data.color = {key_color}

bpy.ops.object.light_add(type='AREA', location=(light_scale * 0.5, light_scale * 0.5, light_scale * 0.4))
fill = bpy.context.active_object
fill.data.energy = 50
fill.data.size = 4

# Render settings
bpy.context.scene.render.engine = '{render_engine}'
bpy.context.scene.render.resolution_x = {width}
bpy.context.scene.render.resolution_y = {height}
bpy.context.scene.render.filepath = r"{render_path}"

# Render
bpy.ops.render.render(write_still=True)

print("RENDER_COMPLETE:", r"{render_path}")
print("ASSET_SAVED:", r"{asset_path}")
'''


def run_blender_script(script: str, config: Dict[str, Any]) -> Tuple[bool, str, str]:
    """Execute Blender script and return success status and output."""
    blender_path = config.get("blender_path", DEFAULT_CONFIG["blender_path"])
    timeout = config.get("timeout_seconds", DEFAULT_CONFIG["timeout_seconds"])

    if not Path(blender_path).exists():
        return False, "", f"Blender not found at {blender_path}"

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(script)
        script_path = f.name

    try:
        result = subprocess.run(
            [blender_path, "--background", "--python", script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Blender timed out after {timeout}s"
    except Exception as e:
        return False, "", str(e)
    finally:
        try:
            os.unlink(script_path)
        except:
            pass


# =============================================================================
# MAIN PIPELINE WITH QA
# =============================================================================

def visualize_product_with_qa(
    pencil_data: Dict[str, Any],
    output_name: str,
    config: Dict[str, Any],
    skip_on_qa_fail: bool = False
) -> RenderResult:
    """
    Main visualization function with QA checkpoints.

    Args:
        pencil_data: Node data from Pencil design
        output_name: Base name for output files
        config: Configuration overrides
        skip_on_qa_fail: If True, stop pipeline on QA failure
    """
    qa_results = []

    # Detect product type
    product_type = detect_product_type(pencil_data)

    # === QA1: Design Coherence ===
    qa1 = qa1_design_coherence(pencil_data, product_type)
    qa_results.append(qa1)

    if skip_on_qa_fail and qa1.status == QAStatus.FAIL:
        return RenderResult(
            success=False,
            error=f"QA1 Failed: {qa1.message}",
            qa_results=qa_results
        )

    # Extract specs
    specs = extract_specs_from_pencil_data(pencil_data)
    specs.product_type = product_type

    # === QA2: Spec Completeness ===
    qa2 = qa2_spec_completeness(specs, product_type)
    qa_results.append(qa2)

    if skip_on_qa_fail and qa2.status == QAStatus.FAIL:
        return RenderResult(
            success=False,
            error=f"QA2 Failed: {qa2.message}",
            specs=specs,
            qa_results=qa_results
        )

    # Setup output paths
    output_dir = Path(config.get("output_dir", DEFAULT_CONFIG["output_dir"]))
    output_dir.mkdir(parents=True, exist_ok=True)

    asset_path = str(output_dir / f"{output_name}_asset.blend")
    render_path = str(output_dir / f"{output_name}_render.png")

    # Generate and run Blender script (includes QA3 auto-framing)
    script = generate_blender_script(specs, asset_path, render_path, config)
    success, stdout, stderr = run_blender_script(script, config)

    # Add QA3 result (camera auto-framing is built into script)
    qa3 = QAResult(
        checkpoint="QA3_CAMERA_FRAMING",
        status=QAStatus.PASS if success else QAStatus.FAIL,
        message="Camera auto-framed to scene bounding box" if success else "Blender script failed",
        details={"auto_framing": True, "margin": config.get("camera_margin", 1.3)}
    )
    qa_results.append(qa3)

    if not success:
        return RenderResult(
            success=False,
            error=stderr or "Blender render failed",
            specs=specs,
            blender_output=stdout + "\n" + stderr,
            qa_results=qa_results
        )

    # === QA4: Output Validation ===
    qa4 = qa4_output_validation(render_path, config)
    qa_results.append(qa4)

    overall_success = not any(qa.status == QAStatus.FAIL for qa in qa_results)

    return RenderResult(
        success=overall_success and Path(render_path).exists(),
        asset_path=asset_path,
        render_path=render_path,
        specs=specs,
        blender_output=stdout,
        qa_results=qa_results
    )


# =============================================================================
# SKILL ENTRY POINT
# =============================================================================

def run(
    args: Dict[str, Any],
    tools: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for the product_visualize skill (v2.0 with QA).

    Args:
        pencil_data: Dict - Node data from Pencil design (from batch_get)
        output_name: str - Base name for output files (default: "product")
        colors: Dict - Override colors {name: "#RRGGBB"}
        materials: Dict - Override materials {roughness: 0.4}
        lighting: Dict - Override lighting {key_direction: "left"}
        product_type: str - Override product type (house, mug, box, generic)
        config: Dict - Override configuration
        skip_on_qa_fail: bool - Stop pipeline on QA failure (default: False)

    Returns:
        {
            "success": bool,
            "asset_path": str,
            "render_path": str,
            "specs": Dict,
            "qa_results": List[Dict],
            "qa_summary": str,
            "summary": str
        }
    """
    config = {**DEFAULT_CONFIG, **args.get("config", {})}
    skip_on_qa_fail = args.get("skip_on_qa_fail", False)

    pencil_data = args.get("pencil_data", {})
    output_name = args.get("output_name", "product")

    if pencil_data:
        # Full pipeline with QA
        result = visualize_product_with_qa(pencil_data, output_name, config, skip_on_qa_fail)
    else:
        # Manual specs mode
        product_type = args.get("product_type", "mug")
        specs = DesignSpecs(
            product_name=output_name,
            product_type=product_type,
            colors={k: hex_to_rgba(v) for k, v in args.get("colors", {}).items()},
            materials=args.get("materials", {"roughness": 0.4}),
            lighting=args.get("lighting", {"key_direction": "left", "color_temp": "warm"}),
            dimensions=get_product_dimensions(product_type, DesignSpecs())
        )

        output_dir = Path(config.get("output_dir", DEFAULT_CONFIG["output_dir"]))
        output_dir.mkdir(parents=True, exist_ok=True)
        asset_path = str(output_dir / f"{output_name}_asset.blend")
        render_path = str(output_dir / f"{output_name}_render.png")

        script = generate_blender_script(specs, asset_path, render_path, config)
        success, stdout, stderr = run_blender_script(script, config)

        qa_results = [
            QAResult("QA1_DESIGN_COHERENCE", QAStatus.PASS, "Manual specs - skipped", {}),
            QAResult("QA2_SPEC_COMPLETENESS", QAStatus.PASS, "Manual specs provided", {}),
            QAResult("QA3_CAMERA_FRAMING", QAStatus.PASS if success else QAStatus.FAIL,
                    "Auto-framed" if success else "Failed", {}),
        ]

        if success and Path(render_path).exists():
            qa4 = qa4_output_validation(render_path, config)
            qa_results.append(qa4)
            result = RenderResult(
                success=True,
                asset_path=asset_path,
                render_path=render_path,
                specs=specs,
                qa_results=qa_results
            )
        else:
            result = RenderResult(
                success=False,
                error=stderr or "Render failed",
                qa_results=qa_results
            )

    # Build QA summary
    qa_summary_parts = []
    for qa in result.qa_results:
        icon = {"pass": "[OK]", "warn": "[!!]", "fail": "[X]"}[qa.status.value]
        qa_summary_parts.append(f"{icon} {qa.checkpoint}: {qa.message}")
    qa_summary = "\n".join(qa_summary_parts)

    return {
        "success": result.success,
        "asset_path": result.asset_path,
        "render_path": result.render_path,
        "specs": result.specs.to_dict() if result.specs else None,
        "error": result.error,
        "qa_results": [qa.to_dict() for qa in result.qa_results],
        "qa_summary": qa_summary,
        "summary": f"Rendered {output_name} to {result.render_path}" if result.success else f"Failed: {result.error}"
    }


if __name__ == "__main__":
    # Test with house specs
    test_result = run(
        {
            "output_name": "qa_test_house",
            "product_type": "house",
            "colors": {
                "background": "#E8F4E8",
                "walls": "#FFFFFF",
                "roof": "#8B4513",
                "door": "#5D4037",
                "windows": "#87CEEB",
                "grass": "#7CB342"
            },
            "materials": {"roughness": 0.6},
            "lighting": {"key_direction": "right", "color_temp": "warm"}
        },
        {},
        {}
    )
    print(json.dumps(test_result, indent=2))
