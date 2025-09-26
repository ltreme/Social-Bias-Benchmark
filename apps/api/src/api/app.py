from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.datasets import router as datasets_router
from .routers.metrics import router as metrics_router
from .routers.runs import router as runs_router


def create_app() -> FastAPI:
    app = FastAPI(title="SBB API", version="0.2.0")

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

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    app.include_router(datasets_router)
    app.include_router(metrics_router)
    app.include_router(runs_router)

    return app

