# apps/benchmark/src/benchmark/pipeline/adapters/persister_sqlite.py
from __future__ import annotations
from typing import List
from ..ports import Persister, AttributeDto, FailureDto

class PersisterPrint(Persister):
    def persist_attributes(self, rows: List[AttributeDto]) -> None:
        if not rows:
            return
        print("UPSERT", [(r.persona_uuid, r.attribute_key, r.value) for r in rows])

    def persist_failure(self, fail: FailureDto) -> None:
        print("FAIL  ", fail.persona_uuid, fail.error_kind, "attempt", fail.attempt)

class PersisterPeewee(Persister):
    def __init__(self):
        from shared.storage.db import get_db
        from shared.storage import models as _models
        self.db = get_db()
        self.models = _models

        if not hasattr(self.models, "AdditionalPersonaAttributes"):
            raise ImportError("shared.storage.models.AdditionalPersonaAttributes not found – adjust PersisterPeewee.")
        if not hasattr(self.models, "FailLog"):
            raise ImportError("shared.storage.models.FailLog not found – adjust PersisterPeewee.")

        self._Attr = self.models.AdditionalPersonaAttributes
        self._Fail = self.models.FailLog

    def persist_attributes(self, rows: List[AttributeDto]) -> None:
        if not rows:
            return
        print(f"PERSISTING {len(rows)} attributes")
        payload = [dict(
            persona_uuid_id=r.persona_uuid,
            attribute_key=r.attribute_key,
            value=r.value,
            attr_generation_run_id=r.attr_generation_run_id,
            attempt=r.attempt,
        ) for r in rows]

        # Upsert auf Unique(persona_uuid, attribute_key)
        with self.db.atomic():
            (self._Attr
            .insert_many(payload)
            .on_conflict(
                conflict_target=[self._Attr.persona_uuid_id, self._Attr.attribute_key],
                update={
                    self._Attr.value: self._Attr.value,           # oder EXCLUDED.value
                    self._Attr.attr_generation_run_id: self._Attr.attr_generation_run_id,
                    self._Attr.attempt: self._Attr.attempt,
                    self._Attr.created_at: self._Attr.created_at, # aktualisiert timestamp
                })
            .execute())
        print(f"PERSISTED {len(rows)} attributes successfully")

    def persist_failure(self, fail: FailureDto) -> None:
        with self.db.atomic():
            self._Fail.create(
                persona_uuid_id=fail.persona_uuid,
                model_id=fail.model_id,
                attempt=fail.attempt,
                error_kind=fail.error_kind,
                raw_text_snippet=fail.raw_text_snippet,
                prompt_snippet=fail.prompt_snippet,
            )
