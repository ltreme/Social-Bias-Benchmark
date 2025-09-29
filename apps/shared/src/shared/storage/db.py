# shared/storage/db.py
import os
from contextlib import contextmanager
import peewee as pw
from playhouse.db_url import connect
from pathlib import Path

db_proxy = pw.Proxy()

DEFAULT_SQLITE_PATH = Path("data/benchmark.db")  # cwd is project root by contract

def _ensure_parent_dir(p: Path) -> None:
    """Create parent directory for file paths if it does not exist."""
    p.parent.mkdir(parents=True, exist_ok=True)

def init_database(db_url: str | None = None) -> pw.Database:
    """
    Initialize DB connection.
    - Default: SQLite under ./data/benchmark.db (created on first connect).
    - Honors DB_URL env or explicit db_url for other backends.
    """
    db_url = db_url or os.getenv("DB_URL")
    if db_url:
        db = connect(db_url)
        if isinstance(db, pw.SqliteDatabase) and db.database not in (":memory:", None):
            _ensure_parent_dir(Path(db.database).resolve())
    else:
        db_path = DEFAULT_SQLITE_PATH.resolve()
        _ensure_parent_dir(db_path)
        db = pw.SqliteDatabase(
            str(db_path),
            pragmas={
                "foreign_keys": 1,   # enforce FK constraints
                # Improve concurrency: WAL journal and relaxed sync are safe for our usage
                "journal_mode": "wal",
                "synchronous": "normal",
            },
        )

    db.connect(reuse_if_open=True)

    db_proxy.initialize(db)
    return db


def create_tables() -> None:
    """Import models lazily and create tables on the active DB connection."""
    from .models import ALL_MODELS  # local import prevents cycles
    db = get_db()
    db.create_tables(ALL_MODELS, safe=True)
    _fix_legacy_indexes(db)
    _ensure_new_columns(db)


def _fix_legacy_indexes(db: pw.Database) -> None:
    """Drop broken legacy indexes that can block inserts.

    Specifically: benchmarkresult_persona_uuid_id_question_uuid_benchmark_run_id
    which referenced a non-existent column (question_uuid) in older DBs and
    effectively enforces a wrong uniqueness (persona_uuid_id, benchmark_run_id).
    """
    try:
        cur = db.execute_sql("PRAGMA index_list(benchmarkresult)")
        idx_rows = cur.fetchall()
        target = 'benchmarkresult_persona_uuid_id_question_uuid_benchmark_run_id'
        for row in idx_rows:
            name = row[1]
            if name != target:
                continue
            # Verify it is problematic (contains a NULL column in PRAGMA index_info)
            info = db.execute_sql(f"PRAGMA index_info({name})").fetchall()
            has_null_col = any(col[2] is None for col in info)
            if has_null_col:
                db.execute_sql(f"DROP INDEX IF EXISTS {name}")
    except Exception:
        # Do not block startup on migration issues
        pass


def _ensure_new_columns(db: pw.Database) -> None:
    """Lightweight migrations to add newly introduced nullable columns.

    - benchmarkresult.scale_order TEXT NULL
    - benchmarkrun.scale_mode TEXT NULL
    """
    try:
        # benchmarkresult.scale_order
        cur = db.execute_sql("PRAGMA table_info(benchmarkresult)")
        cols = {row[1] for row in cur.fetchall()}
        if "scale_order" not in cols:
            db.execute_sql("ALTER TABLE benchmarkresult ADD COLUMN scale_order TEXT NULL")
    except Exception:
        pass
    try:
        # benchmarkrun.scale_mode
        cur = db.execute_sql("PRAGMA table_info(benchmarkrun)")
        cols = {row[1] for row in cur.fetchall()}
        if "scale_mode" not in cols:
            db.execute_sql("ALTER TABLE benchmarkrun ADD COLUMN scale_mode TEXT NULL")
    except Exception:
        pass


def drop_tables() -> None:
    """Drop all tables (for testing)."""
    from .models import ALL_MODELS  # local import prevents cycles
    db = get_db()
    db.drop_tables(ALL_MODELS, safe=True)

@contextmanager
def transaction():
    """Provide a transactional scope."""
    with db_proxy.atomic() as txn:
        try:
            yield
        except Exception:
            txn.rollback()
            raise

def get_db() -> pw.Database:
    """
    Access the active database bound to the proxy.
    Raises if init_database() was not called.
    """
    if not isinstance(db_proxy.obj, pw.Database):
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return db_proxy.obj
