from __future__ import annotations
from typing import List

from ..ports_bench import BenchPersister, BenchAnswerDto


class BenchPersisterPrint(BenchPersister):
    def persist_results(self, rows: List[BenchAnswerDto]) -> None:
        if not rows:
            return
        print("RESULTS", [
            (r.persona_uuid, r.case_id, r.rating, r.model_name, r.template_version, r.benchmark_run_id)
            for r in rows
        ])

    def persist_failure(self, fail) -> None:
        print("FAIL  ", fail.persona_uuid, fail.error_kind, "attempt", fail.attempt)


class BenchPersisterPeewee(BenchPersister):
    def __init__(self):
        from shared.storage.db import get_db
        from shared.storage import models as _models
        self.db = get_db()
        self.models = _models

        if not hasattr(self.models, "BenchmarkResult"):
            raise ImportError("shared.storage.models.BenchmarkResult not found – add model.")
        if not hasattr(self.models, "FailLog"):
            raise ImportError("shared.storage.models.FailLog not found – adjust persister.")

        self._Res = self.models.BenchmarkResult
        self._Fail = self.models.FailLog

    def persist_results(self, rows: List[BenchAnswerDto]) -> None:
        if not rows:
            return
        payload = [dict(
            persona_uuid_id=r.persona_uuid,
            case_id=r.case_id,
            benchmark_run_id=r.benchmark_run_id,
            attempt=r.attempt,
            answer_raw=r.answer_raw,
            rating=r.rating,
        ) for r in rows]

        with self.db.atomic():
            (self._Res
            .insert_many(payload)
            .on_conflict(
                conflict_target=[self._Res.persona_uuid_id, self._Res.case_id, self._Res.benchmark_run_id],
                update={
                    self._Res.answer_raw: self._Res.answer_raw,
                    self._Res.rating: self._Res.rating,
                    self._Res.attempt: self._Res.attempt,
                    self._Res.created_at: self._Res.created_at,
                }
            ).execute())
        # optional debug
        import os
        if os.getenv("BENCH_DEBUG", "").lower() in ("1", "true", "yes"):
            try:
                head = payload[0]
                print(f"[BenchPersisterPeewee] upserted {len(payload)} rows, sample: (persona={head['persona_uuid_id']}, case={head['case_id']}, rating={head['rating']})")
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
                    model = self.models.Model.get(self.models.Model.name == fail.model_name)
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
