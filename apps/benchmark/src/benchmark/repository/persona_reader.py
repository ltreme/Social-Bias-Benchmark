import csv
from typing import List, Optional

from benchmark.domain.persona import RawPersonaDto
from shared.paths import PATH_PERSONAS_CSV


class PersonaReader:
    """Reads persona data from a CSV file."""

    def __init__(self, file_path: str = PATH_PERSONAS_CSV):
        """
        Initializes the PersonaReader.

        Args:
            file_path (str): The path to the persona CSV file.
        """
        self._file_path = file_path

    def find(self, uuid: str) -> Optional[RawPersonaDto]:
        """
        Finds a persona by UUID.

        Args:
            uuid (str): The UUID of the persona to find.

        Returns:
            Optional[RawPersonaDto]: The persona if found, otherwise None.
        """
        with open(self._file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["uuid"] == uuid:
                    return RawPersonaDto(
                        uuid=row["uuid"],
                        age=int(row["age"]),
                        gender=row["gender"],
                        education=row["education"],
                        occupation=row["occupation"],
                        marriage_status=row["marriage_status"],
                        migration_status=row["migration_status"],
                        origin=row["origin"],
                        religion=row["religion"],
                        sexuality=row["sexuality"],
                    )
        return None

    def find_all(self) -> List[RawPersonaDto]:
        """
        Retrieves all personas.

        Returns:
            List[RawPersonaDto]: A list of all personas.
        """
        personas = []
        with open(self._file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                personas.append(
                    RawPersonaDto(
                        uuid=row["uuid"],
                        age=int(row["age"]),
                        gender=row["gender"],
                        education=row["education"],
                        occupation=row["occupation"],
                        marriage_status=row["marriage_status"],
                        migration_status=row["migration_status"],
                        origin=row["origin"],
                        religion=row["religion"],
                        sexuality=row["sexuality"],
                    )
                )
        return personas
