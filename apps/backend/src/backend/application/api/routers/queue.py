"""API router for task queue management."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.application.services.queue_service import QueueService
from backend.infrastructure.notification.notification_service import NotificationService
from backend.infrastructure.queue.executor import QueueExecutor

from ..deps import db_session
from ..utils import ensure_db

router = APIRouter(tags=["queue"], dependencies=[Depends(db_session)])


# Request/Response models
class AddTaskRequest(BaseModel):
    task_type: str
    config: Dict[str, Any]
    label: Optional[str] = None
    depends_on: Optional[int] = None


class TaskIdResponse(BaseModel):
    task_id: int


class StatusResponse(BaseModel):
    ok: bool
    message: Optional[str] = None


# Service instances (singleton for single-process dev)
_queue_service: Optional[QueueService] = None


def _get_queue_service() -> QueueService:
    """Get or create queue service instance."""
    global _queue_service
    if _queue_service is None:
        ensure_db()
        _queue_service = QueueService()
    return _queue_service


def _get_executor() -> QueueExecutor:
    """Get queue executor singleton instance."""
    ensure_db()
    return QueueExecutor.get_instance()


@router.post("/queue/add", response_model=TaskIdResponse)
def add_task(body: AddTaskRequest) -> TaskIdResponse:
    """Add a task to the queue.

    Request body:
    {
        "task_type": "benchmark" | "attrgen" | "pool_gen" | "balanced_gen",
        "config": {...},  # Task-specific configuration
        "label": "Optional label",
        "depends_on": 123  # Optional task ID (only attrgen->benchmark supported)
    }

    Returns:
        {"task_id": 123}
    """
    try:
        service = _get_queue_service()
        result = service.add_to_queue(
            task_type=body.task_type,
            config=body.config,
            label=body.label,
            depends_on=body.depends_on,
        )
        return TaskIdResponse(task_id=result["task_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/stats")
def get_queue_stats() -> Dict[str, Any]:
    """Get queue statistics.

    Returns:
        {
            "total": 10,
            "queued": 3,
            "waiting": 1,
            "running": 1,
            "done": 4,
            "failed": 1,
            "cancelled": 0,
            "skipped": 0,
            "executor_running": true,
            "executor_paused": false
        }
    """
    try:
        service = _get_queue_service()
        stats = service.get_queue_stats()

        # Add executor status
        executor = _get_executor()
        stats["executor_running"] = executor.is_running()
        stats["executor_paused"] = executor.is_paused()

        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue")
def list_queue(
    include_done: bool = False, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """List queue tasks.

    Query params:
    - include_done: Include completed/failed/cancelled tasks (default: false)
    - limit: Maximum number of tasks to return (default: all)

    Returns:
        List of task objects
    """
    try:
        service = _get_queue_service()
        return service.get_queue_status(include_done=include_done, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/{task_id}")
def get_task(task_id: int) -> Dict[str, Any]:
    """Get details of a specific task.

    Returns:
        Task object with full details
    """
    try:
        service = _get_queue_service()
        return service.get_task_by_id(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/queue/{task_id}", response_model=StatusResponse)
def remove_task(task_id: int) -> StatusResponse:
    """Remove a task from the queue.

    Only queued/waiting tasks can be removed.
    Tasks with dependents cannot be removed.

    Returns:
        {"ok": true, "message": "..."}
    """
    try:
        service = _get_queue_service()
        service.remove_from_queue(task_id)
        return StatusResponse(ok=True, message=f"Task #{task_id} removed")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/{task_id}/cancel", response_model=StatusResponse)
def cancel_task(task_id: int) -> StatusResponse:
    """Cancel a running or queued task.

    Also cancels all dependent tasks.

    Returns:
        {"ok": true, "message": "..."}
    """
    try:
        service = _get_queue_service()
        service.cancel_task(task_id)
        return StatusResponse(ok=True, message=f"Task #{task_id} cancelled")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/start", response_model=StatusResponse)
def start_queue() -> StatusResponse:
    """Start queue processing.

    Returns:
        {"ok": true, "message": "..."}
    """
    try:
        executor = _get_executor()
        if executor.is_running():
            return StatusResponse(ok=False, message="Queue already running")

        executor.start()

        # Send notification
        notification = NotificationService()
        notification.send_queue_started()

        return StatusResponse(ok=True, message="Queue started")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/stop", response_model=StatusResponse)
def stop_queue() -> StatusResponse:
    """Stop queue processing.

    Current task will complete, but no new tasks will be started.

    Returns:
        {"ok": true, "message": "..."}
    """
    try:
        executor = _get_executor()
        if not executor.is_running():
            return StatusResponse(ok=False, message="Queue not running")

        executor.stop()
        return StatusResponse(ok=True, message="Queue stopped")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/pause", response_model=StatusResponse)
def pause_queue() -> StatusResponse:
    """Pause queue processing.

    Current task will complete, but processing will pause before next task.

    Returns:
        {"ok": true, "message": "..."}
    """
    try:
        executor = _get_executor()
        if not executor.is_running():
            return StatusResponse(ok=False, message="Queue not running")

        if executor.is_paused():
            return StatusResponse(ok=False, message="Queue already paused")

        executor.pause()

        # Send notification
        notification = NotificationService()
        notification.send_queue_paused()

        return StatusResponse(ok=True, message="Queue paused")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queue/resume", response_model=StatusResponse)
def resume_queue() -> StatusResponse:
    """Resume queue processing.

    Returns:
        {"ok": true, "message": "..."}
    """
    try:
        executor = _get_executor()
        if not executor.is_running():
            return StatusResponse(ok=False, message="Queue not running")

        if not executor.is_paused():
            return StatusResponse(ok=False, message="Queue not paused")

        executor.resume()
        return StatusResponse(ok=True, message="Queue resumed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
