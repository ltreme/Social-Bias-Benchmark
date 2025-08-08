import csv
import os
from typing import Iterator, Optional

from benchmark.domain.case import QuestionDto

QUESTION_PATH = "out/questions/gpt-4.5-07-08-25-uuid.csv"


class QuestionRepository:
    """
    Repository for managing questions in the benchmark.
    Provides methods to create, update, and retrieve questions.
    """

    def __init__(self, path: str = None):
        if path is None:
            path = QUESTION_PATH
        self._file_path = path

    def find(self, uuid: str) -> Optional[QuestionDto]:
        """
        Retrieve a question by its UUID.
        """
        with open(self._file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["uuid"] == uuid:
                    return QuestionDto(
                        uuid=row["uuid"],
                        adjective=row["adjective"],
                        question_template=row["question"],
                    )
        return None

    def iter_all(self) -> Iterator[QuestionDto]:
        """
        Retrieve all questions as a lazy iterator to avoid loading all into memory.
        """
        with open(self._file_path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                yield QuestionDto(
                    uuid=row["uuid"],
                    adjective=row["adjective"],
                    question_template=row["question"],
                )

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
