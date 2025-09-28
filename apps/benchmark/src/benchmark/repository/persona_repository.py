# shared/storage/pipeline_persona_source.py
from __future__ import annotations
from typing import Iterable, Iterator
from benchmark.pipeline.ports import WorkItem, PersonaRepo, PersonaUUID
from benchmark.pipeline.ports_bench import BenchPersonaRepo, BenchWorkItem
from benchmark.services.translator import TranslatorService

# Peewee-Modelle & DB-Init
from shared.storage.db import get_db
from shared.storage.models import Persona
from peewee import JOIN
from shared.storage.models import Persona, Country
from shared.storage.models import DatasetPersona

class PersonaRepository(PersonaRepo):
    """
    Streaming persona source for the pipeline.
    Uses Peewee's iterator() to avoid caching & materialization.
    Only selects the minimal fields needed for prompting.
    """

    def iter_personas(self, dataset_id: int | None = None) -> Iterable[WorkItem]:
        # Ensure DB is initialized by caller (init_database()).
        _ = get_db()

        # Select only minimal fields to reduce IO.
        query = (
            Persona
            .select(
                Persona.uuid, Persona.age, Persona.gender,
                Persona.education, Persona.occupation, Persona.marriage_status,
                Persona.religion, Persona.sexuality,
                Country.country_de.alias("origin_name"),
            )
            .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))
        )
        
        if dataset_id is not None:
            query = (
                query
                .join(DatasetPersona, JOIN.INNER, on=(DatasetPersona.persona_id == Persona.uuid))
                .where(DatasetPersona.dataset_id == dataset_id)
            )
        else:
            query = query.where(True)

        translator = TranslatorService()

        for row in query.iterator():
            origin_name = getattr(row, "origin_name", None)  # None, wenn kein Country
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


class PersonaRepositoryByDataset(PersonaRepo):
    """PersonaRepo that streams only personas that are members of a Dataset."""
    def __init__(self, dataset_id: int):
        self.dataset_id = int(dataset_id)

    def iter_personas(self, dataset_id: int):  # dataset_id ignored here, uses self.dataset_id
        _ = get_db()
        query = (
            Persona
            .select(
                Persona.uuid, Persona.age, Persona.gender,
                Persona.education, Persona.occupation, Persona.marriage_status,
                Persona.religion, Persona.sexuality,
                Country.country_de.alias("origin_name"),
            )
            .join(DatasetPersona, JOIN.INNER, on=(DatasetPersona.persona_id == Persona.uuid))
            .switch(Persona)
            .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))
            .where(DatasetPersona.dataset_id == self.dataset_id)
        )

        translator = TranslatorService()

        for row in query.iterator():
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


class FullPersonaRepository(BenchPersonaRepo):
    """
    Streams full personas including enriched attributes (name, appearance, biography)
    for the benchmark prompts. Avoids materialization via iterator().
    """

    def __init__(self, *, model_name: str | None = None):
        # Optional model_name to filter AdditionalPersonaAttributes per model
        self.model_name = model_name

    def iter_personas(self, dataset_id: int | None = None):
        _ = get_db()
        query = (
            Persona
            .select(
                Persona.uuid, Persona.age, Persona.gender,
                Persona.education, Persona.occupation, Persona.marriage_status,
                Persona.religion, Persona.sexuality,
                Country.country_de.alias("origin_name"),
            )
            .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))
        )
        
        if dataset_id is not None:
            query = (
                query
                .join(DatasetPersona, JOIN.INNER, on=(DatasetPersona.persona_id == Persona.uuid))
                .where(DatasetPersona.dataset_id == dataset_id)
            )
        else:
            query = query.where(True)

        from shared.storage.models import AdditionalPersonaAttributes as Attr
        translator = TranslatorService()

        for row in query.iterator():
            origin_name = getattr(row, "origin_name", None)

            # fetch enriched attributes for this persona (optionally filter by model)
            # NOTE: attr_generation_run_id is an integer FK. Filtering by model_name is incorrect.
            # Until we thread the specific AttrGenerationRun.id to this repo, don't filter here.
            attrs_query = Attr.select(Attr.attribute_key, Attr.value).where(Attr.persona_uuid_id == row.uuid)
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


class FullPersonaRepositoryByDataset(BenchPersonaRepo):
    """
    Streams personas that are members of a Dataset (DatasetPersona).
    """
    def __init__(self, dataset_id: int, *, model_name: str | None = None):
        self.dataset_id = int(dataset_id)
        self.model_name = model_name

    def iter_personas(self, dataset_id: int) -> Iterable[BenchWorkItem]:  # dataset_id unused, uses self.dataset_id
        _ = get_db()
        query = (
            Persona
            .select(
                Persona.uuid, Persona.age, Persona.gender,
                Persona.education, Persona.occupation, Persona.marriage_status,
                Persona.religion, Persona.sexuality,
                Country.country_de.alias("origin_name"),
            )
            .join(DatasetPersona, JOIN.INNER, on=(DatasetPersona.persona_id == Persona.uuid))
            .switch(Persona)
            .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))
            .where(DatasetPersona.dataset_id == self.dataset_id)
        )

        from shared.storage.models import AdditionalPersonaAttributes as Attr
        translator = TranslatorService()

        for row in query.iterator():
            origin_name = getattr(row, "origin_name", None)
            # See note above: do not filter by model_name here, the FK is a run id.
            attrs_query = Attr.select(Attr.attribute_key, Attr.value).where(Attr.persona_uuid_id == row.uuid)
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
