"""Progress tracking for dataset generation and deletion jobs."""

from __future__ import annotations

from typing import Any, Dict


class DatasetJobProgress:
    """Progress information for dataset jobs (pool, balanced, delete)."""

    def __init__(
        self,
        status: str = "unknown",
        total: int = 0,
        done: int = 0,
        phase: str | None = None,
        eta_sec: int | None = None,
        started_at: float | None = None,
        dataset_id: int | None = None,
        error: str | None = None,
        **extra: Any,
    ):
        """Initialize job progress.

        Args:
            status: Job status ('queued', 'sampling', 'inserting', 'selecting', 'deleting', 'done', 'failed', 'unknown')
            total: Total number of items to process
            done: Number of items completed
            phase: Current phase of the job
            eta_sec: Estimated time to completion in seconds
            started_at: Timestamp when job started
            dataset_id: Created dataset ID (for completed jobs)
            error: Error message if failed
            **extra: Additional metadata
        """
        self.status = status
        self.total = total
        self.done = done
        self.phase = phase
        self.eta_sec = eta_sec
        self.started_at = started_at
        self.dataset_id = dataset_id
        self.error = error
        self.extra = extra

    @property
    def pct(self) -> float:
        """Calculate completion percentage."""
        return (100.0 * self.done / self.total) if self.total else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "status": self.status,
            "total": self.total,
            "done": self.done,
            "pct": self.pct,
        }
        if self.phase is not None:
            result["phase"] = self.phase
        if self.eta_sec is not None:
            result["eta_sec"] = self.eta_sec
        if self.started_at is not None:
            result["started_at"] = self.started_at
        if self.dataset_id is not None:
            result["dataset_id"] = self.dataset_id
        if self.error is not None:
            result["error"] = self.error
        result.update(self.extra)
        return result


class DatasetProgressTracker:
    """In-memory progress tracker for dataset jobs.

    For multi-process/production, replace with Redis-based implementation.
    """

    def __init__(self):
        """Initialize the tracker."""
        self._pool_storage: Dict[int, Dict[str, Any]] = {}
        self._balanced_storage: Dict[int, Dict[str, Any]] = {}
        self._delete_storage: Dict[int, Dict[str, Any]] = {}
        self._pool_job_counter = 0
        self._balanced_job_counter = 0
        self._delete_job_counter = 0

    # Pool generation tracking
    def create_pool_job(self, **initial_data: Any) -> int:
        """Create a new pool generation job and return its ID."""
        self._pool_job_counter += 1
        job_id = self._pool_job_counter
        self._pool_storage[job_id] = initial_data
        return job_id

    def get_pool_progress(self, job_id: int) -> DatasetJobProgress | None:
        """Get progress for a pool generation job."""
        data = self._pool_storage.get(job_id)
        if not data:
            return None
        return DatasetJobProgress(**data)

    def update_pool_progress(self, job_id: int, **updates: Any) -> None:
        """Update pool generation job progress."""
        if job_id not in self._pool_storage:
            self._pool_storage[job_id] = {}
        self._pool_storage[job_id].update(updates)

    # Balanced dataset tracking
    def create_balanced_job(self, **initial_data: Any) -> int:
        """Create a new balanced dataset job and return its ID."""
        self._balanced_job_counter += 1
        job_id = self._balanced_job_counter
        self._balanced_storage[job_id] = initial_data
        return job_id

    def get_balanced_progress(self, job_id: int) -> DatasetJobProgress | None:
        """Get progress for a balanced dataset job."""
        data = self._balanced_storage.get(job_id)
        if not data:
            return None
        return DatasetJobProgress(**data)

    def update_balanced_progress(self, job_id: int, **updates: Any) -> None:
        """Update balanced dataset job progress."""
        if job_id not in self._balanced_storage:
            self._balanced_storage[job_id] = {}
        self._balanced_storage[job_id].update(updates)

    # Dataset deletion tracking
    def create_delete_job(self, **initial_data: Any) -> int:
        """Create a new dataset deletion job and return its ID."""
        self._delete_job_counter += 1
        job_id = self._delete_job_counter
        self._delete_storage[job_id] = initial_data
        return job_id

    def get_delete_progress(self, job_id: int) -> DatasetJobProgress | None:
        """Get progress for a dataset deletion job."""
        data = self._delete_storage.get(job_id)
        if not data:
            return None
        return DatasetJobProgress(**data)

    def update_delete_progress(self, job_id: int, **updates: Any) -> None:
        """Update dataset deletion job progress."""
        if job_id not in self._delete_storage:
            self._delete_storage[job_id] = {}
        self._delete_storage[job_id].update(updates)
