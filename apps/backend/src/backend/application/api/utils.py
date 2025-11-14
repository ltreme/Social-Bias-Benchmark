from __future__ import annotations

import os
import sys
from pathlib import Path


def _detect_project_root() -> Path:
    """Walk parents until repository root (pyproject) is found."""
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return cur.parents[-1]


ROOT = _detect_project_root()
BACKEND_SRC = ROOT / "apps" / "backend" / "src"
if BACKEND_SRC.exists():
    src_str = str(BACKEND_SRC)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

from backend.infrastructure.storage.db import create_tables, init_database  # noqa: E402

_SEED_CHECKED = False
_DB_INITED = False


def ensure_db() -> None:
    """Initialize DB once and ensure tables exist. Subsequent calls are no-op."""
    global _DB_INITED
    if not _DB_INITED:
        init_database(os.getenv("DB_URL"))
        create_tables()
        _DB_INITED = True
    global _SEED_CHECKED
    if not _SEED_CHECKED and _DB_INITED:
        # Auto-seed reference data once per process. Duplicate rows are ignored in bulk insert.
        try:
            from backend.infrastructure.storage.prefill_db import (
                DBFiller,  # type: ignore
            )

            DBFiller().fill_all()
        except Exception:
            # Never block API startup on seeding issues
            pass
        _SEED_CHECKED = True
