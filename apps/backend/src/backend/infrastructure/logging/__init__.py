"""Logging infrastructure for the benchmark system."""

from .prompt_logger import is_enabled, log_prompt_response

__all__ = ["log_prompt_response", "is_enabled"]
