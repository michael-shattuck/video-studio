import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from .models import (
    Project, ProjectConfig, ProjectStatus, PipelineStep,
    StepStatus, VideoScript, CreateProjectRequest
)


class ProjectManager:
    def __init__(self, projects_dir: Path):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def _project_path(self, project_id: str) -> Path:
        return self.projects_dir / f"{project_id}.json"

    def _save(self, project: Project) -> None:
        project.updated_at = datetime.now()
        path = self._project_path(project.id)
        with open(path, "w") as f:
            f.write(project.model_dump_json(indent=2))

    def _load(self, project_id: str) -> Optional[Project]:
        path = self._project_path(project_id)
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        return Project.model_validate(data)

    def create(self, config: ProjectConfig) -> Project:
        project = Project(config=config)
        self._save(project)
        return project

    def get(self, project_id: str) -> Optional[Project]:
        return self._load(project_id)

    def list_all(self) -> List[Project]:
        projects = []
        for path in self.projects_dir.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                projects.append(Project.model_validate(data))
            except Exception:
                continue
        return sorted(projects, key=lambda p: p.created_at, reverse=True)

    def update_config(self, project_id: str, config: ProjectConfig) -> Optional[Project]:
        project = self._load(project_id)
        if not project:
            return None
        project.config = config
        self._save(project)
        return project

    def update_status(self, project_id: str, status: ProjectStatus) -> Optional[Project]:
        project = self._load(project_id)
        if not project:
            return None
        project.status = status
        self._save(project)
        return project

    def update_step(
        self,
        project_id: str,
        step_name: str,
        status: Optional[StepStatus] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        artifacts: Optional[List[str]] = None,
        error: Optional[str] = None
    ) -> Optional[Project]:
        project = self._load(project_id)
        if not project or step_name not in project.steps:
            return None

        step = project.steps[step_name]

        if status is not None:
            step.status = status
            if status == StepStatus.RUNNING and step.started_at is None:
                step.started_at = datetime.now()
            elif status in (StepStatus.COMPLETE, StepStatus.FAILED):
                step.completed_at = datetime.now()

        if progress is not None:
            step.progress = progress

        if message is not None:
            step.message = message

        if artifacts is not None:
            step.artifacts = artifacts

        if error is not None:
            step.error = error

        self._save(project)
        return project

    def set_script(self, project_id: str, script: VideoScript) -> Optional[Project]:
        project = self._load(project_id)
        if not project:
            return None
        project.script = script
        self._save(project)
        return project

    def set_output_dir(self, project_id: str, output_dir: str) -> Optional[Project]:
        project = self._load(project_id)
        if not project:
            return None
        project.output_dir = output_dir
        self._save(project)
        return project

    def set_error(self, project_id: str, error: str) -> Optional[Project]:
        project = self._load(project_id)
        if not project:
            return None
        project.error = error
        project.status = ProjectStatus.FAILED
        self._save(project)
        return project

    def delete(self, project_id: str) -> bool:
        path = self._project_path(project_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def reset_steps(self, project_id: str, from_step: Optional[str] = None) -> Optional[Project]:
        project = self._load(project_id)
        if not project:
            return None

        step_order = ["script", "voice", "music", "visuals", "assembly", "thumbnail"]
        reset_from = 0

        if from_step and from_step in step_order:
            reset_from = step_order.index(from_step)

        for i, step_name in enumerate(step_order):
            if i >= reset_from:
                project.steps[step_name] = PipelineStep(name=project.steps[step_name].name)

        project.status = ProjectStatus.DRAFT
        project.error = None
        self._save(project)
        return project
