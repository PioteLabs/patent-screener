"""In-memory store for a screening run's live progress, polled by the web UI.

This is a single-user local app, so a plain dict + lock is enough -- no need
for a task queue. Jobs are lost on server restart, but by then the result is
already saved to history.py's sqlite store.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from pipeline import PipelineResult

# (phase, percent width of the overall bar that phase accounts for)
PHASE_WEIGHTS: list[tuple[str, int]] = [
    ("extract", 10),
    ("search", 15),
    ("compare", 65),
    ("finalize", 10),
]
PHASE_ORDER = [phase for phase, _ in PHASE_WEIGHTS]
PHASE_WEIGHT_BY_NAME = dict(PHASE_WEIGHTS)


@dataclass
class Job:
    id: str
    idea_text: str
    status: str = "running"  # running | done | error
    phase: str = "extract"
    completed: int = 0
    total: int = 1
    log: list[str] = field(default_factory=list)
    result: PipelineResult | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def add_log(self, message: str) -> None:
        with self._lock:
            self.log.append(message)

    def set_progress(self, phase: str, completed: int, total: int) -> None:
        with self._lock:
            self.phase = phase
            self.completed = completed
            self.total = total

    def mark_done(self, result: PipelineResult) -> None:
        with self._lock:
            self.result = result
            self.status = "done"

    def mark_error(self, error: str) -> None:
        with self._lock:
            self.error = error
            self.status = "error"

    def percent(self) -> int:
        with self._lock:
            if self.status == "done":
                return 100
            phase_index = PHASE_ORDER.index(self.phase) if self.phase in PHASE_ORDER else 0
            base = sum(weight for _, weight in PHASE_WEIGHTS[:phase_index])
            weight = PHASE_WEIGHT_BY_NAME.get(self.phase, 0)
            fraction = (self.completed / self.total) if self.total else 1.0
            return min(99, int(base + fraction * weight))

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "status": self.status,
                "phase": self.phase,
                "percent": self.percent(),
                "log": list(self.log),
                "error": self.error,
            }


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()


def create_job(idea_text: str) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], idea_text=idea_text)
    with _jobs_lock:
        _jobs[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    with _jobs_lock:
        return _jobs.get(job_id)
