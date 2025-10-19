from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root (with 'apps') is importable
# __file__ = .../apps/api/src/api/utils.py
# parents: [api, src, api, apps, <PROJECT_ROOT>]
ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# Also add common src roots for in-repo packages when running without installation
SRC_CANDIDATES = [
    ROOT / 'apps' / 'shared' / 'src',
    ROOT / 'apps' / 'analysis' / 'src',
    ROOT / 'apps' / 'benchmark' / 'src',
    ROOT / 'apps' / 'persona_generator' / 'src',
]
for p in SRC_CANDIDATES:
    if p.exists():
        sp = str(p)
        if sp not in sys.path:
            sys.path.append(sp)

from shared.storage.db import init_database, create_tables  # noqa: E402

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
            from shared.storage.prefill_db import DBFiller  # type: ignore
            DBFiller().fill_all()
        except Exception:
            # Never block API startup on seeding issues
            pass
        _SEED_CHECKED = True
