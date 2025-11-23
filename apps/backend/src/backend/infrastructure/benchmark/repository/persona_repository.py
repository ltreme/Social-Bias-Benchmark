# shared/storage/pipeline_persona_source.py
from __future__ import annotations

from typing import Iterable

from peewee import JOIN

from backend.domain.benchmarking.ports import PersonaRepo, PersonaUUID, WorkItem
from backend.domain.benchmarking.ports_bench import BenchPersonaRepo, BenchWorkItem
from backend.infrastructure.common.translator import TranslatorService
from backend.infrastructure.storage.db import get_db
from backend.infrastructure.storage.models import AdditionalPersonaAttributes as Attr
from backend.infrastructure.storage.models import Country, DatasetPersona, Persona


class PersonaRepository(PersonaRepo):
    """
    Streaming persona source for the pipeline.
    Uses Peewee's iterator() to avoid caching & materialization.
    Only selects the minimal fields needed for prompting.
    """

    def iter_personas(self, dataset_id: int | None = None) -> Iterable[WorkItem]:
        # Ensure DB is initialized by caller (init_database()).
        _ = get_db()

        last_uuid = None
        batch_size = 1000
        translator = TranslatorService()

        while True:
            # Select only minimal fields to reduce IO.
            query = Persona.select(
                Persona.uuid,
                Persona.age,
                Persona.gender,
                Persona.education,
                Persona.occupation,
                Persona.marriage_status,
                Persona.religion,
                Persona.sexuality,
                Country.country_de.alias("origin_name"),
            ).join(Country, JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))

            if dataset_id is not None:
                query = query.join(
                    DatasetPersona,
                    JOIN.INNER,
                    on=(DatasetPersona.persona_id == Persona.uuid),
                ).where(DatasetPersona.dataset_id == dataset_id)
            else:
                query = query.where(True)

            if last_uuid is not None:
                query = query.where(Persona.uuid > last_uuid)

            query = query.order_by(Persona.uuid).limit(batch_size)

            rows = list(query)
            if not rows:
                break

            for row in rows:
                last_uuid = row.uuid
                origin_name = getattr(
                    row, "origin_name", None
                )  # None, wenn kein Country
                persona_minimal = {
                    "Alter": row.age,
                    "Geschlecht": translator.translate(row.gender),
                    "Herkunft": origin_name,
                    "Bildung": row.education,
                    "Beruf": row.occupation,
                    "Familienstand": translator.translate(row.marriage_status),
                    "Religion": translator.translate(row.religion),
                    "Sexualität": translator.translate(row.sexuality),
                }
                yield WorkItem(
                    dataset_id=dataset_id or 0,  # Use 0 as default for all personas
                    persona_uuid=PersonaUUID(str(row.uuid)),
                    persona_minimal=persona_minimal,
                )

    def count(self, dataset_id: int | None) -> int:
        _ = get_db()
        if dataset_id is None:
            return Persona.select().count()
        return (
            DatasetPersona.select()
            .where(DatasetPersona.dataset_id == dataset_id)
            .count()
        )


class PersonaRepositoryByDataset(PersonaRepo):
    """PersonaRepo that streams only personas that are members of a Dataset."""

    def __init__(self, dataset_id: int):
        self.dataset_id = int(dataset_id)

    def iter_personas(
        self, dataset_id: int | None
    ) -> Iterable[WorkItem]:  # dataset_id ignored
        _ = get_db()

        last_uuid = None
        batch_size = 1000
        translator = TranslatorService()

        while True:
            query = (
                Persona.select(
                    Persona.uuid,
                    Persona.age,
                    Persona.gender,
                    Persona.education,
                    Persona.occupation,
                    Persona.marriage_status,
                    Persona.religion,
                    Persona.sexuality,
                    Country.country_de.alias("origin_name"),
                )
                .join(
                    DatasetPersona,
                    JOIN.INNER,
                    on=(DatasetPersona.persona_id == Persona.uuid),
                )
                .switch(Persona)
                .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))
                .where(DatasetPersona.dataset_id == self.dataset_id)
            )

            if last_uuid is not None:
                query = query.where(Persona.uuid > last_uuid)

            query = query.order_by(Persona.uuid).limit(batch_size)

            rows = list(query)
            if not rows:
                break

            for row in rows:
                last_uuid = row.uuid
                origin_name = getattr(row, "origin_name", None)
                persona_minimal = {
                    "Alter": row.age,
                    "Geschlecht": translator.translate(row.gender),
                    "Herkunft": origin_name,
                    "Bildung": row.education,
                    "Beruf": row.occupation,
                    "Familienstand": translator.translate(row.marriage_status),
                    "Religion": translator.translate(row.religion),
                    "Sexualität": translator.translate(row.sexuality),
                }
                yield WorkItem(
                    dataset_id=self.dataset_id,
                    persona_uuid=PersonaUUID(str(row.uuid)),
                    persona_minimal=persona_minimal,
                )

    def count(self, dataset_id: int | None) -> int:
        _ = get_db()
        return (
            DatasetPersona.select()
            .where(DatasetPersona.dataset_id == self.dataset_id)
            .count()
        )


