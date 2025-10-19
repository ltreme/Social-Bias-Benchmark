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

    try:
        # Lightweight diagnostic to confirm backend in logs
        if isinstance(db, pw.SqliteDatabase):
            where = db.database or ":memory:"
            print(f"[DB] Using SQLite at {where}")
        elif isinstance(db, pw.PostgresqlDatabase):  # type: ignore[attr-defined]
            # Avoid printing credentials; show db name and host
            host = getattr(db, 'host', None) or 'localhost'
            print(f"[DB] Using PostgreSQL db='{db.database}' host='{host}'")
        else:
            print(f"[DB] Using database backend: {db.__class__.__name__}")
    except Exception:
        pass

    db_proxy.initialize(db)
    return db


def create_tables() -> None:
    """Import models lazily and create tables on the active DB connection."""
    from .models import ALL_MODELS  # local import prevents cycles
    db = get_db()
    db.create_tables(ALL_MODELS, safe=True)
    _fix_legacy_indexes(db)
    _ensure_new_columns(db)
    _migrate_benchmarkresult_unique_index(db)
    _migrate_additional_attrs_unique_index(db)
    _rebuild_benchmarkresult_if_legacy_unique(db)
    _rebuild_additional_attrs_if_legacy_unique(db)


def _fix_legacy_indexes(db: pw.Database) -> None:
    """Drop broken legacy indexes that can block inserts (SQLite only)."""
    # Only relevant for SQLite; Postgres doesn't support PRAGMA and doesn't have these legacy indexes
    if not isinstance(db, pw.SqliteDatabase):
        return
    try:
        cur = db.execute_sql("PRAGMA index_list(benchmarkresult)")
        idx_rows = cur.fetchall()
        target = 'benchmarkresult_persona_uuid_id_question_uuid_benchmark_run_id'
        for row in idx_rows:
            name = row[1]
            if name != target:
                continue
            info = db.execute_sql(f"PRAGMA index_info({name})").fetchall()
            has_null_col = any(col[2] is None for col in info)
            if has_null_col:
                db.execute_sql(f"DROP INDEX IF EXISTS {name}")
    except Exception:
        pass


def _ensure_new_columns(db: pw.Database) -> None:
    """Lightweight migrations to add newly introduced nullable columns (SQLite only).

    On PostgreSQL we rely on Peewee's schema creation and explicit migrations.
    """
    if not isinstance(db, pw.SqliteDatabase):
        return
    try:
        cur = db.execute_sql("PRAGMA table_info(benchmarkresult)")
        cols = {row[1] for row in cur.fetchall()}
        if "scale_order" not in cols:
            db.execute_sql("ALTER TABLE benchmarkresult ADD COLUMN scale_order TEXT NULL")
    except Exception:
        pass
    try:
        cur = db.execute_sql("PRAGMA table_info(benchmarkrun)")
        cols = {row[1] for row in cur.fetchall()}
        if "scale_mode" not in cols:
            db.execute_sql("ALTER TABLE benchmarkrun ADD COLUMN scale_mode TEXT NULL")
    except Exception:
        pass
    try:
        cur = db.execute_sql("PRAGMA table_info(benchmarkrun)")
        cols = {row[1] for row in cur.fetchall()}
        if "dual_fraction" not in cols:
            db.execute_sql("ALTER TABLE benchmarkrun ADD COLUMN dual_fraction REAL NULL")
    except Exception:
        pass

def _migrate_benchmarkresult_unique_index(db: pw.Database) -> None:
    """Ensure uniqueness for benchmarkresult includes scale_order (SQLite only)."""
    if not isinstance(db, pw.SqliteDatabase):
        return
    try:
        cur = db.execute_sql("PRAGMA index_list(benchmarkresult)")
        idx_rows = cur.fetchall()
        for row in idx_rows:
            name = row[1]
            is_unique = bool(row[2])
            if not is_unique:
                continue
            info = db.execute_sql(f"PRAGMA index_info({name})").fetchall()
            cols = [r[2] for r in info]
            if set(cols) == {"benchmark_run_id", "persona_uuid_id", "case_id"}:
                db.execute_sql(f"DROP INDEX IF EXISTS {name}")
        cur = db.execute_sql("PRAGMA index_list(benchmarkresult)")
        idx_rows = cur.fetchall()
        has_target = False
        for row in idx_rows:
            name = row[1]
            is_unique = bool(row[2])
            info = db.execute_sql(f"PRAGMA index_info({name})").fetchall()
            cols = [r[2] for r in info]
            if is_unique and cols == ["benchmark_run_id","persona_uuid_id","case_id","scale_order"]:
                has_target = True
                break
        if not has_target:
            db.execute_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uniq_benchmarkresult_run_persona_case_order "
                "ON benchmarkresult (benchmark_run_id, persona_uuid_id, case_id, scale_order)"
            )
    except Exception:
        pass


