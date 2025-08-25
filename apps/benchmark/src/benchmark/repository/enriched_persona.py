import csv
import os
from typing import Optional

from benchmark.domain.persona import EnrichedPersonaDto
from benchmark.repository.abstract_persona import AbstractPersonaRepository
from shared.paths import get_enriched_personas_path


class EnrichedPersonaRepository(AbstractPersonaRepository):
    def __init__(self, model_name: str):
        fieldnames = [
            "uuid",
            "name",
            "age",
            "gender",
            "education",
            "occupation",
            "marriage_status",
            "migration_status",
            "origin",
            "religion",
            "sexuality",
            "appearance",
            "biography",
        ]
        run_id = os.getenv("RUN_ID") or os.getenv("SLURM_JOB_ID")
        file_path = get_enriched_personas_path(model_name, run_id=run_id)
        # Falls Datei/Verzeichnis noch nicht existiert: automatisch anlegen + Header schreiben
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.isdir(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        if not os.path.exists(file_path):
            with open(file_path, mode="w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

        super().__init__(file_path, EnrichedPersonaDto, fieldnames)

    def save(self, persona: EnrichedPersonaDto) -> None:
        file_exists = os.path.isfile(self._file_path)
        with open(self._file_path, mode="a", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=self._fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(vars(persona))

    def find(self, uuid: str) -> Optional[EnrichedPersonaDto]:
        for persona in self.find_all():
            if persona.uuid == uuid:
                return persona
        return None

    def iter_all(self):
        """Iterator über alle gespeicherten Personas.

        Robust gegen fehlende oder leere Datei: liefert dann einfach nichts.
        """
        if not os.path.exists(self._file_path):
            return
        # Leere Datei (nur Header oder komplett leer) -> nichts yielden
        try:
            size = os.path.getsize(self._file_path)
            if size == 0:
                return
        except OSError:
            return
        with open(self._file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if not row:  # leere Zeile
                    continue
                if row.get("age"):
                    try:
                        row["age"] = int(row["age"])
                    except ValueError:
                        # Falls korrupt -> überspringen oder default
                        continue
                yield self._dto_class(**row)

    def find_all(self) -> list[EnrichedPersonaDto]:
        return list(self.iter_all())

    def count(self) -> int:
        """
        Count the total number of questions in the repository.
        Fast path: count newlines in binary mode and adjust for header.
        """
        path = self._file_path
        try:
            size = os.stat(path).st_size
        except FileNotFoundError:
            return 0
        if size == 0:
            return 0

        nl = 0
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                nl += chunk.count(b"\n")
            # Check if last byte is a newline; if not, there's a trailing line
            try:
                f.seek(-1, os.SEEK_END)
                last = f.read(1)
            except OSError:
                last = b"\n"
        total_lines = nl + (0 if last == b"\n" else 1)
        # subtract header line
        return max(total_lines - 1, 0)
