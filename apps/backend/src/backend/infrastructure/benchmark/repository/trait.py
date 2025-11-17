from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator, Optional

from backend.domain.benchmarking.trait import TraitDto
from backend.infrastructure.storage.models import Trait


class TraitRepository:
    """
    Repository for managing traits (adjectives) in the benchmark.
    Provides methods to create, update, and retrieve traits from the database.
    """

    def __init__(self, path: str | Path | None = None):
        self._csv_path = Path(path) if path else None

    def _model_to_dto(self, trait_model) -> TraitDto:
        """Map Trait model to TraitDto."""
        return TraitDto(
            id=trait_model.id,
            adjective=trait_model.adjective,
            case_template=trait_model.case_template,
            category=trait_model.category,
            valence=trait_model.valence,
            is_active=getattr(trait_model, "is_active", True),
        )

    def _iter_from_csv(self) -> Iterator[TraitDto]:
        assert self._csv_path is not None
        with self._csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                trait_id = (
                    row.get("id")
                    or row.get("trait_id")
                    or row.get("case_id")
                    or row.get("identifier")
                )
                adjective = row.get("adjective") or row.get("trait") or row.get("label")
                if not trait_id or not adjective:
                    continue
                try:
                    valence = (
                        int(row["valence"])
                        if row.get("valence") not in (None, "")
                        else None
                    )
                except (ValueError, TypeError):
                    valence = None
                yield TraitDto(
                    id=str(trait_id).strip(),
                    adjective=str(adjective).strip(),
                    case_template=row.get("case_template") or row.get("template"),
                    category=row.get("category"),
                    valence=valence,
                    is_active=True,
                )

    def find(self, id_: str) -> Optional[TraitDto]:
        """
        Retrieve a trait by its ID.
        """
        if self._csv_path:
            for trait in self._iter_from_csv():
                if trait.id == id_:
                    return trait
            return None
        try:
            trait = Trait.get(Trait.id == id_)
            return self._model_to_dto(trait)
        except Trait.DoesNotExist:
            return None

    def iter_all(self) -> Iterator[TraitDto]:
        """
        Retrieve all traits as a lazy iterator to avoid loading all into memory.
        """
        if self._csv_path:
            yield from self._iter_from_csv()
            return
        for trait in Trait.select().where((Trait.is_active == True)):
            yield self._model_to_dto(trait)

    def count(self) -> int:
        """
        Count the total number of traits in the repository.
        """
        if self._csv_path:
            return sum(1 for _ in self._iter_from_csv())
        return Trait.select().count()
