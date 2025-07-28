import csv
import os

from benchmark.domain.persona import EnrichedPersonaDto
from shared.paths import get_enriched_personas_path


class PersonaWriter:
    """Writes enriched persona data to a CSV file."""

    def __init__(self, model_name: str = "default"):
        """
        Initializes the PersonaWriter.
        The file path is determined by get_enriched_personas_path().
        """
        self._file_path = get_enriched_personas_path(model_name)
        self._fieldnames = [
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

    def savePersona(self, persona: EnrichedPersonaDto) -> None:
        """
        Saves a single enriched persona to the CSV file.
        If the file doesn't exist, it creates it with a header.
        If it exists, it appends the persona.

        Args:
            persona (EnrichedPersonaDto): The enriched persona to save.
        """
        file_exists = os.path.isfile(self._file_path)
        with open(self._file_path, mode="a", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=self._fieldnames)
            if not file_exists:
                writer.writeheader()

            writer.writerow(vars(persona))
