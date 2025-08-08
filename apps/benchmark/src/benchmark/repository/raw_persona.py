import csv
from typing import Optional

from benchmark.domain.persona import RawPersonaDto
from benchmark.repository.abstract_persona import AbstractPersonaRepository
from shared.paths import PATH_PERSONAS_CSV


class RawPersonaRepository(AbstractPersonaRepository):
    def __init__(self, file_path: str = PATH_PERSONAS_CSV):
        fieldnames = [
            "uuid",
            "age",
            "gender",
            "education",
            "occupation",
            "marriage_status",
            "migration_status",
            "origin",
            "religion",
            "sexuality",
        ]
        super().__init__(file_path, RawPersonaDto, fieldnames)

    def find(self, uuid: str) -> Optional[RawPersonaDto]:
        for persona in self.find_all():
            if persona.uuid == uuid:
                # Optional: sicherstellen, dass age ein int ist
                persona = persona.__class__(
                    **{**persona.__dict__, "age": int(persona.age)}
                )
                return persona
        return None

    def find_all(self):
        return self.iter_personas()

    def iter_personas(self):
        with open(self._file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                row["age"] = int(row["age"])
                yield self._dto_class(**row)
