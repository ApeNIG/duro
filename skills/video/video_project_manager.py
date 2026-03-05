"""
Video Project Manager Skill - Scene-based video workflow with reproducibility tracking.

Capabilities:
- Create and manage .vidproj project files
- Track scenes with multiple variants
- Record seed values for reproducibility
- Download and archive approved scenes
- Compose final video from approved scenes
- Handle client revisions by regenerating only changed scenes

Phase 3.2.3
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
    "name": "video_project_manager",
    "description": "Manage scene-based video projects with reproducibility tracking and incremental revision workflow",
    "tier": "tested",
    "version": "1.0.0",
    "phase": "3.2",
    "keywords": [
        "video", "project", "scene", "workflow", "reproducibility",
        "revision", "composition", "ffmpeg", "flow", "seed"
    ],
    "requires_network": True,
    "timeout_seconds": 1800,
    "expected_runtime_seconds": 300,
    "dependencies": ["ffmpeg"],
    "side_effects": ["writes_file", "network_request"],
}


class SceneStatus(Enum):
    """Status of a scene in the project."""
    DRAFT = "draft"
    GENERATING = "generating"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"


class VariantStatus(Enum):
    """Status of a scene variant."""
    GENERATING = "generating"
    READY = "ready"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class SceneVariant:
    """A single variant of a scene."""
    id: str
    seed: Optional[int] = None
    status: VariantStatus = VariantStatus.GENERATING
    flow_url: Optional[str] = None
    download_url: Optional[str] = None
    local_path: Optional[str] = None
    generated_at: Optional[str] = None
    approved_at: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class Scene:
    """A scene in the video project."""
    id: str
    name: str
    prompt: str
    order: int
    status: SceneStatus = SceneStatus.DRAFT
    variants: List[SceneVariant] = field(default_factory=list)
    approved_variant_id: Optional[str] = None
    duration: Optional[float] = None
    aspect_ratio: str = "16:9"
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["variants"] = [v.to_dict() for v in self.variants]
        return d


@dataclass
class VideoProject:
    """A video project with multiple scenes."""
    id: str
    name: str
    description: Optional[str] = None
    scenes: List[Scene] = field(default_factory=list)
    output_path: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scenes"] = [s.to_dict() for s in self.scenes]
        return d


class VideoProjectManager:
    """Manages scene-based video projects."""

    def __init__(self, project_dir: str = None):
        """Initialize the project manager.

        Args:
            project_dir: Directory to store projects. Defaults to ~/video_projects
        """
        if project_dir is None:
            project_dir = str(Path.home() / "video_projects")

        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VideoProject:
        """Create a new video project.

        Args:
            name: Project name
            description: Project description
            metadata: Additional metadata (client, deadline, etc.)

        Returns:
            VideoProject instance
        """
        project_id = self._generate_id(name)
        now = datetime.utcnow().isoformat() + "Z"

        project = VideoProject(
            id=project_id,
            name=name,
            description=description,
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

        # Save project file
        self._save_project(project)

        return project

    def add_scene(
        self,
        project: VideoProject,
        name: str,
        prompt: str,
        order: Optional[int] = None,
        aspect_ratio: str = "16:9"
    ) -> Scene:
        """Add a scene to a project.

        Args:
            project: VideoProject instance
            name: Scene name
            prompt: Video generation prompt
            order: Scene order (defaults to end)
            aspect_ratio: Video aspect ratio

        Returns:
            Scene instance
        """
        scene_id = self._generate_id(f"{project.id}_{name}")
        now = datetime.utcnow().isoformat() + "Z"

        if order is None:
            order = len(project.scenes)

        scene = Scene(
            id=scene_id,
            name=name,
            prompt=prompt,
            order=order,
            aspect_ratio=aspect_ratio,
            created_at=now,
            updated_at=now
        )

        project.scenes.append(scene)
        project.updated_at = now

        self._save_project(project)

        return scene

    def add_variant(
        self,
        project: VideoProject,
        scene: Scene,
        seed: Optional[int] = None,
        flow_url: Optional[str] = None
    ) -> SceneVariant:
        """Add a variant to a scene.

        Args:
            project: VideoProject instance
            scene: Scene instance
            seed: Seed value from Flow generation
            flow_url: URL to the video in Flow

        Returns:
            SceneVariant instance
        """
        variant_id = self._generate_id(f"{scene.id}_{len(scene.variants)}")
        now = datetime.utcnow().isoformat() + "Z"

        variant = SceneVariant(
            id=variant_id,
            seed=seed,
            flow_url=flow_url,
            generated_at=now
        )

        scene.variants.append(variant)
        scene.status = SceneStatus.REVIEW
        scene.updated_at = now
        project.updated_at = now

        self._save_project(project)

        return variant

    def approve_variant(
        self,
        project: VideoProject,
        scene: Scene,
        variant: SceneVariant,
        local_path: Optional[str] = None
    ) -> None:
        """Approve a variant for a scene.

        Args:
            project: VideoProject instance
            scene: Scene instance
            variant: SceneVariant to approve
            local_path: Path to downloaded video file
        """
        now = datetime.utcnow().isoformat() + "Z"

        # Mark variant as approved
        variant.status = VariantStatus.APPROVED
        variant.approved_at = now

        if local_path:
            variant.local_path = local_path

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

    def compose_final_video(
        self,
        project: VideoProject,
        output_path: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Compose final video from approved scenes.

        Args:
            project: VideoProject instance
            output_path: Output file path (defaults to project dir)

        Returns:
            (success, output_path or error_message)
        """
        # Get approved scenes in order
        approved_scenes = [
            s for s in sorted(project.scenes, key=lambda x: x.order)
            if s.status == SceneStatus.APPROVED and s.approved_variant_id
        ]

        if not approved_scenes:
            return False, "No approved scenes to compose"

        # Get video paths
        video_paths = []
        for scene in approved_scenes:
            variant = next(
                (v for v in scene.variants if v.id == scene.approved_variant_id),
                None
            )
            if not variant or not variant.local_path:
                return False, f"Scene '{scene.name}' missing local video file"

            video_paths.append(variant.local_path)

        # Set output path
        if output_path is None:
            project_path = self.project_dir / project.id
            output_path = str(project_path / f"{project.id}_final.mp4")

        # Create concat file for ffmpeg
        project_path = self.project_dir / project.id
        concat_file = project_path / "concat_list.txt"

        with open(concat_file, 'w') as f:
            for video_path in video_paths:
                f.write(f"file '{os.path.abspath(video_path)}'\n")

        # Run ffmpeg
        try:
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                output_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            project.output_path = output_path
            project.updated_at = datetime.utcnow().isoformat() + "Z"
            self._save_project(project)

            return True, output_path

        except subprocess.CalledProcessError as e:
            return False, f"ffmpeg error: {e.stderr}"
        except Exception as e:
            return False, f"Composition failed: {str(e)}"

    def load_project(self, project_id: str) -> Optional[VideoProject]:
        """Load a project from disk.

        Args:
            project_id: Project ID

        Returns:
            VideoProject instance or None if not found
        """
        project_file = self.project_dir / project_id / f"{project_id}.vidproj"

        if not project_file.exists():
            return None

        with open(project_file, 'r') as f:
            data = json.load(f)

        # Reconstruct project
        project = VideoProject(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            output_path=data.get("output_path"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            metadata=data.get("metadata", {})
        )

        # Reconstruct scenes
        for scene_data in data.get("scenes", []):
            scene = Scene(
                id=scene_data["id"],
                name=scene_data["name"],
                prompt=scene_data["prompt"],
                order=scene_data["order"],
                status=SceneStatus(scene_data["status"]),
                approved_variant_id=scene_data.get("approved_variant_id"),
                duration=scene_data.get("duration"),
                aspect_ratio=scene_data.get("aspect_ratio", "16:9"),
                notes=scene_data.get("notes"),
                created_at=scene_data.get("created_at"),
                updated_at=scene_data.get("updated_at")
            )

            # Reconstruct variants
            for variant_data in scene_data.get("variants", []):
                variant = SceneVariant(
                    id=variant_data["id"],
                    seed=variant_data.get("seed"),
                    status=VariantStatus(variant_data["status"]),
                    flow_url=variant_data.get("flow_url"),
                    download_url=variant_data.get("download_url"),
                    local_path=variant_data.get("local_path"),
                    generated_at=variant_data.get("generated_at"),
                    approved_at=variant_data.get("approved_at"),
                    notes=variant_data.get("notes")
                )
                scene.variants.append(variant)

            project.scenes.append(scene)

        return project

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects.

        Returns:
            List of project metadata dicts
        """
        projects = []

        for project_dir in self.project_dir.iterdir():
            if not project_dir.is_dir():
                continue

            project_file = project_dir / f"{project_dir.name}.vidproj"
            if not project_file.exists():
                continue

            with open(project_file, 'r') as f:
                data = json.load(f)

            projects.append({
                "id": data["id"],
                "name": data["name"],
                "description": data.get("description"),
                "scenes_count": len(data.get("scenes", [])),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at")
            })

        return sorted(projects, key=lambda x: x["updated_at"], reverse=True)

    def get_project_status(self, project: VideoProject) -> Dict[str, Any]:
        """Get project status summary.

        Args:
            project: VideoProject instance

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
            "total_scenes": total_scenes,
            "approved_scenes": approved_scenes,
            "draft_scenes": draft_scenes,
            "review_scenes": review_scenes,
            "total_variants": total_variants,
            "ready_to_compose": approved_scenes == total_scenes and total_scenes > 0,
            "completion_percentage": (approved_scenes / total_scenes * 100) if total_scenes > 0 else 0
        }

    def _save_project(self, project: VideoProject) -> None:
        """Save project to disk."""
        project_path = self.project_dir / project.id
        project_file = project_path / f"{project.id}.vidproj"

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
    scene_name: Optional[str] = None,
    prompt: Optional[str] = None,
    variant_id: Optional[str] = None,
    seed: Optional[int] = None,
    flow_url: Optional[str] = None,
    local_path: Optional[str] = None,
    output_path: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Execute video project management actions.

    Args:
        action: Action to perform (create_project, add_scene, add_variant, approve_variant, compose, list, status)
        project_id: Project ID
        project_name: Project name (for create)
        scene_name: Scene name
        prompt: Video generation prompt
        variant_id: Variant ID
        seed: Seed value
        flow_url: Flow URL
        local_path: Local file path
        output_path: Output file path
        **kwargs: Additional arguments

    Returns:
        Result dictionary
    """
    manager = VideoProjectManager()

    try:
        if action == "create_project":
            if not project_name:
                return {"success": False, "error": "project_name required"}

            project = manager.create_project(
                name=project_name,
                description=kwargs.get("description"),
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
                order=kwargs.get("order"),
                aspect_ratio=kwargs.get("aspect_ratio", "16:9")
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
                flow_url=flow_url
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

            manager.approve_variant(
                project=project,
                scene=scene,
                variant=variant,
                local_path=local_path
            )

            return {
                "success": True,
                "message": f"Approved variant for scene '{scene.name}'"
            }

        elif action == "compose":
            if not project_id:
                return {"success": False, "error": "project_id required"}

            project = manager.load_project(project_id)
            if not project:
                return {"success": False, "error": f"Project '{project_id}' not found"}

            success, result = manager.compose_final_video(project, output_path)

            if success:
                return {
                    "success": True,
                    "output_path": result,
                    "message": "Final video composed successfully"
                }
            else:
                return {"success": False, "error": result}

        elif action == "list":
            projects = manager.list_projects()
            return {
                "success": True,
                "projects": projects,
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
