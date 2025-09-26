from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root (with 'apps') is importable
ROOT = Path(__file__).resolve().parents[3]
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


def ensure_db() -> None:
    """Initialize and ensure tables exist (idempotent)."""
    init_database(os.getenv("DB_URL"))
    create_tables()
