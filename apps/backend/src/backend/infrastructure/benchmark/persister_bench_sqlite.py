from __future__ import annotations

from typing import List

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

        # Retry logic for PostgreSQL deadlocks/serialization failures
        max_retries = 5  # Increased from 3
        import logging
        import time

        _LOG = logging.getLogger(__name__)

        for retry in range(max_retries):
            try:
                start_time = time.time()
                with self.db.atomic():
                    # SQLite: use OR IGNORE to be robust to legacy index names/orders.
                    (self._Res.insert_many(payload).on_conflict_ignore().execute())
                elapsed = time.time() - start_time
                if elapsed > 2.0:
                    _LOG.warning(
                        f"[Persister] Slow INSERT: {elapsed:.2f}s for {len(payload)} rows (retry {retry})"
                    )
                break  # Success, exit retry loop
            except Exception as e:
                error_str = str(e).lower()
                # PostgreSQL deadlock or serialization failure
                if (
                    "deadlock" in error_str
                    or "serialization" in error_str
                    or "timeout" in error_str
                ) and retry < max_retries - 1:
                    wait_time = 0.05 * (
                        2**retry
                    )  # Exponential backoff: 50ms, 100ms, 200ms, 400ms, 800ms
                    _LOG.warning(
                        f"[Persister] DB error (retry {retry+1}/{max_retries}): {str(e)[:100]}, waiting {wait_time:.3f}s"
                    )
                    time.sleep(wait_time)
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
