import csv
from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional, Type


class AbstractPersonaRepository(ABC):
    def __init__(self, file_path: str, dto_class: Type[Any], fieldnames: list[str]):
        self._file_path = file_path
        self._dto_class = dto_class
        self._fieldnames = fieldnames

    @abstractmethod
    def find(self, uuid: str) -> Optional[Any]:
        pass

    def find_all(self) -> Iterator[Any]:
        """Returns an iterator over all personas in the CSV."""
        with open(self._file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                yield self._dto_class(**row)
