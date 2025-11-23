import argparse
from typing import List

import peewee as pw

from backend.infrastructure.storage.db import get_db, init_database
from backend.infrastructure.storage.models import (
    CounterfactualLink,
    Dataset,
    DatasetPersona,
    create_tables,
)


def ensure_new_tables(verbose: bool = True) -> List[str]:
    db = get_db()
    before = set(db.get_tables())
    create_tables()
    after = set(db.get_tables())
    created = sorted(list(after - before))
    if verbose:
        if created:
            print("Created tables:", ", ".join(created))
        else:
            print("No new tables needed.")
    return created


def main():
    parser = argparse.ArgumentParser(
        description="Apply DB schema updates without dropping data"
    )
    parser.add_argument(
        "--db_url",
        type=str,
        default=None,
        help="Optional DB URL (fallback to env DB_URL or SQLite path)",
    )
    parser.add_argument(
        "--upgrade-benchmarkresult-unique",
        action="store_true",
        help="Migrate BenchmarkResult unique constraint to (persona_uuid, case_id, benchmark_run)",
    )
    parser.add_argument(
        "--add-task-queue",
        action="store_true",
        help="Create TaskQueue table for queue management",
    )
    args = parser.parse_args()

    init_database(args.db_url)
    ensure_new_tables(verbose=True)

    if args.upgrade_benchmarkresult_unique:
        _upgrade_benchmarkresult_unique()

    if args.add_task_queue:
        _add_task_queue_table()


def _upgrade_benchmarkresult_unique() -> None:
    """
    For SQLite: recreate benchmarkresult with UNIQUE(persona_uuid_id, question_uuid, benchmark_run_id).
    Keeps all rows, preserves column names for compatibility.
    For non-SQLite: prints a hint.
    """
    db = get_db()
    if isinstance(db, pw.SqliteDatabase):
        # Detect unique indexes; if an old one exists, we must rebuild even if the new one exists
        try:
            idx_rows = db.execute_sql(
                "PRAGMA index_list('benchmarkresult');"
            ).fetchall()
            has_new = False
            has_old = False
            for _, name, unique, *_ in idx_rows:
                try:
                    if int(unique) != 1:
                        continue
                except Exception:
                    continue
                cols = [
                    r[2]
                    for r in db.execute_sql(f"PRAGMA index_info('{name}');").fetchall()
                ]
                s = set(cols)
                if s == {"persona_uuid_id", "question_uuid", "benchmark_run_id"}:
                    has_new = True
                if s == {
                    "persona_uuid_id",
                    "question_uuid",
                    "model_name",
                    "template_version",
                }:
                    has_old = True
            if has_new and not has_old:
                print("BenchmarkResult unique constraint already up to date.")
                return
            # If old exists (even if new exists), we rebuild to drop the old autoindex
        except Exception:
            # If inspection fails, proceed with rebuild (idempotent via table rename)
            pass

        print("Upgrading BenchmarkResult unique constraint (SQLite)…")
        db.execute_sql("PRAGMA foreign_keys=OFF;")
        db.execute_sql("BEGIN;")
        db.execute_sql(
            """
            CREATE TABLE benchmarkresult_new (
              id INTEGER PRIMARY KEY,
              persona_uuid_id TEXT NOT NULL,
              question_uuid TEXT NOT NULL,
              model_name TEXT NOT NULL,
              template_version TEXT NOT NULL,
              benchmark_run_id INTEGER,
              gen_time_ms INTEGER NOT NULL,
              attempt INTEGER NOT NULL,
              answer_raw TEXT NOT NULL,
              rating INTEGER,
              created_at TEXT NOT NULL,
              UNIQUE(persona_uuid_id, question_uuid, benchmark_run_id),
              FOREIGN KEY(benchmark_run_id) REFERENCES benchmarkrun(id) ON DELETE CASCADE
            );
            """
        )
        db.execute_sql(
            """
            INSERT INTO benchmarkresult_new
            (id, persona_uuid_id, question_uuid, model_name, template_version, benchmark_run_id,
             gen_time_ms, attempt, answer_raw, rating, created_at)
            SELECT id, persona_uuid_id, question_uuid, model_name, template_version, benchmark_run_id,
                   gen_time_ms, attempt, answer_raw, rating, created_at
            FROM benchmarkresult;
            """
        )
        db.execute_sql("DROP TABLE benchmarkresult;")
        db.execute_sql("ALTER TABLE benchmarkresult_new RENAME TO benchmarkresult;")
        db.execute_sql("COMMIT;")
        db.execute_sql("PRAGMA foreign_keys=ON;")
        print(
            "OK: migrated BenchmarkResult unique to (persona_uuid, question_uuid, benchmark_run)"
        )
        return
    else:
        print(
            "Non-SQLite DB detected. Please adjust unique index to (persona_uuid, question_uuid, benchmark_run) manually."
        )


def _add_task_queue_table() -> None:
    """Create TaskQueue table if it doesn't exist."""
    db = get_db()
    tables = db.get_tables()

    if "taskqueue" in tables:
        print("TaskQueue table already exists.")
        return

    print("Creating TaskQueue table...")
    from backend.infrastructure.storage.models import TaskQueue

    db.create_tables([TaskQueue])
    print("OK: TaskQueue table created successfully.")


if __name__ == "__main__":
    main()
