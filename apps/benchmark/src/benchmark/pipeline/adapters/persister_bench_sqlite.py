from __future__ import annotations
from typing import List

from ..ports_bench import BenchPersister, BenchAnswerDto


class BenchPersisterPrint(BenchPersister):
    def persist_results(self, rows: List[BenchAnswerDto]) -> None:
        if not rows:
            return
        print("RESULTS", [
            (r.persona_uuid, r.question_uuid, r.rating, r.model_name, r.template_version)
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
            persona_uuid=r.persona_uuid,
            question_uuid=r.question_uuid,
            model_name=r.model_name,
            template_version=r.template_version,
            gen_time_ms=r.gen_time_ms,
            attempt=r.attempt,
            answer_raw=r.answer_raw,
            rating=r.rating,
        ) for r in rows]

        with self.db.atomic():
            (self._Res
             .insert_many(payload)
             .on_conflict(
                 conflict_target=[self._Res.persona_uuid, self._Res.question_uuid, self._Res.model_name, self._Res.template_version],
                 update={
                    self._Res.answer_raw: self._Res.answer_raw,
                    self._Res.rating: self._Res.rating,
                    self._Res.gen_time_ms: self._Res.gen_time_ms,
                    self._Res.attempt: self._Res.attempt,
                    self._Res.created_at: self._Res.created_at,
                 }
             ).execute())
        # optional debug
        import os
        if os.getenv("BENCH_DEBUG", "").lower() in ("1", "true", "yes"):
            try:
                head = payload[0]
                print(f"[BenchPersisterPeewee] upserted {len(payload)} rows, sample: (persona={head['persona_uuid']}, question={head['question_uuid']}, rating={head['rating']})")
            except Exception:
                pass

    def persist_failure(self, fail) -> None:
        with self.db.atomic():
            self._Fail.create(
                persona_uuid=fail.persona_uuid,
                model_name=fail.model_name,
                attempt=fail.attempt,
                error_kind=fail.error_kind,
                raw_text_snippet=fail.raw_text_snippet,
                prompt_snippet=fail.prompt_snippet,
            )
