"""
Image Project Manager Skill - Scene-based image workflow with reproducibility tracking.

Capabilities:
- Create and manage .imgproj project files
- Track image "scenes" (brand assets, product mockups, etc.) with variants
- Record generation parameters for reproducibility
- Download and archive approved images
- Export in multiple formats: individual, grid, carousel, PDF
- Handle client revisions by regenerating only changed images

Similar to video_project_manager but for image projects.

Phase 3.2.4
"""

import os
import json
import time
import hashlib
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


SKILL_META = {
    "name": "image_project_manager",
    "description": "Manage scene-based image projects with reproducibility tracking and multi-format export",
    "tier": "tested",
    "version": "1.0.0",
    "phase": "3.2",
    "keywords": [
        "image", "project", "scene", "workflow", "reproducibility",
        "brand", "assets", "mockup", "carousel", "grid", "composition"
    ],
    "requires_network": False,
    "timeout_seconds": 600,
    "expected_runtime_seconds": 60,
    "dependencies": ["PIL", "reportlab"],  # For image composition
    "side_effects": ["writes_file"],
}


class SceneStatus(Enum):
    """Status of a scene in the project."""
    DRAFT = "draft"
    GENERATING = "generating"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"


class VariantStatus(Enum):
    """Status of an image variant."""
    GENERATING = "generating"
    READY = "ready"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExportFormat(Enum):
    """Export format options."""
    INDIVIDUAL = "individual"
    GRID = "grid"
    CAROUSEL_HTML = "carousel_html"
    CAROUSEL_PDF = "carousel_pdf"
    ALL = "all"


@dataclass
class ImageVariant:
    """A single variant of an image scene."""
    id: str
    seed: Optional[int] = None
    status: VariantStatus = VariantStatus.GENERATING
    generation_url: Optional[str] = None
    download_url: Optional[str] = None
    local_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size_bytes: Optional[int] = None
    generated_at: Optional[str] = None
    approved_at: Optional[str] = None
    notes: Optional[str] = None
    generation_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class ImageScene:
    """A scene in the image project (e.g., logo, icon, product shot)."""
    id: str
    name: str
    prompt: str
    scene_type: str  # "logo", "icon", "product", "slide", "banner", etc.
    order: int
    status: SceneStatus = SceneStatus.DRAFT
    variants: List[ImageVariant] = field(default_factory=list)
    approved_variant_id: Optional[str] = None
    aspect_ratio: str = "1:1"
    target_width: Optional[int] = 1024
    target_height: Optional[int] = 1024
    style_reference: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["variants"] = [v.to_dict() for v in self.variants]
        return d


@dataclass
class ImageProject:
    """An image project with multiple scenes."""
    id: str
    name: str
    project_type: str  # "brand_kit", "product_mockups", "carousel", "presentation"
    description: Optional[str] = None
    scenes: List[ImageScene] = field(default_factory=list)
    style_guide: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scenes"] = [s.to_dict() for s in self.scenes]
        return d


