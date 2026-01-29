from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.infrastructure.logging_config import setup_logging
from backend.infrastructure.notification.notification_service import NotificationService
from backend.infrastructure.queue.executor import QueueExecutor

# Ensure repo src paths are on sys.path before importing routers
from . import utils as _api_utils  # noqa: F401  (triggers sys.path setup)
from .middleware.read_only import read_only_middleware
from .routers.attrgen import router as attrgen_router
from .routers.datasets import router as datasets_router
from .routers.models_admin import router as models_admin_router
from .routers.queue import router as queue_router
from .routers.runs import router as runs_router
from .routers.traits import router as traits_router
from .utils import ensure_db


def create_app() -> FastAPI:
    # Setup centralized logging with separate log files
    setup_logging()

    app = FastAPI(title="SBB API", version="0.2.0")
    # Initialize database once at app startup
    ensure_db()

    # Setup notification callback for queue executor
    notification_service = NotificationService()
    executor = QueueExecutor.get_instance()
    executor.set_notification_callback(notification_service.handle_task_notification)

    # Auto-start queue executor
    if not executor.is_running():
        logging.getLogger(__name__).info("Auto-starting queue executor...")
        executor.start()

    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    # Add read-only middleware
    app.middleware("http")(read_only_middleware)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/config")
    def get_config() -> dict:
        """Get application configuration."""
        read_only = os.getenv("READ_ONLY_MODE", "false").lower() in ("true", "1", "yes")
        return {"read_only_mode": read_only, "version": "0.2.0"}

    app.include_router(datasets_router)
    app.include_router(runs_router)
    app.include_router(attrgen_router)
    app.include_router(models_admin_router)
    app.include_router(traits_router)
    app.include_router(queue_router)

    return app
