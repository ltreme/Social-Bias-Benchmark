# apps/benchmark/src/benchmark/pipeline/adapters/persister_sqlite.py
from __future__ import annotations

from typing import List

from backend.domain.benchmarking.ports import AttributeDto, FailureDto, Persister


class PersisterPrint(Persister):
    def persist_attributes(self, rows: List[AttributeDto]) -> None:
        if not rows:
            return
        print("UPSERT", [(r.persona_uuid, r.attribute_key, r.value) for r in rows])

    def persist_failure(self, fail: FailureDto) -> None:
        print("FAIL  ", fail.persona_uuid, fail.error_kind, "attempt", fail.attempt)

    def update_token_usage(
        self,
        attr_generation_run_id: int,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        """Print token usage (no persistence in print-only mode)."""
        print(
            f"TOKEN_USAGE attrgen_run_id={attr_generation_run_id} prompt={prompt_tokens} "
            f"completion={completion_tokens} total={total_tokens}"
        )


class PersisterPeewee(Persister):
    def __init__(self):
        from backend.infrastructure.storage import models as _models
        from backend.infrastructure.storage.db import get_db

        self.db = get_db()
        self.models = _models

        if not hasattr(self.models, "AdditionalPersonaAttributes"):
            raise ImportError(
                "storage models missing AdditionalPersonaAttributes – adjust PersisterPeewee."
            )
        if not hasattr(self.models, "FailLog"):
            raise ImportError(
                "storage models missing FailLog – adjust PersisterPeewee."
            )

        self._Attr = self.models.AdditionalPersonaAttributes
        self._Fail = self.models.FailLog

    def persist_attributes(self, rows: List[AttributeDto]) -> None:
        if not rows:
            return
        import os

        debug = os.getenv("ATTRGEN_DEBUG", "").lower() in ("1", "true", "yes")
        if debug:
            print(f"[AttrGenPersist] persisting {len(rows)} attributes")
        payload = [
            dict(
                persona_uuid_id=r.persona_uuid,
                attribute_key=r.attribute_key,
                value=r.value,
                attr_generation_run_id=r.attr_generation_run_id,
                attempt=r.attempt,
            )
            for r in rows
        ]

        # Upsert auf Unique(persona_uuid, attribute_key)
        # Upsert and update column values to the incoming (EXCLUDED) values
        # Note: Peewee does not expose EXCLUDED directly; use raw SQL references.
        from peewee import SQL

        # Sanity: require attr_generation_run_id for correct run-scoped uniqueness
        if any(r.get("attr_generation_run_id") in (None, "") for r in payload):
            raise ValueError(
                "attr_generation_run_id missing for attribute upsert; required for run-scoped uniqueness"
            )

        with self.db.atomic():
            (
                self._Attr.insert_many(payload)
                .on_conflict(
                    conflict_target=[
                        self._Attr.attr_generation_run_id,
                        self._Attr.persona_uuid_id,
                        self._Attr.attribute_key,
                    ],
                    update={
                        self._Attr.value: SQL("excluded.value"),
                        self._Attr.attempt: SQL("excluded.attempt"),
                        self._Attr.created_at: SQL("excluded.created_at"),
                    },
                )
                .execute()
            )
        if debug:
            print(f"[AttrGenPersist] wrote {len(rows)} attributes")

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

    def update_token_usage(
        self,
        attr_generation_run_id: int,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        """Update the token usage counters for an attribute generation run."""
        with self.db.atomic():
            run = self.models.AttrGenerationRun.get_by_id(attr_generation_run_id)
            run.total_prompt_tokens = (run.total_prompt_tokens or 0) + prompt_tokens
            run.total_completion_tokens = (
                run.total_completion_tokens or 0
            ) + completion_tokens
            run.total_tokens = (run.total_tokens or 0) + total_tokens
            run.save()
