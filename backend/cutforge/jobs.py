"""Bounded local worker pool. Job status survives restarts; work does not resume."""
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4


class Jobs:
    def __init__(self, root: Path):
        self.path = root / "jobs.json"
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cutforge")
        self.items = json.loads(self.path.read_text()) if self.path.exists() else {}
        for job in self.items.values():
            if job["status"] in {"queued", "running"}:
                job.update(status="failed", error="CutForge stopped before this job completed. Run it again; imported media was preserved.")
        self.persist()

    def persist(self):
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.items, indent=2), encoding="utf-8")
        os.replace(temp, self.path)

    def busy(self, project_id: str) -> bool:
        with self.lock:
            return any(j["project_id"] == project_id and j["status"] in {"queued", "running"} for j in self.items.values())

    def submit(self, project_id: str, kind: str, work) -> dict:
        with self.lock:
            if sum(j["status"] in {"queued", "running"} for j in self.items.values()) >= 4:
                raise ValueError("Four media jobs are already queued. Wait for one to finish.")
            job = dict(id=uuid4().hex, project_id=project_id, kind=kind, status="queued", error=None)
            self.items[job["id"]] = job
            self.persist()

        def execute():
            with self.lock:
                job["status"] = "running"
                self.persist()
            try:
                work()
            except Exception as exc:
                with self.lock:
                    job.update(status="failed", error=str(exc))
            else:
                with self.lock:
                    job["status"] = "completed"
            finally:
                with self.lock:
                    self.persist()

        self.pool.submit(execute)
        return job.copy()

    def get(self, identifier: str):
        with self.lock:
            return self.items[identifier].copy()
