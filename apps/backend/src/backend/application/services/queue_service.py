"""Service for managing task queue orchestration."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import peewee as pw

from backend.infrastructure.storage.models import TaskQueue, utcnow

_LOG = logging.getLogger(__name__)


class QueueService:
    """Service for managing the task execution queue."""

    def add_to_queue(
        self,
        task_type: str,
        config: Dict[str, Any],
        label: Optional[str] = None,
        depends_on: Optional[int] = None,
    ) -> Dict[str, int]:
        """Add a task to the queue.

        Args:
            task_type: Type of task ('benchmark' | 'attrgen' | 'pool_gen' | 'balanced_gen')
            config: Task-specific configuration as dict
            label: Optional user-friendly label
            depends_on: Optional task ID this task depends on (only attrgen->benchmark supported)

        Returns:
            Dict with task_id

        Raises:
            ValueError: If dependency is invalid or would create a cycle
        """
        # Validate task_type
        valid_types = ("benchmark", "attrgen", "pool_gen", "balanced_gen")
        if task_type not in valid_types:
            raise ValueError(
                f"Invalid task_type '{task_type}'. Must be one of: {valid_types}"
            )

        # Validate dependency (hybrid approach: only attrgen -> benchmark)
        dependency_task = None
        if depends_on is not None:
            dependency_task = TaskQueue.get_or_none(TaskQueue.id == depends_on)
            if not dependency_task:
                raise ValueError(f"Dependency task #{depends_on} not found")

            # Hybrid approach: only allow attrgen -> benchmark dependencies
            if not (
                dependency_task.task_type == "attrgen" and task_type == "benchmark"
            ):
                raise ValueError(
                    f"Dependencies only supported for attrgen->benchmark. "
                    f"Got {dependency_task.task_type}->{task_type}"
                )

            # Check for cycles (simple: no transitive dependencies in hybrid mode)
            if dependency_task.depends_on is not None:
                raise ValueError(
                    "Transitive dependencies not supported in hybrid mode. "
                    f"Task #{depends_on} already depends on another task."
                )

        # Determine next position
        max_position = TaskQueue.select(pw.fn.MAX(TaskQueue.position)).scalar() or 0
        next_position = max_position + 1

        # Generate label if not provided
        if not label:
            label = self._generate_label(task_type, config)

        # Determine initial status
        initial_status = "waiting" if depends_on else "queued"

        # Create task
        task = TaskQueue.create(
            task_type=task_type,
            status=initial_status,
            position=next_position,
            config=json.dumps(config),
            depends_on=dependency_task,
            label=label,
        )

        return {"task_id": int(task.id)}

    def _generate_label(self, task_type: str, config: Dict[str, Any]) -> str:
        """Generate automatic label from task config.

        Args:
            task_type: The task type
            config: Task configuration

        Returns:
            Generated label string
        """
        if task_type == "benchmark":
            model = config.get("model_name", "?")
            ds_id = config.get("dataset_id", "?")
            rationale = " + Rationale" if config.get("include_rationale") else ""
            return f"Benchmark: {model} - DS#{ds_id}{rationale}"

        elif task_type == "attrgen":
            model = config.get("model_name", "?")
            ds_id = config.get("dataset_id", "?")
            return f"AttrGen: {model} - DS#{ds_id}"

        elif task_type == "pool_gen":
            n = config.get("n", "?")
            return f"Pool Generation: {n} personas"

        elif task_type == "balanced_gen":
            n = config.get("n", "?")
            ds_id = config.get("dataset_id", "?")
            return f"Balanced Gen: {n} personas - DS#{ds_id}"

        return f"Task: {task_type}"

    def _get_task_progress(
        self, task_type: str, run_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get progress info for a running task.

        Args:
            task_type: Type of task ('benchmark' or 'attrgen')
            run_id: The run ID (benchmark_run_id or attrgen_run_id)

        Returns:
            Dict with 'done', 'total', 'percent' or None if unavailable
        """
        try:
            if task_type == "benchmark":
                from backend.application.services.benchmark_service import (
                    BenchmarkService,
                )

                service = BenchmarkService()
                status = service.get_status(run_id)
                done = status.get("done", 0)
                total = status.get("total", 0)
                percent = (done / total * 100) if total > 0 else 0

                return {"done": done, "total": total, "percent": round(percent, 1)}

            elif task_type == "attrgen":
                from backend.infrastructure.persona.progress_tracker import (
                    get_progress as get_attrgen_progress,
                )

                progress = get_attrgen_progress(run_id)
                done = progress.get("done", 0)
                total = progress.get("total", 0)
                percent = (done / total * 100) if total > 0 else 0

                return {"done": done, "total": total, "percent": round(percent, 1)}

        except Exception:
            # Silently fail - progress is optional
            pass

        return None

    def get_queue_status(
        self, include_done: bool = False, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get current queue status.

        Args:
            include_done: Include completed tasks (default: False)
            limit: Maximum number of tasks to return (default: all)

        Returns:
            List of task status dicts
        """
        query = TaskQueue.select().order_by(TaskQueue.position)

        if not include_done:
            query = query.where(
                TaskQueue.status.not_in(["done", "failed", "cancelled", "skipped"])
            )

        if limit:
            query = query.limit(limit)

        tasks = []
        for task in query:
            task_dict = {
                "id": int(task.id),
                "task_type": str(task.task_type),
                "status": str(task.status),
                "position": int(task.position),
                "label": str(task.label) if task.label else None,
                "created_at": str(task.created_at),
                "started_at": str(task.started_at) if task.started_at else None,
                "finished_at": str(task.finished_at) if task.finished_at else None,
                "error": str(task.error) if task.error else None,
                "depends_on": int(task.depends_on.id) if task.depends_on else None,
                "result_run_id": task.result_run_id,
                "result_run_type": task.result_run_type,
            }

            # Add progress info for running tasks
            if task.status == "running" and task.result_run_id:
                task_dict["progress"] = self._get_task_progress(
                    task.task_type, task.result_run_id
                )

            # Parse config for preview
            try:
                task_dict["config"] = json.loads(task.config)
            except Exception:
                task_dict["config"] = {}

            tasks.append(task_dict)

        return tasks

    def remove_from_queue(self, task_id: int) -> Dict[str, bool]:
        """Remove a task from the queue.

        Args:
            task_id: The task ID to remove

        Returns:
            Dict with ok=True on success

        Raises:
            ValueError: If task not found or cannot be removed
        """
        task = TaskQueue.get_or_none(TaskQueue.id == task_id)
        if not task:
            raise ValueError(f"Task #{task_id} not found")

        # Can only remove queued/waiting tasks
        if task.status not in ("queued", "waiting"):
            raise ValueError(
                f"Cannot remove task with status '{task.status}'. "
                f"Only queued/waiting tasks can be removed."
            )

        # Check if other tasks depend on this one
        dependents = list(task.dependents)
        if dependents:
            dependent_ids = [d.id for d in dependents]
            raise ValueError(
                f"Cannot remove task #{task_id}. "
                f"Tasks {dependent_ids} depend on it. Remove them first."
            )

        task.delete_instance()
        return {"ok": True}

    def retry_task(self, task_id: int, delete_results: bool = False) -> Dict[str, Any]:
        """Retry a failed or cancelled task.

        Args:
            task_id: The task ID to retry
            delete_results: If True, delete all previous results. If False, resume from where it stopped.

        Returns:
            Dict with ok=True on success

        Raises:
            ValueError: If task not found or cannot be retried
        """
        task = TaskQueue.get_or_none(TaskQueue.id == task_id)
        if not task:
            raise ValueError(f"Task #{task_id} not found")

        # Can only retry failed/cancelled tasks
        if task.status not in ("failed", "cancelled"):
            raise ValueError(
                f"Cannot retry task with status '{task.status}'. "
                f"Only failed/cancelled tasks can be retried."
            )

        # Delete previous results if requested
        if delete_results and task.result_run_id:
            try:
                if task.task_type == "benchmark":
                    from backend.infrastructure.storage.models import (
                        BenchmarkResult,
                        BenchmarkRun,
                    )

                    # Delete results
                    BenchmarkResult.delete().where(
                        BenchmarkResult.benchmark_run_id == task.result_run_id
                    ).execute()

                    # Delete run record
                    BenchmarkRun.delete().where(
                        BenchmarkRun.id == task.result_run_id
                    ).execute()

                elif task.task_type == "attrgen":
                    from backend.infrastructure.storage.models import (
                        AttrGenRun,
                        GeneratedPersona,
                    )

                    # Delete generated personas
                    GeneratedPersona.delete().where(
                        GeneratedPersona.attr_generation_run_id == task.result_run_id
                    ).execute()

                    # Delete run record
                    AttrGenRun.delete().where(
                        AttrGenRun.id == task.result_run_id
                    ).execute()

                # Clear result_run_id since we deleted everything
                task.result_run_id = None
                task.result_run_type = None

            except Exception as e:
                raise ValueError(f"Failed to delete previous results: {e}")

        # Reset task to queued state
        task.status = "queued"
        task.error = None
        task.started_at = None
        task.finished_at = None

        # Clear vllm_base_url from config to force re-discovery on retry
        # This prevents reusing a failed/stale URL from previous attempt
        try:
            config = json.loads(task.config)
            if "vllm_base_url" in config:
                _LOG.info(
                    f"[QueueService] Clearing cached vllm_base_url from task #{task_id} config for retry"
                )
                config.pop("vllm_base_url", None)
                task.config = json.dumps(config)
        except Exception as e:
            _LOG.warning(
                f"[QueueService] Failed to clear vllm_base_url from config: {e}"
            )

        task.save()

        return {"ok": True}

    def cancel_task(self, task_id: int) -> Dict[str, bool]:
        """Cancel a running or queued task.

        Args:
            task_id: The task ID to cancel

        Returns:
            Dict with ok=True on success

        Raises:
            ValueError: If task not found or cannot be cancelled
        """
        task = TaskQueue.get_or_none(TaskQueue.id == task_id)
        if not task:
            raise ValueError(f"Task #{task_id} not found")

        if task.status in ("done", "failed", "cancelled", "skipped"):
            raise ValueError(
                f"Cannot cancel task with status '{task.status}'. Already completed."
            )

        # For running tasks, we set a cancellation flag
        # The executor will check this and stop gracefully
        if task.status == "running":
            # TODO: Implement cancellation mechanism for running tasks
            # For now, just mark as cancelled (executor will need to check this)
            task.status = "cancelled"
            task.finished_at = utcnow()
            task.error = "Cancelled by user"
            task.save()
        else:
            # For queued/waiting tasks, immediate cancellation
            task.status = "cancelled"
            task.finished_at = utcnow()
            task.error = "Cancelled by user"
            task.save()

            # Cascade cancel dependent tasks
            self._cascade_cancel(task)

        return {"ok": True}

    def _cascade_cancel(self, cancelled_task: TaskQueue) -> None:
        """Cancel all tasks that depend on the cancelled task.

        Args:
            cancelled_task: The cancelled task
        """
        dependents = (
            TaskQueue.select()
            .where(TaskQueue.depends_on == cancelled_task.id)
            .where(TaskQueue.status.in_(["queued", "waiting"]))
        )

        for dep in dependents:
            dep.status = "cancelled"
            dep.finished_at = utcnow()
            dep.error = f"Cancelled due to dependency #{cancelled_task.id} cancellation"
            dep.save()

            # Recursive cascade
            self._cascade_cancel(dep)

    def get_task_by_id(self, task_id: int) -> Dict[str, Any]:
        """Get detailed information about a specific task.

        Args:
            task_id: The task ID

        Returns:
            Task details dict

        Raises:
            ValueError: If task not found
        """
        task = TaskQueue.get_or_none(TaskQueue.id == task_id)
        if not task:
            raise ValueError(f"Task #{task_id} not found")

        task_dict = {
            "id": int(task.id),
            "task_type": str(task.task_type),
            "status": str(task.status),
            "position": int(task.position),
            "label": str(task.label) if task.label else None,
            "created_at": str(task.created_at),
            "started_at": str(task.started_at) if task.started_at else None,
            "finished_at": str(task.finished_at) if task.finished_at else None,
            "error": str(task.error) if task.error else None,
            "depends_on": int(task.depends_on.id) if task.depends_on else None,
            "result_run_id": task.result_run_id,
            "result_run_type": task.result_run_type,
        }

        try:
            task_dict["config"] = json.loads(task.config)
        except Exception:
            task_dict["config"] = {}

        return task_dict

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dict with queue stats
        """
        total = TaskQueue.select().count()
        queued = TaskQueue.select().where(TaskQueue.status == "queued").count()
        waiting = TaskQueue.select().where(TaskQueue.status == "waiting").count()
        running = TaskQueue.select().where(TaskQueue.status == "running").count()
        done = TaskQueue.select().where(TaskQueue.status == "done").count()
        failed = TaskQueue.select().where(TaskQueue.status == "failed").count()
        cancelled = TaskQueue.select().where(TaskQueue.status == "cancelled").count()
        skipped = TaskQueue.select().where(TaskQueue.status == "skipped").count()

        return {
            "total": total,
            "queued": queued,
            "waiting": waiting,
            "running": running,
            "done": done,
            "failed": failed,
            "cancelled": cancelled,
            "skipped": skipped,
        }
