#!/usr/bin/env python3
"""
Quick migrator: import legacy benchmark results from an old SQLite DB
into the current schema. It copies personas (with demographics), cases,
and benchmark results. It also ensures a placeholder Dataset and Model
exist, and creates BenchmarkRun rows for legacy run IDs if missing.

Usage:
  python scripts/migrate_legacy_db.py --from data/benchmark.backup-YYYYMMDD.db \
      [--to data/benchmark.db] [--run-ids 10 11]

Safe by default: uses INSERT OR IGNORE semantics where possible to avoid
duplicating data.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Tuple

import peewee as pw

# Bind new DB through project helpers
import sys
from pathlib import Path

# Ensure repo root on path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.shared.src.shared.storage.db import init_database, create_tables, get_db
from apps.shared.src.shared.storage.models import (
    Persona, Case, BenchmarkResult, BenchmarkRun, Dataset, Model,
)
from apps.shared.src.shared.storage.prefill_db import DBFiller


def read_legacy_rows(conn: sqlite3.Connection, sql: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    return cur.fetchall()


def ensure_lookup_data() -> None:
    """Ensure cases table is populated (adjectives) and create placeholder dataset/model."""
    # Populate cases from CSV; ignores duplicates
    try:
        DBFiller().fill_cases()
    except Exception as e:
        print(f"[WARN] Could not prefill cases from CSV: {e}")

    # Upsert placeholder Dataset + Model
    ds, _ = Dataset.get_or_create(name="legacy-import", defaults={"kind": "reality"})
    # Some deployed DBs have NOT NULL on vllm_serve_cmd. Provide a safe default.
    Model.get_or_create(name="legacy", defaults={"min_vram": None, "vllm_serve_cmd": ""})

def update_case_adjectives_from_csv() -> int:
    """Ensure 'case.adjective' is filled for g* IDs using CSV.

    If rows already exist with empty/NULL adjective, update them.
    """
    import pandas as pd
    from apps.shared.src.shared.storage.prefill_db import cases_path
    path = cases_path("simple_likert.csv")
    if not path.exists():
        print(f"[WARN] Cases CSV not found at {path}")
        return 0
    df = pd.read_csv(path)
    mapping = {str(r["id"]).strip(): str(r["adjective"]).strip() for _, r in df.iterrows()}
    updated = 0
    with get_db().atomic():
        for cid, adj in mapping.items():
            try:
                q = Case.update(adjective=adj).where((Case.id == cid) & ((Case.adjective.is_null(True)) | (Case.adjective == "")))
                updated += q.execute() or 0
            except Exception:
                pass
    if updated:
        print(f"Updated adjectives for {updated} cases from CSV.")
    return updated


def upsert_personas(conn: sqlite3.Connection, limit_to_personas: Optional[Iterable[str]] = None) -> int:
    """Insert personas from legacy DB if missing, copying demographics when available."""
    # Probe legacy persona columns
    cols = {row[1] for row in conn.execute("PRAGMA table_info(persona)").fetchall()}

    sel_cols = [c for c in [
        "uuid", "age", "gender", "education", "occupation", "marriage_status",
        "migration_status", "religion", "sexuality", "origin_id",
    ] if c in cols]
    if not sel_cols:
        print("[WARN] Legacy persona table missing expected columns; will only ensure UUIDs exist.")
        sel_cols = ["uuid"]

    where = ""
    params: Tuple[Any, ...] = ()
    if limit_to_personas:
        uuids = list(limit_to_personas)
        where = f" WHERE uuid IN ({','.join(['?']*len(uuids))})"
        params = tuple(uuids)
    rows = read_legacy_rows(conn, f"SELECT {', '.join(sel_cols)} FROM persona{where}", params)

    inserted = 0
    with get_db().atomic():
        for r in rows:
            data: Dict[str, Any] = {k: r[k] for k in r.keys() if k != "uuid"}
            try:
                Persona.insert({"uuid": r["uuid"], **data}).on_conflict_ignore().execute()
                inserted += 1
            except Exception as e:
                print(f"[WARN] Persona {r['uuid']} not inserted: {e}")
    print(f"Personas upserted: {inserted} (duplicates ignored)")
    return inserted


def upsert_cases_from_results(conn: sqlite3.Connection, run_ids: Optional[List[int]]) -> int:
    where = ""
    params: Tuple[Any, ...] = ()
    if run_ids:
        where = f" WHERE benchmark_run_id IN ({','.join(['?']*len(run_ids))})"
        params = tuple(run_ids)
    # Legacy column name: question_uuid
    rows = read_legacy_rows(conn, f"SELECT DISTINCT question_uuid FROM benchmarkresult{where}", params)
    ids = [str(r["question_uuid"]) for r in rows if r["question_uuid"] is not None]
    if not ids:
        return 0
    # Create missing cases with adjective=id (will be overwritten by prefill if available)
    existing = {c.id for c in Case.select(Case.id).where(Case.id.in_(ids))}
    new_ids = [i for i in ids if i not in existing]
    with get_db().atomic():
        for cid in new_ids:
            try:
                Case.insert({"id": cid, "adjective": cid, "case_template": None}).on_conflict_ignore().execute()
            except Exception:
                pass
    print(f"Cases ensured: {len(ids)} (new: {len(new_ids)})")
    return len(new_ids)


def ensure_runs(run_ids: List[int]) -> None:
    ds = Dataset.get(Dataset.name == "legacy-import")
    model = Model.get(Model.name == "legacy")
    for rid in run_ids:
        BenchmarkRun.insert({
            "id": int(rid),
            "dataset_id": ds.id,
            "model_id": model.id,
            "include_rationale": True,
        }).on_conflict_ignore().execute()


def import_results(conn: sqlite3.Connection, run_ids: Optional[List[int]], only_g: bool = True) -> int:
    where = ""
    params: Tuple[Any, ...] = ()
    if run_ids:
        where = f" WHERE benchmark_run_id IN ({','.join(['?']*len(run_ids))})"
        params = tuple(run_ids)
    rows = read_legacy_rows(conn, f"""
        SELECT id, persona_uuid_id, question_uuid, benchmark_run_id, attempt, answer_raw, rating, created_at
        FROM benchmarkresult{where}
    """, params)
    if not rows:
        print("No legacy benchmarkresult rows found.")
        return 0

    # Optional filter to g*-questions only
    if only_g:
        rows = [r for r in rows if (r["question_uuid"] or "").startswith("g")]

    # Ensure personas referenced exist
    used_personas = {str(r["persona_uuid_id"]) for r in rows if r["persona_uuid_id"]}
    upsert_personas(conn, used_personas)

    # Ensure cases referenced exist
    upsert_cases_from_results(conn, run_ids)

    # Ensure runs exist
    if run_ids:
        ensure_runs(run_ids)
    else:
        ensure_runs(sorted({int(r["benchmark_run_id"]) for r in rows if r["benchmark_run_id"] is not None}))

    # quick summary
    from collections import Counter, defaultdict
    per_run = Counter([int(r["benchmark_run_id"]) for r in rows if r["benchmark_run_id"] is not None])
    per_q = Counter([str(r["question_uuid"]) for r in rows if r["question_uuid"]])
    print("Rows to import → per run:", dict(per_run))
    print("Rows to import → per question:", dict(per_q))

    inserted = 0
    with get_db().atomic():
        for r in rows:
            data = {
                "persona_uuid_id": r["persona_uuid_id"],
                "case_id": r["question_uuid"],
                "benchmark_run_id": int(r["benchmark_run_id"]) if r["benchmark_run_id"] is not None else None,
                "attempt": int(r["attempt"]) if r["attempt"] is not None else 1,
                "answer_raw": r["answer_raw"] or "",
                "rating": int(r["rating"]) if r["rating"] is not None else None,
                "created_at": r["created_at"],
            }
            try:
                BenchmarkResult.insert(data).on_conflict_ignore().execute()
                inserted += 1
            except Exception as e:
                print(f"[WARN] result row not inserted (persona={data['persona_uuid_id']} case={data['case_id']} run={data['benchmark_run_id']}): {e}")
    print(f"BenchmarkResult inserted: {inserted} (duplicates ignored where present)")
    return inserted


def ensure_benchmarkresult_unique_triple_sqlite() -> None:
    """On SQLite, ensure UNIQUE(benchmark_run_id, persona_uuid_id, case_id).

    If the existing table has an incompatible UNIQUE (e.g., only run+persona),
    we rebuild the table and copy data. This is safe-ish with a backup.
    """
    db = get_db()
    if not isinstance(db, pw.SqliteDatabase):
        return
    # Detect if a unique index exists on the desired triple
    con = db.connection()
    con.row_factory = sqlite3.Row
    indexes = con.execute("PRAGMA index_list(benchmarkresult)").fetchall()
    has_triple = False
    for idx in indexes:
        name = idx[1]
        if not name:
            continue
        cols = [r[2] for r in con.execute(f"PRAGMA index_info('{name}')").fetchall()]
        if set(cols) == {"benchmark_run_id", "persona_uuid_id", "case_id"} and idx[2]:  # unique
            has_triple = True
            break
    if has_triple:
        return
    print("[MIGRATE] Rebuilding benchmarkresult to enforce UNIQUE(run, persona, case)…")
    with db.atomic():
        con.executescript(
            """
            BEGIN;
            CREATE TABLE IF NOT EXISTS benchmarkresult_new (
                id INTEGER PRIMARY KEY,
                persona_uuid_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                benchmark_run_id INTEGER NOT NULL,
                attempt INTEGER NOT NULL DEFAULT 1,
                answer_raw TEXT NOT NULL,
                rating INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(persona_uuid_id) REFERENCES persona(uuid) ON DELETE CASCADE,
                FOREIGN KEY(case_id) REFERENCES "case"(id) ON DELETE RESTRICT,
                FOREIGN KEY(benchmark_run_id) REFERENCES benchmarkrun(id) ON DELETE CASCADE,
                UNIQUE(benchmark_run_id, persona_uuid_id, case_id)
            );
            INSERT OR IGNORE INTO benchmarkresult_new
            (id, persona_uuid_id, case_id, benchmark_run_id, attempt, answer_raw, rating, created_at)
            SELECT id, persona_uuid_id, case_id, benchmark_run_id, attempt, answer_raw, rating, created_at FROM benchmarkresult;
            DROP TABLE benchmarkresult;
            ALTER TABLE benchmarkresult_new RENAME TO benchmarkresult;
            COMMIT;
            """
        )
    print("[MIGRATE] benchmarkresult table rebuilt with correct UNIQUE constraint.")


def print_dest_distribution(run_ids: List[int]) -> None:
    db = get_db()
    con = db.connection()
    con.row_factory = sqlite3.Row
    for rid in run_ids:
        rows = con.execute(
            "SELECT case_id, COUNT(*) AS n FROM benchmarkresult WHERE benchmark_run_id=? GROUP BY case_id ORDER BY case_id",
            (rid,),
        ).fetchall()
        print(f"Dest distribution for run {rid}:", {r["case_id"]: r["n"] for r in rows})


def delete_runs_from_dest(run_ids: List[int]) -> None:
    db = get_db()
    with db.atomic():
        for rid in run_ids:
            get_db().execute_sql("DELETE FROM benchmarkresult WHERE benchmark_run_id=?", (rid,))
            print(f"Deleted existing results for run {rid} in destination DB.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Migrate legacy benchmark DB into current schema")
    ap.add_argument("--from", dest="src", required=True, help="Path to legacy SQLite DB")
    ap.add_argument("--to", dest="dst", default=os.getenv("DB_URL") or "data/benchmark.db", help="Destination DB file or DB_URL")
    ap.add_argument("--run-ids", dest="run_ids", nargs="*", type=int, help="Legacy run IDs to import (default: all)")
    ap.add_argument("--replace-runs", dest="replace_runs", nargs="*", type=int, help="Delete existing results for these run IDs in destination before import")
    args = ap.parse_args()

    # Init destination DB
    if args.dst.endswith('.db'):
        dst_url = f"sqlite:///{args.dst}"
    elif args.dst.startswith('sqlite:') or '://' in args.dst:
        dst_url = args.dst
    else:
        # assume file path
        dst_url = f"sqlite:///{args.dst}"
    init_database(dst_url)
    create_tables()
    ensure_lookup_data()
    # Ensure result unique constraint is correct before import
    ensure_benchmarkresult_unique_triple_sqlite()
    update_case_adjectives_from_csv()

    # Connect legacy DB
    if not os.path.exists(args.src):
        raise SystemExit(f"Legacy DB not found: {args.src}")
    conn = sqlite3.connect(args.src)

    # Import
    run_ids = args.run_ids if args.run_ids else None
    if run_ids:
        print(f"Importing runs: {run_ids}")
    # Optionally clear runs to avoid residual partial data
    if args.replace_runs:
        delete_runs_from_dest(args.replace_runs)
    n = import_results(conn, run_ids, only_g=True)
    print(f"Done. Inserted {n} results.")
    # Show destination distribution for quick verification
    if run_ids:
        print_dest_distribution(run_ids)


if __name__ == "__main__":
    main()
