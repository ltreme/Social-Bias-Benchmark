from __future__ import annotations

from typing import Generator

from backend.infrastructure.storage.db import get_db

from .utils import ensure_db


def db_session() -> Generator[None, None, None]:
    """
    FastAPI dependency that ensures the database is initialised and closes the
    Peewee connection for the current worker thread after each request.
    """
    ensure_db()
    db = get_db()
    with db.connection_context():
        yield
