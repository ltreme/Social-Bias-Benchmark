"""Queue executor for processing tasks in background."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

import peewee as pw

from backend.application.services.attrgen_service import AttrGenService
from backend.application.services.benchmark_service import BenchmarkService
from backend.infrastructure.storage.models import TaskQueue, utcnow

_LOG = logging.getLogger(__name__)


class QueueExecutor:
    """Background worker for processing task queue with dependency support."""

    _instance: Optional[QueueExecutor] = None
    _lock = threading.Lock()

    def __init__(self):
        """Initialize the queue executor."""
        self._running = False
        self._paused = False
        self._worker_thread: Optional[threading.Thread] = None
        self._benchmark_service = BenchmarkService()
        self._attrgen_service = AttrGenService()
        self._notification_callback: Optional[Callable] = None
        self._last_activity = time.time()
        self._heartbeat_interval = 300  # 5 minutes
        self._current_task_id: Optional[int] = None
        self._task_started_at = time.time()  # When current task started

    @classmethod
    def get_instance(cls) -> QueueExecutor:
        """Get singleton instance of queue executor.

        Returns:
            The global QueueExecutor instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def set_notification_callback(
        self, callback: Callable[[TaskQueue, bool, Optional[Exception]], None]
    ) -> None:
        """Set callback for task notifications.

        Args:
            callback: Function called with (task, success, error) after task completion
        """
        self._notification_callback = callback

    def start(self) -> bool:
        """Start the queue processing worker.

        Returns:
            True if started, False if already running
        """
        with self._lock:
            if self._running:
                _LOG.warning("Queue executor already running")
                return False

            # Cleanup orphaned tasks from previous runs (e.g. after restart)
            self._cleanup_orphaned_tasks()

            self._running = True
            self._paused = False
            self._worker_thread = threading.Thread(
                target=self._worker_loop, daemon=True, name="queue-executor"
            )
            self._worker_thread.start()
            _LOG.info("Queue executor started")
            return True

    def stop(self) -> bool:
        """Stop the queue processing worker.

        Returns:
            True if stopped, False if not running
        """
        with self._lock:
            if not self._running:
                return False

            self._running = False
            _LOG.info("Queue executor stopping...")
            return True

    def pause(self) -> bool:
        """Pause queue processing (current task continues).

        Returns:
            True if paused, False if not running
        """
        with self._lock:
            if not self._running:
                return False
            self._paused = True
            _LOG.info("Queue executor paused")
            return True

    def resume(self) -> bool:
        """Resume queue processing.

        Returns:
            True if resumed, False if not running or not paused
        """
        with self._lock:
            if not self._running or not self._paused:
                return False
            self._paused = False
            _LOG.info("Queue executor resumed")
            return True

    def is_running(self) -> bool:
        """Check if executor is running."""
        return self._running

    def is_paused(self) -> bool:
        """Check if executor is paused."""
        return self._paused

    def _cleanup_orphaned_tasks(self) -> None:
        """Reset tasks that were left in 'running' state from previous server restarts.

        This handles the case where the server crashed or was restarted while tasks
        were running. Those tasks will never complete and should be reset to 'queued'.
        """
        try:
            orphaned = TaskQueue.select().where(TaskQueue.status == "running")
            count = 0
            for task in orphaned:
                _LOG.warning(
                    f"[QueueExecutor] Resetting orphaned task #{task.id} "
                    f"(type={task.task_type}, label={task.label})"
                )
                task.status = "queued"
                task.error = "Task was reset after server restart"
                task.save()
                count += 1

            if count > 0:
                _LOG.info(f"[QueueExecutor] Reset {count} orphaned task(s)")
        except Exception as e:
            _LOG.error(f"[QueueExecutor] Failed to cleanup orphaned tasks: {e}")

    def _worker_loop(self) -> None:
        """Main worker loop - processes queue continuously."""
        _LOG.info("[QueueExecutor] Worker loop started")

        last_had_tasks = False

        while self._running:
            try:
                # Check if paused
                if self._paused:
                    time.sleep(5)
                    continue

                # Get next runnable task
                task = self._get_next_runnable_task()

                if task is None:
                    # Check if queue is now empty (transition from having tasks to none)
                    has_pending = self._has_pending_tasks()

                    if last_had_tasks and not has_pending:
                        # Queue just became empty - send notification
                        _LOG.info("[QueueExecutor] Queue is now empty")
                        if self._notification_callback:
                            try:
                                # Use a special marker to indicate queue empty
                                # We'll handle this in the notification service
                                from backend.infrastructure.notification.notification_service import (
                                    NotificationService,
                                )

                                ns = NotificationService()
                                ns.send_queue_empty()
                            except Exception as e:
                                _LOG.error(
                                    f"[QueueExecutor] Queue empty notification failed: {e}"
                                )

                    last_had_tasks = has_pending
                    # No tasks available, sleep and retry
                    time.sleep(5)
                    continue

                last_had_tasks = True

                # Execute the task
                self._execute_task(task)

            except Exception as e:
                _LOG.error(f"[QueueExecutor] Error in worker loop: {e}", exc_info=True)
                time.sleep(5)  # Prevent tight loop on persistent errors

        _LOG.info("[QueueExecutor] Worker loop stopped")

    def _get_next_runnable_task(self) -> Optional[TaskQueue]:
        """Find the next task that can be executed.

        A task is runnable if:
        1. Status is 'queued'
        2. No dependency OR dependency is 'done'
        3. No other task is currently running

        Returns:
            Next runnable task or None
        """
        # Check if there's already a running task
        running_count = TaskQueue.select().where(TaskQueue.status == "running").count()
        if running_count > 0:
            _LOG.debug(
                f"[QueueExecutor] {running_count} task(s) already running, waiting..."
            )
            return None

        # Get all queued tasks, ordered by position
        candidates = (
            TaskQueue.select()
            .where(TaskQueue.status == "queued")
            .order_by(TaskQueue.position)
        )

        for task in candidates:
            # No dependency - directly runnable
            if task.depends_on is None:
                return task

            # Check dependency status
            dep = task.depends_on
            if dep.status == "done":
                # Dependency completed - task is runnable
                return task
            elif dep.status in ("failed", "cancelled", "skipped"):
                # Dependency failed - skip this task
                _LOG.warning(
                    f"[QueueExecutor] Task #{task.id} dependency #{dep.id} "
                    f"failed with status '{dep.status}' - skipping task"
                )
                task.status = "skipped"
                task.error = (
                    f"Dependency #{dep.id} failed: {dep.error or 'No error message'}"
                )
                task.finished_at = utcnow()
                task.save()

                # Cascade skip to dependents
                self._cascade_skip(task)
            else:
                # Dependency still running/queued - set to waiting
                if task.status != "waiting":
                    task.status = "waiting"
                    task.save()

        # No runnable tasks found
        return None

    def _cascade_skip(self, failed_task: TaskQueue) -> None:
        """Recursively skip all tasks that depend on the failed task.

        Args:
            failed_task: The task that failed/was skipped
        """
        dependents = (
            TaskQueue.select()
            .where(TaskQueue.depends_on == failed_task.id)
            .where(TaskQueue.status.in_(["queued", "waiting"]))
        )

        for dep in dependents:
            _LOG.warning(
                f"[QueueExecutor] Cascade skipping task #{dep.id} "
                f"due to failed dependency #{failed_task.id}"
            )
            dep.status = "skipped"
            dep.error = f"Dependency chain broken (task #{failed_task.id} failed)"
            dep.finished_at = utcnow()
            dep.save()

            # Recursive cascade
            self._cascade_skip(dep)

    def _has_pending_tasks(self) -> bool:
        """Check if there are any pending tasks in the queue.

        Returns:
            True if there are tasks with status queued/waiting/running
        """
        count = (
            TaskQueue.select()
            .where(TaskQueue.status.in_(["queued", "waiting", "running"]))
            .count()
        )
        return count > 0

    def _execute_task(self, task: TaskQueue) -> None:
        """Execute a single task.

        Args:
            task: The task to execute
        """
        _LOG.info(
            f"[QueueExecutor] Executing task #{task.id} "
            f"(type={task.task_type}, label={task.label})"
        )

        # Mark as running and track current task
        task.status = "running"
        task.started_at = utcnow()
        task.save()

        self._current_task_id = task.id
        self._task_started_at = time.time()  # Track task start for elapsed time
        self._last_activity = time.time()  # Track last progress for stall detection

        try:
            # Parse config
            config = json.loads(task.config)

            # Inject dependency result if applicable (attrgen -> benchmark)
            if task.depends_on and task.depends_on.task_type == "attrgen":
                if task.depends_on.result_run_id:
                    config["attrgen_run_id"] = task.depends_on.result_run_id
                    _LOG.info(
                        f"[QueueExecutor] Injected attrgen_run_id={task.depends_on.result_run_id} "
                        f"from dependency #{task.depends_on.id}"
                    )

            # Execute based on task type
            if task.task_type == "benchmark":
                self._execute_benchmark(task, config)
            elif task.task_type == "attrgen":
                self._execute_attrgen(task, config)
            elif task.task_type == "pool_gen":
                self._execute_pool_gen(task, config)
            elif task.task_type == "balanced_gen":
                self._execute_balanced_gen(task, config)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")

            # Mark as done
            task.status = "done"
            task.finished_at = utcnow()
            task.save()

            _LOG.info(f"[QueueExecutor] Task #{task.id} completed successfully")

            # Notify
            if self._notification_callback:
                try:
                    self._notification_callback(task, True, None)
                except Exception as e:
                    _LOG.error(f"[QueueExecutor] Notification callback failed: {e}")

            # Check if waiting tasks can now run
            self._check_waiting_tasks(task)

        except Exception as e:
            _LOG.error(f"[QueueExecutor] Task #{task.id} failed: {e}", exc_info=True)

            # Mark as failed
            task.status = "failed"
            task.error = str(e)
            task.finished_at = utcnow()
            task.save()

            # Cascade skip dependents
            self._cascade_skip(task)

            # Notify
            if self._notification_callback:
                try:
                    self._notification_callback(task, False, e)
                except Exception as notify_error:
                    _LOG.error(
                        f"[QueueExecutor] Notification callback failed: {notify_error}"
                    )
        finally:
            # Clear current task tracking
            self._current_task_id = None
            self._last_activity = time.time()

    def _execute_benchmark(self, task: TaskQueue, config: Dict[str, Any]) -> None:
        """Execute a benchmark task.

        Args:
            task: The task record
            config: Benchmark configuration
        """
        _LOG.info(f"[QueueExecutor] Starting benchmark: {config}")

        result = self._benchmark_service.start_benchmark(config)
        run_id = result["run_id"]

        _LOG.info(f"[QueueExecutor] Benchmark started with run_id={run_id}")

        # Wait for completion
        self._wait_for_benchmark_completion(run_id)

        # Store result reference
        task.result_run_id = run_id
        task.result_run_type = "benchmark"
        task.save()

    def _execute_attrgen(self, task: TaskQueue, config: Dict[str, Any]) -> None:
        """Execute an attribute generation task.

        Args:
            task: The task record
            config: AttrGen configuration
        """
        _LOG.info(f"[QueueExecutor] Starting attrgen: {config}")

        result = self._attrgen_service.start_attr_generation(config)
        run_id = result["run_id"]

        _LOG.info(f"[QueueExecutor] AttrGen started with run_id={run_id}")

        # Wait for completion
        self._wait_for_attrgen_completion(run_id)

        # Store result reference
        task.result_run_id = run_id
        task.result_run_type = "attrgen"
        task.save()

    def _execute_pool_gen(self, task: TaskQueue, config: Dict[str, Any]) -> None:
        """Execute a pool generation task.

        Args:
            task: The task record
            config: Pool gen configuration
        """
        # TODO: Implement pool generation queue support
        raise NotImplementedError("Pool generation not yet supported in queue")

    def _execute_balanced_gen(self, task: TaskQueue, config: Dict[str, Any]) -> None:
        """Execute a balanced generation task.

        Args:
            task: The task record
            config: Balanced gen configuration
        """
        # TODO: Implement balanced generation queue support
        raise NotImplementedError("Balanced generation not yet supported in queue")

    def _wait_for_benchmark_completion(
        self, run_id: int, poll_interval: float = 5.0
    ) -> None:
        """Wait for a benchmark to complete.

        Args:
            run_id: The benchmark run ID
            poll_interval: Polling interval in seconds
        """
        _LOG.info(f"[QueueExecutor] Waiting for benchmark {run_id} to complete...")

        max_retries = 3
        retry_delay = 2.0
        last_heartbeat = time.time()
        stall_timeout = 600  # 10 minutes without progress = stall
        last_progress = time.time()
        last_done_count = 0

        _LOG.info(f"[QueueExecutor] Stall detection enabled: {stall_timeout}s timeout")

        while True:
            retry_count = 0
            status = None
            now = time.time()

            # Retry loop for connection errors
            while retry_count < max_retries:
                try:
                    query_start = time.time()
                    status = self._benchmark_service.get_status(run_id)
                    query_time = time.time() - query_start
                    if query_time > 2.0:
                        _LOG.warning(
                            f"[QueueExecutor] Slow get_status() query: {query_time:.2f}s "
                            f"(possible DB contention)"
                        )
                    break  # Success, exit retry loop
                except Exception as e:
                    error_str = str(e).lower()
                    # Check if it's a connection pool error
                    if "max" in error_str and "connection" in error_str:
                        retry_count += 1
                        if retry_count < max_retries:
                            _LOG.warning(
                                f"[QueueExecutor] Connection pool exhausted (attempt {retry_count}/{max_retries}), "
                                f"retrying in {retry_delay}s..."
                            )
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            _LOG.error(
                                f"[QueueExecutor] Connection pool exhausted after {max_retries} retries"
                            )
                            raise RuntimeError(
                                f"Database connection pool exhausted (critical error): {e}"
                            ) from e
                    else:
                        # Not a connection error, re-raise immediately
                        raise

            if status is None:
                raise RuntimeError("Failed to get benchmark status after retries")

            # Check for stall - no progress for stall_timeout seconds
            done = status.get("done", 0)
            total = status.get("total", 0)
            check_time = time.time()  # Get current time for stall check
            time_since_progress = check_time - last_progress

            if done > last_done_count:
                # Progress made - reset stall timer
                _LOG.debug(
                    f"[QueueExecutor] Benchmark {run_id} progress: {last_done_count} -> {done}/{total}"
                )
                last_progress = check_time
                last_done_count = done
                self._last_activity = check_time  # Update activity timestamp
            elif time_since_progress > stall_timeout:
                # No progress for too long - likely stalled
                _LOG.error(
                    f"[QueueExecutor] Benchmark {run_id} STALLED: No progress for {int(time_since_progress)}s "
                    f"(stuck at {done}/{total}). Possible causes: vLLM timeout, cache pollution, OOM. "
                    f"Last vLLM request likely timed out or never returned."
                )
                raise RuntimeError(
                    f"Benchmark stalled: No progress for {int(time_since_progress)}s at {done}/{total} items. "
                    f"Check vLLM server logs for timeout/OOM errors."
                )

            # Heartbeat logging (after progress check so we have current done count)
            if check_time - last_heartbeat >= self._heartbeat_interval:
                elapsed_total = int(check_time - self._task_started_at)
                elapsed_since_progress = int(time_since_progress)
                pct = (100.0 * done / total) if total > 0 else 0.0
                _LOG.info(
                    f"[QueueExecutor] Heartbeat: Task #{self._current_task_id} still running "
                    f"(benchmark run_id={run_id}, total_elapsed={elapsed_total}s, "
                    f"since_progress={elapsed_since_progress}s, progress={done}/{total} ({pct:.1f}%))"
                )
                last_heartbeat = check_time

            if status.get("status") in ("done", "failed", "cancelled"):
                if status.get("status") == "failed":
                    error = status.get("error", "Unknown error")
                    raise RuntimeError(f"Benchmark failed: {error}")
                if status.get("status") == "cancelled":
                    raise RuntimeError("Benchmark was cancelled")

                _LOG.info(f"[QueueExecutor] Benchmark {run_id} completed")
                return

            time.sleep(poll_interval)

    def _wait_for_attrgen_completion(
        self, run_id: int, poll_interval: float = 5.0
    ) -> None:
        """Wait for an attribute generation run to complete.

        Args:
            run_id: The attrgen run ID
            poll_interval: Polling interval in seconds
        """
        _LOG.info(f"[QueueExecutor] Waiting for attrgen {run_id} to complete...")

        max_retries = 3
        retry_delay = 2.0
        last_heartbeat = time.time()
        stall_timeout = 600  # 10 minutes without progress = stall
        last_progress = time.time()
        last_done_count = 0

        _LOG.info(f"[QueueExecutor] Stall detection enabled: {stall_timeout}s timeout")

        while True:
            retry_count = 0
            status = None
            now = time.time()

            # Retry loop for connection errors
            while retry_count < max_retries:
                try:
                    status = self._attrgen_service.get_run_status(run_id)
                    break  # Success, exit retry loop
                except Exception as e:
                    error_str = str(e).lower()
                    # Check if it's a connection pool error
                    if "max" in error_str and "connection" in error_str:
                        retry_count += 1
                        if retry_count < max_retries:
                            _LOG.warning(
                                f"[QueueExecutor] Connection pool exhausted (attempt {retry_count}/{max_retries}), "
                                f"retrying in {retry_delay}s..."
                            )
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            _LOG.error(
                                f"[QueueExecutor] Connection pool exhausted after {max_retries} retries"
                            )
                            raise RuntimeError(
                                f"Database connection pool exhausted (critical error): {e}"
                            ) from e
                    else:
                        # Not a connection error, re-raise immediately
                        raise

            if status is None:
                raise RuntimeError("Failed to get attrgen status after retries")

            # Check for stall - no progress for stall_timeout seconds
            done = status.get("done", 0)
            total = status.get("total", 0)
            check_time = time.time()  # Get current time for stall check
            time_since_progress = check_time - last_progress

            if done > last_done_count:
                # Progress made - reset stall timer
                _LOG.debug(
                    f"[QueueExecutor] AttrGen {run_id} progress: {last_done_count} -> {done}/{total}"
                )
                last_progress = check_time
                last_done_count = done
                self._last_activity = check_time  # Update activity timestamp
            elif time_since_progress > stall_timeout:
                # No progress for too long - likely stalled
                _LOG.error(
                    f"[QueueExecutor] AttrGen {run_id} STALLED: No progress for {int(time_since_progress)}s "
                    f"(stuck at {done}/{total}). Possible causes: vLLM timeout, cache pollution, OOM. "
                    f"Last vLLM request likely timed out or never returned."
                )
                raise RuntimeError(
                    f"AttrGen stalled: No progress for {int(time_since_progress)}s at {done}/{total} items. "
                    f"Check vLLM server logs for timeout/OOM errors."
                )

            # Heartbeat logging (after progress check so we have current done count)
            if check_time - last_heartbeat >= self._heartbeat_interval:
                elapsed_total = int(check_time - self._task_started_at)
                elapsed_since_progress = int(time_since_progress)
                pct = (100.0 * done / total) if total > 0 else 0.0
                _LOG.info(
                    f"[QueueExecutor] Heartbeat: Task #{self._current_task_id} still running "
                    f"(attrgen run_id={run_id}, total_elapsed={elapsed_total}s, "
                    f"since_progress={elapsed_since_progress}s, progress={done}/{total} ({pct:.1f}%))"
                )
                last_heartbeat = check_time

            if status.get("status") in ("done", "failed"):
                if status.get("status") == "failed":
                    error = status.get("error", "Unknown error")
                    raise RuntimeError(f"AttrGen failed: {error}")

                _LOG.info(f"[QueueExecutor] AttrGen {run_id} completed")
                return

            time.sleep(poll_interval)

    def _check_waiting_tasks(self, completed_task: TaskQueue) -> None:
        """Check if any waiting tasks can now be queued.

        Args:
            completed_task: The task that just completed
        """
        waiting_tasks = (
            TaskQueue.select()
            .where(TaskQueue.status == "waiting")
            .where(TaskQueue.depends_on == completed_task.id)
        )

        for task in waiting_tasks:
            _LOG.info(
                f"[QueueExecutor] Task #{task.id} dependency satisfied, "
                f"moving to queued status"
            )
            task.status = "queued"
            task.save()
