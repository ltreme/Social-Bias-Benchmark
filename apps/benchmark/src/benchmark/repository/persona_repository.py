# shared/storage/pipeline_persona_source.py
from __future__ import annotations
from typing import Iterable, Iterator
from benchmark.pipeline.ports import WorkItem, PersonaRepo, PersonaUUID
from benchmark.services.translator import TranslatorService

# Peewee-Modelle & DB-Init
from shared.storage.db import get_db
from shared.storage.models import Persona
from peewee import JOIN
from shared.storage.models import Persona, Country

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

