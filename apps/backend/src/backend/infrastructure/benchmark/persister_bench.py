from __future__ import annotations

import threading
import time
from typing import Dict, List

from backend.domain.benchmarking.ports_bench import BenchAnswerDto, BenchPersister


class BenchPersisterPrint(BenchPersister):
    def persist_results(self, rows: List[BenchAnswerDto]) -> None:
        if not rows:
            return
        print(
            "RESULTS",
            [
                (
                    r.persona_uuid,
                    r.case_id,
                    r.rating,
                    r.model_name,
                    r.template_version,
                    r.benchmark_run_id,
                )
                for r in rows
            ],
        )

    def persist_failure(self, fail) -> None:
        print("FAIL  ", fail.persona_uuid, fail.error_kind, "attempt", fail.attempt)


class BenchPersisterPeewee(BenchPersister):
    # Class-level lock to ensure only ONE persist operation at a time across all instances
    _persist_lock = threading.Lock()
    # In-memory progress tracking per benchmark_run_id to avoid expensive COUNT queries
    # Format: {run_id: {"count": int, "last_update": float}}
    _progress_counters = {}

    def __init__(self):
        from backend.infrastructure.storage import models as _models
        from backend.infrastructure.storage.db import get_db

        self.db = get_db()
        self.models = _models

        if not hasattr(self.models, "BenchmarkResult"):
            raise ImportError("storage models missing BenchmarkResult – add model.")
        if not hasattr(self.models, "FailLog"):
            raise ImportError("storage models missing FailLog – adjust persister.")

        self._Res = self.models.BenchmarkResult
        self._Fail = self.models.FailLog

        # Detect legacy column 'question_uuid' (pre-rename of case_id) to stay backward compatible
        self._has_legacy_question_col = False
        # Prefer model-field detection; PRAGMA is SQLite-specific
        try:
            self._has_scale_order_col = hasattr(self._Res, "scale_order")
        except Exception:
            self._has_scale_order_col = False
        # Legacy question_uuid detection (best-effort; safe if table missing)
        try:
            cur = self.db.execute_sql("PRAGMA table_info(benchmarkresult)")
            cols = {row[1] for row in cur.fetchall()}  # row[1] = name
            self._has_legacy_question_col = "question_uuid" in cols
        except Exception:
            self._has_legacy_question_col = False

    def persist_results(self, rows: List[BenchAnswerDto]) -> None:
        if not rows:
            return

        import logging
        import time

        _LOG = logging.getLogger(__name__)

        # CRITICAL: Acquire lock to ensure only ONE persist at a time
        # This prevents concurrent INSERTs from different LLM batches → no more deadlocks
        wait_start = time.time()
        _LOG.debug(f"[Persister] Acquiring lock for {len(rows)} rows...")
        with self._persist_lock:
            wait_time = time.time() - wait_start
            if wait_time > 0.1:
                _LOG.info(
                    f"[Persister] Waited {wait_time:.3f}s for lock (queue size indicator)"
                )

            _LOG.debug(f"[Persister] Lock acquired. Writing to DB...")
            payload = []
            for r in rows:
                item = dict(
                    persona_uuid_id=r.persona_uuid,
                    case_id=r.case_id,
                    benchmark_run_id=r.benchmark_run_id,
                    attempt=r.attempt,
                    answer_raw=r.answer_raw,
                    rating=r.rating,
                )
                if self._has_legacy_question_col:
                    # Mirror case_id into legacy column to satisfy old UNIQUE(persona_uuid_id, question_uuid, benchmark_run_id)
                    item["question_uuid"] = r.case_id
                if getattr(self, "_has_scale_order_col", False):
                    item["scale_order"] = (
                        "rev" if getattr(r, "scale_reversed", False) else "in"
                    )
                payload.append(item)

            # Retry logic for PostgreSQL deadlocks/serialization failures (now less likely!)
            max_retries = 3  # Reduced back to 3 since deadlocks should be rare now

            for retry in range(max_retries):
                try:
                    start_time = time.time()
                    with self.db.atomic():
                        # SQLite: use OR IGNORE to be robust to legacy index names/orders.
                        (self._Res.insert_many(payload).on_conflict_ignore().execute())
                    elapsed = time.time() - start_time

                    # Update in-memory progress counter
                    # Extract benchmark_run_id from first item (all rows have same run_id)
                    if payload:
                        run_id = payload[0].get("benchmark_run_id")
                        if run_id:
                            counter = self._progress_counters.setdefault(
                                run_id, {"count": 0, "last_update": time.time()}
                            )
                            counter["count"] += len(payload)
                            counter["last_update"] = time.time()

                    if elapsed > 1.0:
                        _LOG.warning(
                            f"[Persister] Slow INSERT: {elapsed:.2f}s for {len(payload)} rows"
                        )
                    elif elapsed > 0.5:
                        _LOG.info(
                            f"[Persister] INSERT took {elapsed:.3f}s for {len(payload)} rows"
                        )

                    _LOG.debug(f"[Persister] Done writing {len(payload)} rows.")
                    break  # Success, exit retry loop
                except Exception as e:
                    error_str = str(e).lower()
                    # PostgreSQL deadlock or serialization failure (should be rare now with lock!)
                    if (
                        "deadlock" in error_str
                        or "serialization" in error_str
                        or "timeout" in error_str
                    ) and retry < max_retries - 1:
                        backoff = 0.1 * (2**retry)  # 100ms, 200ms, 400ms
                        _LOG.error(
                            f"[Persister] DB error despite lock (retry {retry+1}/{max_retries}): {str(e)[:100]}, waiting {backoff:.3f}s"
                        )
                        time.sleep(backoff)
                        continue
                    else:
                        # Not a deadlock or final retry - re-raise
                        _LOG.error(
                            f"[Persister] Failed to persist {len(payload)} rows after {retry+1} retries: {e}"
                        )
                        raise

            # optional debug
            import os

            if os.getenv("BENCH_DEBUG", "").lower() in ("1", "true", "yes"):
                try:
                    head = payload[0]
                    print(
                        f"[BenchPersisterPeewee] upserted {len(payload)} rows, sample: (persona={head['persona_uuid_id']}, case={head['case_id']}, rating={head['rating']})"
                    )
                except Exception:
                    pass

    @classmethod
    def set_progress_count(cls, run_id: int, count: int) -> None:
        """Set the progress count for a run explicitly."""
        cls._progress_counters[run_id] = {"count": count, "last_update": time.time()}

    @classmethod
    def get_progress_count(cls, run_id: int) -> int:
        """Get the current progress count for a run from in-memory cache."""
        counter = cls._progress_counters.get(run_id)
        if counter:
            return counter["count"]
        return 0

    @classmethod
    def reset_progress_count(cls, run_id: int) -> None:
        """Reset the progress count for a run (e.g. on start/restart)."""
        if run_id in cls._progress_counters:
            del cls._progress_counters[run_id]

    def persist_failure(self, fail) -> None:
        with self.db.atomic():
            # Get model_id from model_name
            model_id = None
            if fail.model_id:
                model_id = fail.model_id
            else:
                try:
                    model = self.models.Model.get(
                        self.models.Model.name == fail.model_name
                    )
                    model_id = model.id
                except self.models.Model.DoesNotExist:
                    pass

            self._Fail.create(
                persona_uuid_id=fail.persona_uuid,
                model_id=model_id,
                attempt=fail.attempt,
                error_kind=fail.error_kind,
                raw_text_snippet=fail.raw_text_snippet,
                prompt_snippet=fail.prompt_snippet,
            )
