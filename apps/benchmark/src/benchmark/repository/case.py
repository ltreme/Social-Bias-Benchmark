import os
import sys
from typing import Iterator, Optional

from benchmark.domain.case import CaseDto

# Add shared src to path for imports
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SHARED_SRC = os.path.join(REPO_ROOT, "apps", "shared", "src")
if SHARED_SRC not in sys.path:
    sys.path.insert(0, SHARED_SRC)

from shared.storage.models import Case


class CaseRepository:
    """
    Repository for managing cases in the benchmark.
    Provides methods to create, update, and retrieve cases from the database.
    """

    def __init__(self):
        pass

    def _model_to_dto(self, case_model) -> CaseDto:
        """Map Case model to CaseDto."""
        return CaseDto(id=case_model.id, adjective=case_model.adjective, case_template=case_model.case_template)

    def find(self, id_: str) -> Optional[CaseDto]:
        """
        Retrieve a case by its ID.
        """
        try:
            case = Case.get(Case.id == id_)
            return self._model_to_dto(case)
        except Case.DoesNotExist:
            return None

    def iter_all(self) -> Iterator[CaseDto]:
        """
        Retrieve all cases as a lazy iterator to avoid loading all into memory.
        """
        for case in Case.select():
            yield self._model_to_dto(case)

    def count(self) -> int:
        """
        Count the total number of cases in the repository.
        """
        return Case.select().count()
