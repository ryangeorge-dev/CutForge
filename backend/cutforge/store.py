import json
import os
import re
import threading
from pathlib import Path
from uuid import uuid4

from .models import Project


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def directory(self, identifier: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise ValueError("Invalid project ID")
        path = (self.root / identifier).resolve()
        if path.parent != self.root:
            raise ValueError("Project path escapes workspace")
        return path

    def load(self, identifier: str) -> Project:
        path = self.directory(identifier) / "project.json"
        if path.is_symlink():
            raise ValueError("Project files must not be symbolic links")
        project = Project.model_validate_json(path.read_text(encoding="utf-8"))
        if project.id != identifier:
            raise ValueError("Project JSON ID does not match its workspace directory.")
        return project

    def save(self, project: Project) -> None:
        project.schema_version = 2
        directory = self.directory(project.id)
        directory.mkdir(exist_ok=True)
        temp = directory / f".{uuid4().hex}.tmp"
        with temp.open("w", encoding="utf-8") as file:
            file.write(project.model_dump_json(indent=2))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, directory / "project.json")

    def media(self, project: Project) -> Path:
        directory = self.directory(project.id)
        path = (directory / project.media_name).resolve()
        if path.parent != directory or path.name != project.media_name:
            raise ValueError("Invalid media path")
        if not path.is_file():
            raise ValueError("Workspace media is missing. Restore it at its original workspace path.")
        if path.stat().st_size != project.media_size:
            raise ValueError("Workspace media size changed. Restore the original imported copy.")
        return path

    def list(self) -> list[dict]:
        result = []
        for path in self.root.glob("*/project.json"):
            try:
                p = self.load(path.parent.name)
                result.append({"id": p.id, "name": p.name, "revision": p.revision})
            except (ValueError, OSError, json.JSONDecodeError):
                continue
        return result
