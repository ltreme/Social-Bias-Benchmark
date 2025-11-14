from __future__ import annotations

import sys
from pathlib import Path


def _ensure_backend_src() -> Path:
    backend_src = Path(__file__).resolve().parents[4]  # .../apps/backend/src
    if str(backend_src) not in sys.path:
        sys.path.insert(0, str(backend_src))
    return backend_src


BACKEND_SRC = _ensure_backend_src()

from backend.application.api.app import create_app  # type: ignore

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.application.api.main:app",
        host="0.0.0.0",
        port=8765,
        reload=True,
        app_dir=str(BACKEND_SRC),
    )
