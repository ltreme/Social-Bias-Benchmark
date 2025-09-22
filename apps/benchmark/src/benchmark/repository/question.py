import csv
import os
from typing import Iterator, Optional

from benchmark.domain.case import CaseDto

# Simple Likert catalog with columns: id,adjective (no question text anymore)
CASE_PATH = "data/cases/simple_likert.csv"


class CaseRepository:
    """
    Repository for managing questions in the benchmark.
    Provides methods to create, update, and retrieve questions.
    """

    def __init__(self, path: str = None):
        if path is None:
            path = CASE_PATH
        self._file_path = path

    def _row_to_dto(self, row: dict) -> Optional[CaseDto]:
        """Map CSV row (strict schema) to QuestionDto.

        Required schema: id,adjective. Any extra columns are ignored.
        """
        if "id" not in row or "adjective" not in row:
            raise ValueError("Question CSV must have headers: id,adjective")
        qid = str(row["id"]).strip()
        if not qid:
            return None
        return CaseDto(id=qid, adjective=row["adjective"], case_template=None)

    def find(self, id_: str) -> Optional[CaseDto]:
        """
        Retrieve a question by its UUID.
        """
        with open(self._file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if str(row.get("id")) == str(id_):
                    return self._row_to_dto(row)
        return None

    def iter_all(self) -> Iterator[CaseDto]:
        """
        Retrieve all questions as a lazy iterator to avoid loading all into memory.
        """
        with open(self._file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                dto = self._row_to_dto(row)
                if dto:
                    yield dto

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
