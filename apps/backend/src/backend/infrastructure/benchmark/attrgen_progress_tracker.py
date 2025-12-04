"""Progress tracking for attribute generation jobs."""

from __future__ import annotations

from typing import Any, Dict, Protocol


class ProgressInfo:
    """Progress information for an attribute generation run."""

    def __init__(
        self,
        status: str = "unknown",
        total: int = 0,
        done: int = 0,
        error: str | None = None,
        **extra: Any,
    ):
        """Initialize progress info.

        Args:
            status: Job status ('queued', 'running', 'done', 'failed', 'unknown')
            total: Total number of items to process
            done: Number of items completed
            error: Error message if failed
            **extra: Additional metadata (llm, vllm_base_url, skip_completed, etc.)
        """
        self.status = status
        self.total = total
        self.done = done
        self.error = error
        self.extra = extra

    @property
    def pct(self) -> float:
        """Calculate completion percentage."""
        return (100.0 * self.done / self.total) if self.total else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "status": self.status,
            "total": self.total,
            "done": self.done,
            "pct": self.pct,
            "error": self.error,
            **self.extra,
        }


class ProgressTracker(Protocol):
    """Protocol for progress tracking implementations."""

    def get_progress(self, run_id: int) -> ProgressInfo | None:
        """Get progress information for a run.

        Args:
            run_id: The run ID

        Returns:
            ProgressInfo or None if not tracked
        """
        ...

    def set_progress(self, run_id: int, progress: ProgressInfo) -> None:
        """Set progress information for a run.

        Args:
            run_id: The run ID
            progress: Progress information to store
        """
        ...

    def update_progress(self, run_id: int, **updates: Any) -> None:
        """Update specific fields of progress information.

        Args:
            run_id: The run ID
            **updates: Fields to update
        """
        ...

    def delete_progress(self, run_id: int) -> None:
        """Delete progress tracking for a run.

        Args:
            run_id: The run ID
        """
        ...


class InMemoryProgressTracker:
    """In-memory progress tracker for single-process development.

    For multi-process/production, replace with Redis-based implementation.
    """

    def __init__(self):
        """Initialize the tracker."""
        self._storage: Dict[int, Dict[str, Any]] = {}

    def get_progress(self, run_id: int) -> ProgressInfo | None:
        """Get progress information for a run."""
        data = self._storage.get(run_id)
        if not data:
            return None
        return ProgressInfo(**data)

    def set_progress(self, run_id: int, progress: ProgressInfo) -> None:
        """Set progress information for a run."""
        self._storage[run_id] = progress.to_dict()

    def update_progress(self, run_id: int, **updates: Any) -> None:
        """Update specific fields of progress information."""
        if run_id not in self._storage:
            self._storage[run_id] = {}
        self._storage[run_id].update(updates)

    def delete_progress(self, run_id: int) -> None:
        """Delete progress tracking for a run."""
        self._storage.pop(run_id, None)

    def compute_and_update_progress(
        self, run_id: int, total: int, done: int
    ) -> ProgressInfo:
        """Compute progress and update storage.

        Args:
            run_id: The run ID
            total: Total items
            done: Completed items

        Returns:
            Updated ProgressInfo
        """
        current = self.get_progress(run_id) or ProgressInfo()
        self.update_progress(run_id, total=total, done=done)
        return self.get_progress(run_id) or ProgressInfo()
