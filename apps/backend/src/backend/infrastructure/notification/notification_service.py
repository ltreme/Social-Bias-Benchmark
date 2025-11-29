"""Enhanced notification service for task queue events."""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

from backend.infrastructure.storage.models import TaskQueue

# Load .env file
load_dotenv()

_LOG = logging.getLogger(__name__)


class TelegramClient:
    """Robust Telegram client with retry logic."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        max_retries: int = 3,
    ):
        """Initialize Telegram client.

        Args:
            bot_token: Bot token (defaults to TELEGRAM_BOT_TOKEN env var)
            chat_id: Chat ID (defaults to TELEGRAM_CHAT_ID env var)
            max_retries: Maximum number of retry attempts
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.max_retries = max_retries
        self._enabled = bool(self.bot_token and self.chat_id)

        if not self._enabled:
            _LOG.warning(
                "Telegram notifications disabled: TELEGRAM_BOT_TOKEN or "
                "TELEGRAM_CHAT_ID not set"
            )

    def send_message(
        self, text: str, parse_mode: str = "Markdown", disable_preview: bool = True
    ) -> bool:
        """Send a text message via Telegram.

        Args:
            text: Message text
            parse_mode: Parse mode (Markdown or HTML)
            disable_preview: Disable link previews

        Returns:
            True if sent successfully, False otherwise
        """
        if not self._enabled:
            _LOG.debug(f"Telegram disabled, would send: {text}")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview,
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, json=payload, timeout=10)
                response.raise_for_status()
                _LOG.debug(
                    f"Telegram message sent successfully (attempt {attempt + 1})"
                )
                return True

            except requests.RequestException as e:
                _LOG.warning(
                    f"Telegram send failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    sleep_time = 2**attempt
                    time.sleep(sleep_time)
                else:
                    _LOG.error(
                        f"Telegram send failed after {self.max_retries} retries: {e}"
                    )
                    return False

        return False


class NotificationService:
    """Service for sending task queue notifications."""

    def __init__(self, telegram_client: Optional[TelegramClient] = None):
        """Initialize notification service.

        Args:
            telegram_client: Telegram client instance (default: new instance)
        """
        self.telegram = telegram_client or TelegramClient()

    def send_task_success(self, task: TaskQueue) -> None:
        """Send notification for successful task completion.

        Args:
            task: The completed task
        """
        # Special handling for benchmark tasks: run quick analysis
        if task.task_type == "benchmark" and task.result_run_id:
            self._send_benchmark_success(task)
            return

        # Calculate duration
        duration = self._format_duration(task)

        # Build message
        msg = (
            f"✅ *Task Completed*\n\n"
            f"*Type:* {task.task_type}\n"
            f"*Label:* {task.label or f'Task #{task.id}'}\n"
            f"*Duration:* {duration}\n"
        )

        # Add result info if available
        if task.result_run_id and task.result_run_type:
            msg += (
                f"*Result:* {task.result_run_type.upper()} Run #{task.result_run_id}\n"
            )

        self.telegram.send_message(msg)
        _LOG.info(f"Sent success notification for task #{task.id}")

    def _send_benchmark_success(self, task: TaskQueue) -> None:
        """Send enhanced notification for benchmark completion with quick analysis.

        Args:
            task: The completed benchmark task
        """
        from backend.application.services.analysis_service import get_analysis_service

        run_id = task.result_run_id
        duration = self._format_duration(task)

        # Run quick analysis
        try:
            analysis_service = get_analysis_service()
            summary = analysis_service.run_quick_analysis(run_id)

            # Format message with analysis results
            msg = analysis_service.format_telegram_message(run_id, summary)
            msg += f"\n⏱️ Dauer: {duration}"

            self.telegram.send_message(msg)
            _LOG.info(
                f"Sent benchmark success notification with analysis for run #{run_id}"
            )

        except Exception as e:
            _LOG.error(f"Quick analysis failed for run {run_id}: {e}")
            # Fallback to simple notification
            msg = (
                f"✅ *Benchmark Completed*\n\n"
                f"*Run:* #{run_id}\n"
                f"*Label:* {task.label or f'Task #{task.id}'}\n"
                f"*Duration:* {duration}\n"
                f"⚠️ Quick analysis failed: {str(e)[:100]}"
            )
            self.telegram.send_message(msg)

    def send_task_failure(
        self, task: TaskQueue, error: Optional[Exception] = None
    ) -> None:
        """Send notification for task failure.

        Args:
            task: The failed task
            error: The error that caused the failure
        """
        # Categorize error
        error_category = self._categorize_error(task, error)

        # Build message
        msg = (
            f"❌ *Task Failed*\n\n"
            f"*Type:* {task.task_type}\n"
            f"*Label:* {task.label or f'Task #{task.id}'}\n"
        )

        # Add error details
        error_text = task.error or (str(error) if error else "Unknown error")
        msg += f"*Error:* {error_text[:200]}\n"  # Truncate long errors

        # Add critical warning for specific error types
        if error_category == "critical":
            msg += "\n⚠️ *CRITICAL ERROR*\n"

            if (
                "connection pool" in error_text.lower()
                or "max connections" in error_text.lower()
            ):
                msg += "Database connection pool exhausted!\n"
            elif "vllm" in error_text.lower() or (
                "connection" in error_text.lower() and "refused" in error_text.lower()
            ):
                msg += "vLLM server may be unreachable!\n"
            elif "out of memory" in error_text.lower() or "oom" in error_text.lower():
                msg += "Out of memory error!\n"

        # Check for dependent tasks
        dependents = list(task.dependents)
        if dependents:
            msg += f"\n⚠️ {len(dependents)} dependent task(s) will be skipped\n"

        self.telegram.send_message(msg)
        _LOG.info(f"Sent failure notification for task #{task.id}")

    def send_queue_empty(self) -> None:
        """Send notification when queue is empty."""
        msg = "🎉 *Queue Completed*\n\nAll queued tasks have been processed!"
        self.telegram.send_message(msg)
        _LOG.info("Sent queue empty notification")

    def send_queue_started(self) -> None:
        """Send notification when queue processing starts."""
        msg = "▶️ *Queue Started*\n\nTask queue processing has begun."
        self.telegram.send_message(msg)
        _LOG.info("Sent queue started notification")

    def send_queue_paused(self) -> None:
        """Send notification when queue is paused."""
        msg = "⏸️ *Queue Paused*\n\nTask queue processing has been paused."
        self.telegram.send_message(msg)
        _LOG.info("Sent queue paused notification")

    def _format_duration(self, task: TaskQueue) -> str:
        """Format task duration as human-readable string.

        Args:
            task: The task

        Returns:
            Formatted duration string
        """
        if not task.started_at or not task.finished_at:
            return "N/A"

        delta = task.finished_at - task.started_at
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"

        minutes = total_seconds // 60
        seconds = total_seconds % 60

        if minutes < 60:
            return f"{minutes}m {seconds}s"

        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}h {minutes}m {seconds}s"

    def _categorize_error(
        self, task: TaskQueue, error: Optional[Exception] = None
    ) -> str:
        """Categorize error severity.

        Args:
            task: The task
            error: The error

        Returns:
            Error category ('critical' | 'normal')
        """
        error_text = (task.error or (str(error) if error else "")).lower()

        # Critical errors that require immediate attention
        critical_keywords = [
            "vllm",
            "connection refused",
            "connection timeout",
            "connection pool exhausted",
            "max connections exceeded",
            "database connection",
            "out of memory",
            "oom",
            "cuda",
            "gpu",
            "server not reachable",
            "cannot connect",
        ]

        for keyword in critical_keywords:
            if keyword in error_text:
                return "critical"

        return "normal"

    def handle_task_notification(
        self, task: TaskQueue, success: bool, error: Optional[Exception] = None
    ) -> None:
        """Handle task completion notification (callback from QueueExecutor).

        Args:
            task: The completed task
            success: True if task succeeded, False if failed
            error: The error if task failed
        """
        if success:
            self.send_task_success(task)
        else:
            self.send_task_failure(task, error)
