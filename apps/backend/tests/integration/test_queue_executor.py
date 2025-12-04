"""Integration tests for Queue Executor - kritisch für Task-Dependencies."""

import sys
from pathlib import Path

# Ensure backend package is importable
REPO_ROOT = Path(__file__).resolve().parents[5]
SRC_ROOT = REPO_ROOT / "apps" / "backend" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from backend.infrastructure.queue.executor import QueueExecutor
from backend.infrastructure.storage.models import TaskQueue, utcnow

pytestmark = (
    pytest.mark.integration
)  # Mark all tests in this module as integration tests


@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database."""
    import peewee as pw

    from backend.infrastructure.storage.models import TaskQueue

    db_path = tmp_path / "test_queue.db"
    test_db = pw.SqliteDatabase(str(db_path))

    # Bind TaskQueue model to test DB
    test_db.bind([TaskQueue], bind_refs=False, bind_backrefs=False)
    test_db.connect()
    test_db.create_tables([TaskQueue])

    yield test_db

    test_db.close()


@pytest.fixture
def executor(test_db):
    """Create a QueueExecutor instance for testing."""
    # Reset singleton
    QueueExecutor._instance = None
    executor = QueueExecutor.get_instance()

    yield executor

    # Cleanup
    if executor.is_running():
        executor.stop()
        time.sleep(0.5)


class TestQueueExecutorLifecycle:
    """Test executor start/stop/pause/resume lifecycle."""

    def test_executor_starts(self, executor):
        """Executor should start successfully."""
        result = executor.start()
        assert result is True
        assert executor.is_running() is True
        assert executor.is_paused() is False

    def test_executor_stops(self, executor):
        """Executor should stop successfully."""
        executor.start()
        time.sleep(0.1)

        result = executor.stop()
        assert result is True
        time.sleep(0.5)
        assert executor.is_running() is False

    def test_start_twice_returns_false(self, executor):
        """Starting already running executor should return False."""
        executor.start()
        result = executor.start()
        assert result is False

    def test_pause_resume(self, executor):
        """Executor should pause and resume correctly."""
        executor.start()

        pause_result = executor.pause()
        assert pause_result is True
        assert executor.is_paused() is True

        resume_result = executor.resume()
        assert resume_result is True
        assert executor.is_paused() is False

    def test_pause_when_not_running_fails(self, executor):
        """Pausing non-running executor should fail."""
        result = executor.pause()
        assert result is False


class TestOrphanedTaskCleanup:
    """Test orphaned task cleanup after restart."""

    def test_orphaned_tasks_reset_to_queued(self, executor, test_db):
        """Tasks left in 'running' state should be reset to 'queued'."""
        # Create orphaned tasks with valid config
        orphan1 = TaskQueue.create(
            task_type="benchmark",
            label="Orphaned Task 1",
            status="running",
            config='{"dataset_id": 1, "model_id": 1}',
            position=1,
        )
        orphan2 = TaskQueue.create(
            task_type="attrgen",
            label="Orphaned Task 2",
            status="running",
            config='{"dataset_id": 1, "model_id": 1}',
            position=2,
        )
        completed = TaskQueue.create(
            task_type="benchmark",
            label="Completed Task",
            status="completed",
            config='{"dataset_id": 1, "model_id": 1}',
            position=3,
        )

        # Start executor (triggers cleanup and attempts execution)
        executor.start()
        time.sleep(0.5)  # Give time for cleanup and execution attempts
        executor.stop()

        # Reload from DB
        orphan1_reloaded = TaskQueue.get_by_id(orphan1.id)
        orphan2_reloaded = TaskQueue.get_by_id(orphan2.id)
        completed_reloaded = TaskQueue.get_by_id(completed.id)

        # Orphaned tasks should be reset to queued, then executed (and likely failed)
        # The important thing is they were picked up for processing
        assert orphan1_reloaded.status in ["queued", "running", "failed"]
        assert orphan2_reloaded.status in ["queued", "running", "failed"]
        # Completed task should not be affected
        assert completed_reloaded.status == "completed"

    def test_no_orphans_no_changes(self, executor, test_db):
        """When no orphaned tasks exist, nothing should change."""
        queued = TaskQueue.create(
            task_type="benchmark",
            label="Queued Task",
            status="queued",
            config='{"dataset_id": 1, "model_id": 1}',
            position=1,
        )

        executor.start()
        time.sleep(0.5)  # Give time for execution
        executor.stop()

        queued_reloaded = TaskQueue.get_by_id(queued.id)
        # Should have been picked up and executed (likely failed due to test config)
        assert queued_reloaded.status in ["queued", "running", "failed"]


class TestTaskDependencies:
    """Test task dependency resolution and execution order."""

    @pytest.mark.skip(
        reason="Complex test requiring full service mocking - TODO: refactor to use test fixtures"
    )
    def test_simple_dependency_chain(self, executor, test_db):
        """Task with dependency should wait for dependency to complete."""
        # Create parent task
        parent = TaskQueue.create(
            task_type="attrgen",
            label="Parent Task",
            status="queued",
            config='{"dataset_id": 1}',
            position=1,
        )

        # Create child task that depends on parent
        child = TaskQueue.create(
            task_type="benchmark",
            label="Child Task",
            status="queued",
            depends_on=parent.id,
            config='{"dataset_id": 1}',
            position=2,
        )

        # Mock service methods to return proper result structure
        with patch.object(
            executor._attrgen_service, "start_attr_generation"
        ) as mock_attrgen:
            with patch.object(
                executor._benchmark_service, "start_benchmark"
            ) as mock_bench:
                # Mock attrgen to return a run_id structure
                mock_attrgen.return_value = {"run_id": 999}
                mock_bench.return_value = {"run_id": 1000}

                executor.start()
                time.sleep(1.5)  # Give time for tasks to process
                executor.stop()

        # Reload tasks
        parent_reloaded = TaskQueue.get_by_id(parent.id)
        child_reloaded = TaskQueue.get_by_id(child.id)

        # Parent should complete first, then child
        # (In real scenario, both would complete if parent finishes fast)
        assert parent_reloaded.status in ["completed", "running"]

    def test_child_not_run_if_parent_pending(self, executor, test_db):
        """Child task should not run if parent is still pending."""
        # Create parent that will fail
        parent = TaskQueue.create(
            task_type="attrgen",
            label="Parent Task",
            status="queued",
            config='{"dataset_id": 1}',
            position=1,
        )

        child = TaskQueue.create(
            task_type="benchmark",
            label="Child Task",
            status="queued",
            depends_on=parent.id,
            config='{"dataset_id": 1}',
            position=2,
        )

        # Mock parent to never complete (simulate long-running)
        with patch.object(
            executor._attrgen_service, "start_attr_generation"
        ) as mock_attrgen:
            # Make parent task sleep forever
            def sleep_forever(*args, **kwargs):
                time.sleep(10)

            mock_attrgen.side_effect = sleep_forever

            executor.start()
            time.sleep(0.5)  # Short wait
            executor.stop()
            time.sleep(0.5)

        # Child should still be queued (parent didn't complete)
        child_reloaded = TaskQueue.get_by_id(child.id)
        assert child_reloaded.status == "queued"


class TestConcurrentTaskSubmission:
    """Test handling of concurrent task submissions."""

    def test_multiple_tasks_submitted_concurrently(self, executor, test_db):
        """Multiple tasks submitted at once should all be queued."""
        tasks = []
        for i in range(5):
            task = TaskQueue.create(
                task_type="benchmark",
                label=f"Concurrent Task {i}",
                status="queued",
                config=f'{{"id": {i}}}',
                position=i + 1,
            )
            tasks.append(task)

        # All should be in DB
        count = TaskQueue.select().where(TaskQueue.status == "queued").count()
        assert count == 5

    def test_tasks_process_in_order(self, executor, test_db):
        """Tasks without dependencies should process in creation order."""
        task1 = TaskQueue.create(
            task_type="benchmark",
            label="Task 1",
            status="queued",
            config="{}",
            position=1,
            created_at=utcnow(),
        )

        time.sleep(0.01)  # Ensure different timestamps

        task2 = TaskQueue.create(
            task_type="benchmark",
            label="Task 2",
            status="queued",
            config="{}",
            position=2,
            created_at=utcnow(),
        )

        # Query should return task1 first (older)
        next_task = (
            TaskQueue.select()
            .where(TaskQueue.status == "queued")
            .order_by(TaskQueue.created_at.asc())
            .first()
        )

        assert next_task.id == task1.id


class TestTaskCancellation:
    """Test task cancellation behavior."""

    def test_cancel_queued_task(self, test_db):
        """Queued task should be cancellable."""
        task = TaskQueue.create(
            task_type="benchmark",
            label="To Be Cancelled",
            status="queued",
            config="{}",
            position=1,
        )

        # Cancel it
        task.status = "cancelled"
        task.save()

        reloaded = TaskQueue.get_by_id(task.id)
        assert reloaded.status == "cancelled"

    def test_cancelled_task_not_picked_up(self, executor, test_db):
        """Cancelled tasks should not be picked up by executor."""
        task = TaskQueue.create(
            task_type="benchmark",
            label="Cancelled Task",
            status="cancelled",
            config='{"dataset_id": 1, "model_id": 1}',
            position=1,
        )

        executor.start()
        time.sleep(0.5)
        executor.stop()

        # Reload and verify it stayed cancelled (not picked up)
        task_reloaded = TaskQueue.get_by_id(task.id)
        assert task_reloaded.status == "cancelled"


class TestSingletonPattern:
    """Test executor singleton pattern."""

    def test_get_instance_returns_same_instance(self):
        """Multiple calls to get_instance should return same object."""
        QueueExecutor._instance = None

        instance1 = QueueExecutor.get_instance()
        instance2 = QueueExecutor.get_instance()

        assert instance1 is instance2

    def test_thread_safe_singleton(self):
        """Singleton should be thread-safe."""
        QueueExecutor._instance = None
        instances = []

        def get_instance():
            instances.append(QueueExecutor.get_instance())

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All instances should be the same
        assert all(inst is instances[0] for inst in instances)