def _migrate_additional_attrs_unique_index(db: pw.Database) -> None:
    """Ensure AdditionalPersonaAttributes unique index (SQLite only)."""
    if not isinstance(db, pw.SqliteDatabase):
        return
    try:
        table = 'additionalpersonaattributes'
        cur = db.execute_sql(f"PRAGMA index_list({table})")
        idx_rows = cur.fetchall()
        for row in idx_rows:
            name = row[1]
            is_unique = bool(row[2])
            if not is_unique:
                continue
            info = db.execute_sql(f"PRAGMA index_info({name})").fetchall()
            cols = [r[2] for r in info]
            if set(cols) == {"persona_uuid_id", "attribute_key"}:
                db.execute_sql(f"DROP INDEX IF EXISTS {name}")
        cur = db.execute_sql(f"PRAGMA index_list({table})")
        idx_rows = cur.fetchall()
        has_target = False
        for row in idx_rows:
            name = row[1]
            is_unique = bool(row[2])
            info = db.execute_sql(f"PRAGMA index_info({name})").fetchall()
            cols = [r[2] for r in info]
            if is_unique and cols == ["attr_generation_run_id", "persona_uuid_id", "attribute_key"]:
                has_target = True
                break
        if not has_target:
            db.execute_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uniq_attr_run_persona_key "
                "ON additionalpersonaattributes (attr_generation_run_id, persona_uuid_id, attribute_key)"
            )
    except Exception:
        pass

def _rebuild_benchmarkresult_if_legacy_unique(db: pw.Database) -> None:
    """On SQLite, rebuild table if it still has a legacy UNIQUE(run,persona,case).

    Some DBs carry an internal sqlite_autoindex generated from a table-level
    UNIQUE constraint on (benchmark_run_id, persona_uuid_id, case_id). That
    constraint cannot be dropped with DROP INDEX. We detect this situation and
    rebuild the table with the desired UNIQUE including scale_order.
    """
    try:
        if not isinstance(db, pw.SqliteDatabase):
            return
        rows = db.execute_sql("PRAGMA index_list(benchmarkresult)").fetchall()
        auto = [r for r in rows if r[1] == 'sqlite_autoindex_benchmarkresult_1']
        if not auto:
            return
        info = db.execute_sql("PRAGMA index_info('sqlite_autoindex_benchmarkresult_1')").fetchall()
        cols = [r[2] for r in info]
        if set(cols) != {"benchmark_run_id", "persona_uuid_id", "case_id"}:
            return
        # Rebuild
        db.execute_sql("PRAGMA foreign_keys=OFF")
        try:
            db.execute_sql("BEGIN")
            db.execute_sql(
                "CREATE TABLE benchmarkresult_new (\n"
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
                "  persona_uuid_id TEXT NOT NULL,\n"
                "  case_id TEXT NOT NULL,\n"
                "  benchmark_run_id INTEGER NOT NULL,\n"
                "  attempt INTEGER NOT NULL DEFAULT 1,\n"
                "  answer_raw TEXT NOT NULL,\n"
                "  rating INTEGER,\n"
                "  created_at TEXT NOT NULL,\n"
                "  scale_order TEXT,\n"
                "  FOREIGN KEY(persona_uuid_id) REFERENCES persona(uuid) ON DELETE CASCADE,\n"
                "  FOREIGN KEY(case_id) REFERENCES \"case\"(id) ON DELETE RESTRICT,\n"
                "  FOREIGN KEY(benchmark_run_id) REFERENCES benchmarkrun(id) ON DELETE CASCADE\n"
                ")"
            )
            # Copy data; keep existing scale_order if present
            db.execute_sql(
                "INSERT INTO benchmarkresult_new (id, persona_uuid_id, case_id, benchmark_run_id, attempt, answer_raw, rating, created_at, scale_order)\n"
                "SELECT id, persona_uuid_id, case_id, benchmark_run_id, attempt, answer_raw, rating, created_at, scale_order FROM benchmarkresult"
            )
            db.execute_sql("DROP TABLE benchmarkresult")
            db.execute_sql("ALTER TABLE benchmarkresult_new RENAME TO benchmarkresult")
            # Indexes
            db.execute_sql("CREATE INDEX IF NOT EXISTS benchmarkresult_case_id ON benchmarkresult(case_id)")
            db.execute_sql("CREATE INDEX IF NOT EXISTS benchmarkresult_benchmark_run_id ON benchmarkresult(benchmark_run_id)")
            db.execute_sql("CREATE INDEX IF NOT EXISTS benchmarkresult_persona_uuid_id ON benchmarkresult(persona_uuid_id)")
            db.execute_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uniq_benchmarkresult_run_persona_case_order ON benchmarkresult (benchmark_run_id, persona_uuid_id, case_id, scale_order)"
            )
            db.execute_sql("COMMIT")
        except Exception:
            db.execute_sql("ROLLBACK")
            raise
        finally:
            db.execute_sql("PRAGMA foreign_keys=ON")
    except Exception:
        # Don't block startup on migration failure
        pass


