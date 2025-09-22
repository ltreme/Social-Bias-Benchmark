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

    def iter_personas(self, gen_id: int) -> Iterable[WorkItem]:
        # Ensure DB is initialized by caller (init_database()).
        _ = get_db()

        # Select only minimal fields to reduce IO.
        query = (
            Persona
            .select(
                Persona.uuid, Persona.gen_id, Persona.age, Persona.gender,
                Persona.education, Persona.occupation, Persona.marriage_status,
                Persona.religion, Persona.sexuality,
                Country.country_de.alias("origin_name"),
            )
            .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin == Country.id))
            .where(Persona.gen_id == gen_id)
        )

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
                gen_id=row.gen_id,
                persona_uuid=PersonaUUID(str(row.uuid)),
                persona_minimal=persona_minimal,
            )


class PersonaRepositoryByDataset(PersonaRepo):
    """PersonaRepo that streams only personas that are members of a Dataset."""
    def __init__(self, dataset_id: int):
        self.dataset_id = int(dataset_id)

    def iter_personas(self, gen_id: int):  # gen_id ignored here
        _ = get_db()
        query = (
            Persona
            .select(
                Persona.uuid, Persona.gen_id, Persona.age, Persona.gender,
                Persona.education, Persona.occupation, Persona.marriage_status,
                Persona.religion, Persona.sexuality,
                Country.country_de.alias("origin_name"),
            )
            .join(DatasetPersona, JOIN.INNER, on=(DatasetPersona.persona == Persona.uuid))
            .switch(Persona)
            .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin == Country.id))
            .where(DatasetPersona.dataset == self.dataset_id)
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
                gen_id=row.gen_id,
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

    def iter_personas(self, gen_id: int):
        _ = get_db()
        query = (
            Persona
            .select(
                Persona.uuid, Persona.gen_id, Persona.age, Persona.gender,
                Persona.education, Persona.occupation, Persona.marriage_status,
                Persona.religion, Persona.sexuality,
                Country.country_de.alias("origin_name"),
            )
            .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin == Country.id))
            .where(Persona.gen_id == gen_id)
        )

        from shared.storage.models import AdditionalPersonaAttributes as Attr
        translator = TranslatorService()

        for row in query.iterator():
            origin_name = getattr(row, "origin_name", None)

            # fetch enriched attributes for this persona (optionally filter by model)
            attrs_query = Attr.select(Attr.attribute_key, Attr.value).where(Attr.persona_uuid == row.uuid)
            if self.model_name:
                attrs_query = attrs_query.where(Attr.model_name == self.model_name)
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
                gen_id=row.gen_id,
                persona_uuid=PersonaUUID(str(row.uuid)),
                persona_context=persona_ctx,
                case_id="",  # filled later
                adjective="",
                case_template=None,
            )


class FullPersonaRepositoryByDataset(BenchPersonaRepo):
    """
    Streams personas that are members of a Dataset (DatasetPersona).
    Ignores the gen_id passed to iter_personas; uses dataset_id instead.
    """
    def __init__(self, dataset_id: int, *, model_name: str | None = None):
        self.dataset_id = int(dataset_id)
        self.model_name = model_name

    def iter_personas(self, gen_id: int) -> Iterable[BenchWorkItem]:  # gen_id unused
        _ = get_db()
        query = (
            Persona
            .select(
                Persona.uuid, Persona.gen_id, Persona.age, Persona.gender,
                Persona.education, Persona.occupation, Persona.marriage_status,
                Persona.religion, Persona.sexuality,
                Country.country_de.alias("origin_name"),
            )
            .join(DatasetPersona, JOIN.INNER, on=(DatasetPersona.persona == Persona.uuid))
            .switch(Persona)
            .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin == Country.id))
            .where(DatasetPersona.dataset == self.dataset_id)
        )

        from shared.storage.models import AdditionalPersonaAttributes as Attr
        translator = TranslatorService()

        for row in query.iterator():
            origin_name = getattr(row, "origin_name", None)
            attrs_query = Attr.select(Attr.attribute_key, Attr.value).where(Attr.persona_uuid == row.uuid)
            if self.model_name:
                attrs_query = attrs_query.where(Attr.model_name == self.model_name)
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
                gen_id=row.gen_id,
                persona_uuid=PersonaUUID(str(row.uuid)),
                persona_context=persona_ctx,
                case_id="",
                adjective="",
                case_template=None,
            )
