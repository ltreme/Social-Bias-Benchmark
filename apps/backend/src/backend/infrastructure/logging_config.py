"""Centralized logging configuration for the backend."""

import logging
import logging.handlers
import os
from pathlib import Path


def setup_logging():
    """Configure logging with separate files for different components.

    Structure:
    - logs/api.log: FastAPI requests and general API activity
    - logs/queue.log: Queue executor and task processing
    - logs/benchmark.log: Benchmark execution details
    - Console: Only WARNING and above for all loggers
    """
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Get log level from environment
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Base format for all logs
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler - only WARNING and above to reduce noise
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    # API log file - FastAPI and general application logs
    api_handler = logging.handlers.RotatingFileHandler(
        log_dir / "api.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    api_handler.setLevel(log_level)
    api_handler.setFormatter(formatter)

    # Queue log file - Queue executor and task management
    queue_handler = logging.handlers.RotatingFileHandler(
        log_dir / "queue.log",
        maxBytes=50 * 1024 * 1024,  # 50 MB (larger for detailed task logs)
        backupCount=10,
        encoding="utf-8",
    )
    queue_handler.setLevel(log_level)
    queue_handler.setFormatter(formatter)

    # Benchmark log file - Benchmark execution
    benchmark_handler = logging.handlers.RotatingFileHandler(
        log_dir / "benchmark.log",
        maxBytes=100 * 1024 * 1024,  # 100 MB (largest for detailed execution)
        backupCount=10,
        encoding="utf-8",
    )
    benchmark_handler.setLevel(log_level)
    benchmark_handler.setFormatter(formatter)

    # Configure root logger - catches everything
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(api_handler)

    # Queue-specific loggers
    queue_loggers = [
        "backend.infrastructure.queue.executor",
        "backend.application.services.queue_service",
        "backend.infrastructure.notification.notification_service",
    ]
    for logger_name in queue_loggers:
        logger = logging.getLogger(logger_name)
        logger.addHandler(queue_handler)
        logger.propagate = True  # Also send to root (api.log)

    # Benchmark-specific loggers
    benchmark_loggers = [
        "backend.domain.benchmarking.benchmark",
        "backend.domain.benchmarking.adapters.postprocess",
        "backend.infrastructure.benchmark.executor",
        "backend.infrastructure.benchmark.cache_warming",
        "backend.infrastructure.benchmark.persister_bench",
        "backend.infrastructure.llm",
        "backend.application.services.benchmark_run_service",
        "backend.application.services.benchmark_analytics_service",
        "backend.application.services.attrgen_service",
    ]
    for logger_name in benchmark_loggers:
        logger = logging.getLogger(logger_name)
        logger.addHandler(benchmark_handler)
        logger.propagate = True  # Also send to root (api.log)

    # Reduce noise from uvicorn access logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.info("Logging configured: api.log, queue.log, benchmark.log")
    logging.info(f"Log level: {log_level_str}, Console: WARNING+")