def _rebuild_additional_attrs_if_legacy_unique(db: pw.Database) -> None:
    """Rebuild AdditionalPersonaAttributes if it still has legacy UNIQUE(persona_uuid_id, attribute_key).

    When the legacy unique constraint was defined at table-level, SQLite creates
    an internal sqlite_autoindex that cannot be dropped. Detect that shape and
    rebuild the table with the desired UNIQUE(attr_generation_run_id, persona_uuid_id, attribute_key).
    """
    try:
        if not isinstance(db, pw.SqliteDatabase):
            return
        rows = db.execute_sql("PRAGMA index_list(additionalpersonaattributes)").fetchall()
        auto = [r for r in rows if r[1] == 'sqlite_autoindex_additionalpersonaattributes_1']
        if not auto:
            return
        info = db.execute_sql("PRAGMA index_info('sqlite_autoindex_additionalpersonaattributes_1')").fetchall()
        cols = [r[2] for r in info]
        # legacy unique was exactly on (persona_uuid_id, attribute_key)
        if set(cols) != {"persona_uuid_id", "attribute_key"}:
            return
        # Rebuild
        db.execute_sql("PRAGMA foreign_keys=OFF")
        try:
            db.execute_sql("BEGIN")
            db.execute_sql(
                "CREATE TABLE additionalpersonaattributes_new (\n"
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
                "  persona_uuid_id TEXT NOT NULL,\n"
                "  attr_generation_run_id INTEGER,\n"
                "  attempt INTEGER NOT NULL DEFAULT 1,\n"
                "  attribute_key TEXT NOT NULL,\n"
                "  value TEXT NOT NULL,\n"
                "  created_at TEXT NOT NULL,\n"
                "  FOREIGN KEY(persona_uuid_id) REFERENCES persona(uuid) ON DELETE CASCADE,\n"
                "  FOREIGN KEY(attr_generation_run_id) REFERENCES attrgenerationrun(id) ON DELETE SET NULL\n"
                ")"
            )
            # Copy data verbatim; legacy rows may have NULL run ids
            db.execute_sql(
                "INSERT INTO additionalpersonaattributes_new (id, persona_uuid_id, attr_generation_run_id, attempt, attribute_key, value, created_at)\n"
                "SELECT id, persona_uuid_id, attr_generation_run_id, attempt, attribute_key, value, created_at FROM additionalpersonaattributes"
            )
            db.execute_sql("DROP TABLE additionalpersonaattributes")
            db.execute_sql("ALTER TABLE additionalpersonaattributes_new RENAME TO additionalpersonaattributes")
            # Helpful secondary indexes
            db.execute_sql("CREATE INDEX IF NOT EXISTS add_attr_persona_uuid_id ON additionalpersonaattributes(persona_uuid_id)")
            db.execute_sql("CREATE INDEX IF NOT EXISTS add_attr_run_id ON additionalpersonaattributes(attr_generation_run_id)")
            # Desired unique index
            db.execute_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uniq_attr_run_persona_key "
                "ON additionalpersonaattributes (attr_generation_run_id, persona_uuid_id, attribute_key)"
            )
            db.execute_sql("COMMIT")
        except Exception:
            db.execute_sql("ROLLBACK")
            raise
        finally:
            db.execute_sql("PRAGMA foreign_keys=ON")
    except Exception:
        # Don't block startup on migration failure
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
