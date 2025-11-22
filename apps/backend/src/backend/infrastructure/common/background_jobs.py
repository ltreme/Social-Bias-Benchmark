"""Background job execution utilities."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Protocol


class BackgroundJobRunner(Protocol):
    """Protocol for background job execution."""

    def run_async(self, target: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Run a function asynchronously in the background.

        Args:
            target: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        """
        ...


class ThreadedJobRunner:
    """Thread-based background job runner for single-process development.

    For multi-process/production, replace with Celery, RQ, or similar.
    """

    def run_async(self, target: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Run a function asynchronously in a daemon thread.

        Args:
            target: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        """
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        thread.start()


class PeriodicPoller:
    """Periodic polling utility for monitoring background jobs."""

    def __init__(
        self,
        target: Callable[[], bool],
        interval: float = 2.0,
        condition: Callable[[], bool] | None = None,
    ):
        """Initialize the poller.

        Args:
            target: Function to call periodically (should return True to continue)
            interval: Polling interval in seconds
            condition: Optional function to check if polling should continue
        """
        self.target = target
        self.interval = interval
        self.condition = condition or (lambda: True)

    def run(self) -> None:
        """Run the polling loop."""
        try:
            while self.condition():
                should_continue = self.target()
                if not should_continue:
                    break
                time.sleep(self.interval)
        except Exception:
            # Silently stop on any error
            pass

    def run_async(self, runner: BackgroundJobRunner | None = None) -> None:
        """Run the polling loop asynchronously.

        Args:
            runner: Job runner to use (defaults to ThreadedJobRunner)
        """
        runner = runner or ThreadedJobRunner()
        runner.run_async(self.run)