class FullPersonaRepository(BenchPersonaRepo):
    """
    Streams full personas including enriched attributes (name, appearance, biography)
    for the benchmark prompts. Avoids materialization via iterator().
    """

    def __init__(
        self,
        *,
        model_name: str | None = None,
        attr_generation_run_id: int | None = None,
    ):
        # Optional: historic parameter kept for compatibility
        self.model_name = model_name
        # Attributes should be selected from a specific attr-gen run to ensure
        # model-consistent enrichment.
        self.attr_generation_run_id = attr_generation_run_id

    def iter_personas(self, dataset_id: int | None = None):
        _ = get_db()

        last_uuid = None
        batch_size = 1000
        translator = TranslatorService()

        while True:
            query = Persona.select(
                Persona.uuid,
                Persona.age,
                Persona.gender,
                Persona.education,
                Persona.occupation,
                Persona.marriage_status,
                Persona.religion,
                Persona.sexuality,
                Country.country_de.alias("origin_name"),
            ).join(Country, JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))

            if dataset_id is not None:
                query = query.join(
                    DatasetPersona,
                    JOIN.INNER,
                    on=(DatasetPersona.persona_id == Persona.uuid),
                ).where(DatasetPersona.dataset_id == dataset_id)
            else:
                query = query.where(True)

            if last_uuid is not None:
                query = query.where(Persona.uuid > last_uuid)

            query = query.order_by(Persona.uuid).limit(batch_size)

            rows = list(query)
            if not rows:
                break

            for row in rows:
                last_uuid = row.uuid
                origin_name = getattr(row, "origin_name", None)

                # Fetch enriched attributes for this persona. If a specific
                # attr_generation_run_id is provided, restrict to that run.
                attrs_query = Attr.select(Attr.attribute_key, Attr.value).where(
                    Attr.persona_uuid_id == row.uuid
                )
                if self.attr_generation_run_id is not None:
                    attrs_query = attrs_query.where(
                        Attr.attr_generation_run_id == int(self.attr_generation_run_id)
                    )
                attrs = attrs_query
                attr_map = {a.attribute_key: a.value for a in attrs}

                persona_ctx = {
                    "name": attr_map.get("name"),
                    "appearance": attr_map.get("appearance"),
                    "biography": attr_map.get("biography"),
                    "Alter": row.age,
                    "Geschlecht": translator.translate(row.gender),
                    "Herkunft": origin_name,
                    "Bildung": row.education,
                    "Beruf": row.occupation,
                    "Familienstand": translator.translate(row.marriage_status),
                    "Religion": translator.translate(row.religion),
                    "Sexualität": translator.translate(row.sexuality),
                }

                yield BenchWorkItem(
                    dataset_id=dataset_id or 0,  # Use 0 as default for all personas
                    persona_uuid=PersonaUUID(str(row.uuid)),
                    persona_context=persona_ctx,
                    case_id="",  # filled later
                    adjective="",
                    case_template=None,
                )

    def count(self, dataset_id: int | None) -> int:
        _ = get_db()
        if dataset_id is None:
            return Persona.select().count()
        return (
            DatasetPersona.select()
            .where(DatasetPersona.dataset_id == dataset_id)
            .count()
        )


class FullPersonaRepositoryByDataset(BenchPersonaRepo):
    """
    Streams personas that are members of a Dataset (DatasetPersona).
    """

    def __init__(
        self,
        dataset_id: int,
        *,
        model_name: str | None = None,
        attr_generation_run_id: int | None = None,
    ):
        self.dataset_id = int(dataset_id)
        self.model_name = model_name
        self.attr_generation_run_id = attr_generation_run_id

    def iter_personas(
        self, dataset_id: int | None
    ) -> Iterable[BenchWorkItem]:  # dataset_id unused, uses self.dataset_id
        _ = get_db()

        last_uuid = None
        batch_size = 1000
        translator = TranslatorService()

        while True:
            query = (
                Persona.select(
                    Persona.uuid,
                    Persona.age,
                    Persona.gender,
                    Persona.education,
                    Persona.occupation,
                    Persona.marriage_status,
                    Persona.religion,
                    Persona.sexuality,
                    Country.country_de.alias("origin_name"),
                )
                .join(
                    DatasetPersona,
                    JOIN.INNER,
                    on=(DatasetPersona.persona_id == Persona.uuid),
                )
                .switch(Persona)
                .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))
                .where(DatasetPersona.dataset_id == self.dataset_id)
            )

            if last_uuid is not None:
                query = query.where(Persona.uuid > last_uuid)

            query = query.order_by(Persona.uuid).limit(batch_size)

            rows = list(query)
            if not rows:
                break

            for row in rows:
                last_uuid = row.uuid
                origin_name = getattr(row, "origin_name", None)
                # Restrict attributes to the provided attr-generation run when specified
                attrs_query = Attr.select(Attr.attribute_key, Attr.value).where(
                    Attr.persona_uuid_id == row.uuid
                )
                if self.attr_generation_run_id is not None:
                    attrs_query = attrs_query.where(
                        Attr.attr_generation_run_id == int(self.attr_generation_run_id)
                    )
                attr_map = {a.attribute_key: a.value for a in attrs_query}

                persona_ctx = {
                    "name": attr_map.get("name"),
                    "appearance": attr_map.get("appearance"),
                    "biography": attr_map.get("biography"),
                    "Alter": row.age,
                    "Geschlecht": translator.translate(row.gender),
                    "Herkunft": origin_name,
                    "Bildung": row.education,
                    "Beruf": row.occupation,
                    "Familienstand": translator.translate(row.marriage_status),
                    "Religion": translator.translate(row.religion),
                    "Sexualität": translator.translate(row.sexuality),
                }

                yield BenchWorkItem(
                    dataset_id=self.dataset_id,
                    persona_uuid=PersonaUUID(str(row.uuid)),
                    persona_context=persona_ctx,
                    case_id="",
                    adjective="",
                    case_template=None,
                )

    def count(self, dataset_id: int) -> int:
        _ = get_db()
        return (
            DatasetPersona.select()
            .where(DatasetPersona.dataset_id == self.dataset_id)
            .count()
        )
