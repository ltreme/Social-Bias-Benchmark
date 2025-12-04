"""Dedicated logger for LLM prompts and responses.

Logs to a separate file for full transparency without DB overhead.
Each log entry contains:
- Timestamp
- Benchmark run ID
- Persona UUID  
- Case ID
- Scale order (in/rev)
- Full prompt text
- Full raw response
- Parsed rating (if successful)

Format: JSON Lines (one JSON object per line) for easy parsing.
"""

import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Dedicated logger - separate from main app logger
_PROMPT_LOG = logging.getLogger("prompt_response")
_PROMPT_LOG.setLevel(logging.INFO)
_PROMPT_LOG.propagate = False  # Don't propagate to root logger

_INITIALIZED = False


def _ensure_initialized() -> None:
    """Initialize the prompt logger with file handler."""
    global _INITIALIZED
    if _INITIALIZED:
        return

    # Determine log directory
    log_dir = Path(os.environ.get("PROMPT_LOG_DIR", "/app/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "prompts.jsonl"

    # Rotating file handler: 50MB per file, keep 10 files
    handler = RotatingFileHandler(
        log_file,
        maxBytes=50 * 1024 * 1024,  # 50 MB
        backupCount=10,
        encoding="utf-8",
    )

    # Raw format - we'll write JSON directly
    handler.setFormatter(logging.Formatter("%(message)s"))

    _PROMPT_LOG.addHandler(handler)
    _INITIALIZED = True


def log_prompt_response(
    *,
    benchmark_run_id: int,
    persona_uuid: str,
    case_id: str,
    scale_order: str,
    prompt_text: str,
    raw_response: str,
    rating: Optional[int] = None,
    gen_time_ms: Optional[int] = None,
    attempt: int = 1,
    model_name: str = "",
    success: bool = True,
    error_reason: Optional[str] = None,
) -> None:
    """Log a prompt/response pair to the dedicated log file.

    Args:
        benchmark_run_id: The benchmark run this belongs to
        persona_uuid: UUID of the persona
        case_id: The trait/case ID
        scale_order: 'in' or 'rev'
        prompt_text: Full prompt sent to LLM
        raw_response: Full raw response from LLM
        rating: Parsed rating (1-5) if successful
        gen_time_ms: Generation time in milliseconds
        attempt: Attempt number (1-based)
        model_name: Name of the model
        success: Whether parsing succeeded
        error_reason: Reason for failure if not success
    """
    _ensure_initialized()

    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "run_id": benchmark_run_id,
        "persona": persona_uuid,
        "case": case_id,
        "scale": scale_order,
        "attempt": attempt,
        "model": model_name,
        "prompt": prompt_text,
        "response": raw_response,
        "rating": rating,
        "gen_ms": gen_time_ms,
        "ok": success,
    }

    if error_reason:
        entry["error"] = error_reason

    try:
        _PROMPT_LOG.info(json.dumps(entry, ensure_ascii=False))
    except Exception:
        # Never let logging break the benchmark
        pass


def is_enabled() -> bool:
    """Check if prompt logging is enabled."""
    return os.environ.get("PROMPT_LOG_ENABLED", "1").lower() in ("1", "true", "yes")