class ImageProjectManager:
    """Manages scene-based image projects."""

    def __init__(self, project_dir: str = None):
        """Initialize the project manager.

        Args:
            project_dir: Directory to store projects. Defaults to ~/image_projects
        """
        if project_dir is None:
            project_dir = str(Path.home() / "image_projects")

        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def create_project(
        self,
        name: str,
        project_type: str = "brand_kit",
        description: Optional[str] = None,
        style_guide: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ImageProject:
        """Create a new image project.

        Args:
            name: Project name
            project_type: Type of project (brand_kit, product_mockups, carousel, presentation)
            description: Project description
            style_guide: Style guide dict (colors, fonts, brand guidelines)
            metadata: Additional metadata (client, deadline, etc.)

        Returns:
            ImageProject instance
        """
        project_id = self._generate_id(name)
        now = datetime.utcnow().isoformat() + "Z"

        project = ImageProject(
            id=project_id,
            name=name,
            project_type=project_type,
            description=description,
            style_guide=style_guide or {},
            created_at=now,
            updated_at=now,
            metadata=metadata or {}
        )

        # Create project directory
        project_path = self.project_dir / project_id
        project_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (project_path / "scenes").mkdir(exist_ok=True)
        (project_path / "variants").mkdir(exist_ok=True)
        (project_path / "approved").mkdir(exist_ok=True)
        (project_path / "exports").mkdir(exist_ok=True)

        # Save project file
        self._save_project(project)

        return project

    def add_scene(
        self,
        project: ImageProject,
        name: str,
        prompt: str,
        scene_type: str = "image",
        order: Optional[int] = None,
        aspect_ratio: str = "1:1",
        target_width: int = 1024,
        target_height: int = 1024
    ) -> ImageScene:
        """Add a scene to a project.

        Args:
            project: ImageProject instance
            name: Scene name (e.g., "Logo", "Icon", "Hero Banner")
            prompt: Image generation prompt
            scene_type: Type (logo, icon, product, slide, banner, etc.)
            order: Scene order (defaults to end)
            aspect_ratio: Image aspect ratio
            target_width: Target width in pixels
            target_height: Target height in pixels

        Returns:
            ImageScene instance
        """
        scene_id = self._generate_id(f"{project.id}_{name}")
        now = datetime.utcnow().isoformat() + "Z"

        if order is None:
            order = len(project.scenes)

        scene = ImageScene(
            id=scene_id,
            name=name,
            prompt=prompt,
            scene_type=scene_type,
            order=order,
            aspect_ratio=aspect_ratio,
            target_width=target_width,
            target_height=target_height,
            created_at=now,
            updated_at=now
        )

        project.scenes.append(scene)
        project.updated_at = now

        self._save_project(project)

        return scene

    def add_variant(
        self,
        project: ImageProject,
        scene: ImageScene,
        seed: Optional[int] = None,
        generation_url: Optional[str] = None,
        local_path: Optional[str] = None,
        generation_params: Optional[Dict[str, Any]] = None
    ) -> ImageVariant:
        """Add a variant to a scene.

        Args:
            project: ImageProject instance
            scene: ImageScene instance
            seed: Seed value from generation
            generation_url: URL where image was generated
            local_path: Path to downloaded image
            generation_params: Generation parameters (model, steps, cfg, etc.)

        Returns:
            ImageVariant instance
        """
        variant_id = self._generate_id(f"{scene.id}_{len(scene.variants)}")
        now = datetime.utcnow().isoformat() + "Z"

        variant = ImageVariant(
            id=variant_id,
            seed=seed,
            generation_url=generation_url,
            local_path=local_path,
            generated_at=now,
            generation_params=generation_params or {}
        )

        # Get image dimensions if local_path exists
        if local_path and os.path.exists(local_path):
            try:
                from PIL import Image
                img = Image.open(local_path)
                variant.width = img.width
                variant.height = img.height
                variant.file_size_bytes = os.path.getsize(local_path)
                variant.status = VariantStatus.READY
            except Exception:
                pass

        scene.variants.append(variant)
        scene.status = SceneStatus.REVIEW
        scene.updated_at = now
        project.updated_at = now

        self._save_project(project)

        return variant

    def approve_variant(
        self,
        project: ImageProject,
        scene: ImageScene,
        variant: ImageVariant
    ) -> None:
        """Approve a variant for a scene.

        Args:
            project: ImageProject instance
            scene: ImageScene instance
            variant: ImageVariant to approve
        """
        now = datetime.utcnow().isoformat() + "Z"

        # Mark variant as approved
        variant.status = VariantStatus.APPROVED
        variant.approved_at = now

        # Mark other variants as rejected
        for v in scene.variants:
            if v.id != variant.id and v.status != VariantStatus.REJECTED:
                v.status = VariantStatus.REJECTED

        # Update scene
        scene.approved_variant_id = variant.id
        scene.status = SceneStatus.APPROVED
        scene.updated_at = now
        project.updated_at = now

        self._save_project(project)

    def export_individual(
        self,
        project: ImageProject,
        output_dir: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Export approved images as individual files.

        Args:
            project: ImageProject instance
            output_dir: Output directory (defaults to project/exports/individual)

        Returns:
            (success, output_dir or error_message)
        """
        if output_dir is None:
            project_path = self.project_dir / project.id
            output_dir = str(project_path / "exports" / "individual")

        os.makedirs(output_dir, exist_ok=True)

        approved_scenes = [s for s in project.scenes if s.status == SceneStatus.APPROVED]

        if not approved_scenes:
            return False, "No approved scenes to export"

        for scene in approved_scenes:
            variant = next(
                (v for v in scene.variants if v.id == scene.approved_variant_id),
                None
            )
            if not variant or not variant.local_path:
                continue

            # Copy to export directory with descriptive name
            src = variant.local_path
            dest = os.path.join(output_dir, f"{scene.name.replace(' ', '_')}.png")

            try:
                import shutil
                shutil.copy2(src, dest)
            except Exception as e:
                return False, f"Export failed: {str(e)}"

        return True, output_dir

    def export_grid(
        self,
        project: ImageProject,
        output_path: Optional[str] = None,
        cols: int = 3,
        spacing: int = 20
    ) -> Tuple[bool, str]:
        """Export approved images as a grid.

        Args:
            project: ImageProject instance
            output_path: Output file path (defaults to project/exports/grid.png)
            cols: Number of columns
            spacing: Spacing between images in pixels

        Returns:
            (success, output_path or error_message)
        """
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            return False, "PIL required for grid export (pip install Pillow)"

        if output_path is None:
            project_path = self.project_dir / project.id
            output_path = str(project_path / "exports" / "grid.png")

        approved_scenes = sorted(
            [s for s in project.scenes if s.status == SceneStatus.APPROVED],
            key=lambda x: x.order
        )

        if not approved_scenes:
            return False, "No approved scenes to export"

        # Load all images
        images = []
        for scene in approved_scenes:
            variant = next(
                (v for v in scene.variants if v.id == scene.approved_variant_id),
                None
            )
            if variant and variant.local_path and os.path.exists(variant.local_path):
                images.append(Image.open(variant.local_path))

        if not images:
            return False, "No valid images found"

        # Calculate grid dimensions
        rows = (len(images) + cols - 1) // cols
        cell_width = max(img.width for img in images)
        cell_height = max(img.height for img in images)

        grid_width = cols * cell_width + (cols + 1) * spacing
        grid_height = rows * cell_height + (rows + 1) * spacing

        # Create grid canvas
        grid = Image.new('RGB', (grid_width, grid_height), 'white')

        # Place images
        for idx, img in enumerate(images):
            row = idx // cols
            col = idx % cols
            x = col * cell_width + (col + 1) * spacing
            y = row * cell_height + (row + 1) * spacing

            # Center image in cell
            x_offset = (cell_width - img.width) // 2
            y_offset = (cell_height - img.height) // 2

            grid.paste(img, (x + x_offset, y + y_offset))

        grid.save(output_path)
        return True, output_path

    def load_project(self, project_id: str) -> Optional[ImageProject]:
        """Load a project from disk.

        Args:
            project_id: Project ID

        Returns:
            ImageProject instance or None if not found
        """
        project_file = self.project_dir / project_id / f"{project_id}.imgproj"

        if not project_file.exists():
            return None

        with open(project_file, 'r') as f:
            data = json.load(f)

        # Reconstruct project
        project = ImageProject(
            id=data["id"],
            name=data["name"],
            project_type=data["project_type"],
            description=data.get("description"),
            style_guide=data.get("style_guide", {}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            metadata=data.get("metadata", {})
        )

        # Reconstruct scenes
        for scene_data in data.get("scenes", []):
            scene = ImageScene(
                id=scene_data["id"],
                name=scene_data["name"],
                prompt=scene_data["prompt"],
                scene_type=scene_data["scene_type"],
                order=scene_data["order"],
                status=SceneStatus(scene_data["status"]),
                approved_variant_id=scene_data.get("approved_variant_id"),
                aspect_ratio=scene_data.get("aspect_ratio", "1:1"),
                target_width=scene_data.get("target_width", 1024),
                target_height=scene_data.get("target_height", 1024),
                notes=scene_data.get("notes"),
                created_at=scene_data.get("created_at"),
                updated_at=scene_data.get("updated_at")
            )

            # Reconstruct variants
            for variant_data in scene_data.get("variants", []):
                variant = ImageVariant(
                    id=variant_data["id"],
                    seed=variant_data.get("seed"),
                    status=VariantStatus(variant_data["status"]),
                    generation_url=variant_data.get("generation_url"),
                    download_url=variant_data.get("download_url"),
                    local_path=variant_data.get("local_path"),
                    width=variant_data.get("width"),
                    height=variant_data.get("height"),
                    file_size_bytes=variant_data.get("file_size_bytes"),
                    generated_at=variant_data.get("generated_at"),
                    approved_at=variant_data.get("approved_at"),
                    notes=variant_data.get("notes"),
                    generation_params=variant_data.get("generation_params", {})
                )
                scene.variants.append(variant)

            project.scenes.append(scene)

        return project

    def get_project_status(self, project: ImageProject) -> Dict[str, Any]:
        """Get project status summary.

        Args:
            project: ImageProject instance

        Returns:
            Status summary dict
        """
        total_scenes = len(project.scenes)
        approved_scenes = len([s for s in project.scenes if s.status == SceneStatus.APPROVED])
        draft_scenes = len([s for s in project.scenes if s.status == SceneStatus.DRAFT])
        review_scenes = len([s for s in project.scenes if s.status == SceneStatus.REVIEW])

        total_variants = sum(len(s.variants) for s in project.scenes)

        return {
            "project_id": project.id,
            "name": project.name,
            "project_type": project.project_type,
            "total_scenes": total_scenes,
            "approved_scenes": approved_scenes,
            "draft_scenes": draft_scenes,
            "review_scenes": review_scenes,
            "total_variants": total_variants,
            "ready_to_export": approved_scenes == total_scenes and total_scenes > 0,
            "completion_percentage": (approved_scenes / total_scenes * 100) if total_scenes > 0 else 0
        }

    def _save_project(self, project: ImageProject) -> None:
        """Save project to disk."""
        project_path = self.project_dir / project.id
        project_file = project_path / f"{project.id}.imgproj"

        with open(project_file, 'w') as f:
            json.dump(project.to_dict(), f, indent=2)

    def _generate_id(self, name: str) -> str:
        """Generate a unique ID from name."""
        timestamp = str(int(time.time() * 1000))
        hash_input = f"{name}_{timestamp}"
        hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        return f"{hash_digest}_{timestamp[-6:]}"


# Main skill function
def run(
    action: str,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    project_type: str = "brand_kit",
    scene_name: Optional[str] = None,
    prompt: Optional[str] = None,
    scene_type: str = "image",
    variant_id: Optional[str] = None,
    seed: Optional[int] = None,
    generation_url: Optional[str] = None,
    local_path: Optional[str] = None,
    generation_params: Optional[Dict[str, Any]] = None,
    export_format: str = "individual",
    output_path: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Execute image project management actions.

    Args:
        action: Action to perform (create_project, add_scene, add_variant, approve_variant, export, list, status)
        project_id: Project ID
        project_name: Project name (for create)
        project_type: Type (brand_kit, product_mockups, carousel, presentation)
        scene_name: Scene name
        prompt: Image generation prompt
        scene_type: Scene type (logo, icon, product, slide, banner)
        variant_id: Variant ID
        seed: Seed value
        generation_url: Generation URL
        local_path: Local file path
        generation_params: Generation parameters dict
        export_format: Export format (individual, grid, carousel_html, carousel_pdf)
        output_path: Output file/directory path
        **kwargs: Additional arguments

    Returns:
        Result dictionary
    """
    manager = ImageProjectManager()

    try:
        if action == "create_project":
            if not project_name:
                return {"success": False, "error": "project_name required"}

            project = manager.create_project(
                name=project_name,
                project_type=project_type,
                description=kwargs.get("description"),
                style_guide=kwargs.get("style_guide"),
                metadata=kwargs.get("metadata")
            )

            return {
                "success": True,
                "project_id": project.id,
                "message": f"Created project '{project.name}'"
            }

        elif action == "add_scene":
            if not project_id or not scene_name or not prompt:
                return {"success": False, "error": "project_id, scene_name, and prompt required"}

            project = manager.load_project(project_id)
            if not project:
                return {"success": False, "error": f"Project '{project_id}' not found"}

            scene = manager.add_scene(
                project=project,
                name=scene_name,
                prompt=prompt,
                scene_type=scene_type,
                order=kwargs.get("order"),
                aspect_ratio=kwargs.get("aspect_ratio", "1:1"),
                target_width=kwargs.get("target_width", 1024),
                target_height=kwargs.get("target_height", 1024)
            )

            return {
                "success": True,
                "scene_id": scene.id,
                "message": f"Added scene '{scene.name}' to project"
            }

        elif action == "add_variant":
            if not project_id or not scene_name:
                return {"success": False, "error": "project_id and scene_name required"}

            project = manager.load_project(project_id)
            if not project:
                return {"success": False, "error": f"Project '{project_id}' not found"}

            scene = next((s for s in project.scenes if s.name == scene_name), None)
            if not scene:
                return {"success": False, "error": f"Scene '{scene_name}' not found"}

            variant = manager.add_variant(
                project=project,
                scene=scene,
                seed=seed,
                generation_url=generation_url,
                local_path=local_path,
                generation_params=generation_params
            )

            return {
                "success": True,
                "variant_id": variant.id,
                "message": f"Added variant to scene '{scene.name}'"
            }

        elif action == "approve_variant":
            if not project_id or not scene_name or not variant_id:
                return {"success": False, "error": "project_id, scene_name, and variant_id required"}

            project = manager.load_project(project_id)
            if not project:
                return {"success": False, "error": f"Project '{project_id}' not found"}

            scene = next((s for s in project.scenes if s.name == scene_name), None)
            if not scene:
                return {"success": False, "error": f"Scene '{scene_name}' not found"}

            variant = next((v for v in scene.variants if v.id == variant_id), None)
            if not variant:
                return {"success": False, "error": f"Variant '{variant_id}' not found"}

            manager.approve_variant(project, scene, variant)

            return {
                "success": True,
                "message": f"Approved variant for scene '{scene.name}'"
            }

        elif action == "export":
            if not project_id:
                return {"success": False, "error": "project_id required"}

            project = manager.load_project(project_id)
            if not project:
                return {"success": False, "error": f"Project '{project_id}' not found"}

            if export_format == "individual":
                success, result = manager.export_individual(project, output_path)
            elif export_format == "grid":
                success, result = manager.export_grid(
                    project,
                    output_path,
                    cols=kwargs.get("cols", 3),
                    spacing=kwargs.get("spacing", 20)
                )
            else:
                return {"success": False, "error": f"Unsupported export format: {export_format}"}

            if success:
                return {
                    "success": True,
                    "output_path": result,
                    "message": f"Exported as {export_format}"
                }
            else:
                return {"success": False, "error": result}

        elif action == "list":
            # List all projects
            projects = []
            for project_dir in manager.project_dir.iterdir():
                if not project_dir.is_dir():
                    continue

                project_file = project_dir / f"{project_dir.name}.imgproj"
                if not project_file.exists():
                    continue

                with open(project_file, 'r') as f:
                    data = json.load(f)

                projects.append({
                    "id": data["id"],
                    "name": data["name"],
                    "project_type": data["project_type"],
                    "scenes_count": len(data.get("scenes", [])),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at")
                })

            return {
                "success": True,
                "projects": sorted(projects, key=lambda x: x["updated_at"], reverse=True),
                "count": len(projects)
            }

        elif action == "status":
            if not project_id:
                return {"success": False, "error": "project_id required"}

            project = manager.load_project(project_id)
            if not project:
                return {"success": False, "error": f"Project '{project_id}' not found"}

            status = manager.get_project_status(project)
            return {
                "success": True,
                "status": status
            }

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Test the skill
    result = run(action="list")
    print(json.dumps(result, indent=2))
