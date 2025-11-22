"""Repository for trait persistence operations."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from peewee import fn

from backend.infrastructure.storage.models import BenchmarkResult, Trait


class TraitDatabaseRepository:
    """Repository for trait database operations."""

    def list_all(self) -> List[Trait]:
        """List all traits ordered by ID."""
        return list(Trait.select().order_by(Trait.id.asc()))

    def get_by_id(self, trait_id: str) -> Optional[Trait]:
        """Get trait by ID."""
        return Trait.get_or_none(Trait.id == trait_id)

    def get_by_ids(self, trait_ids: List[str]) -> Dict[str, Trait]:
        """Get multiple traits by IDs.

        Returns:
            Dict mapping trait_id to Trait object
        """
        traits_dict = {}
        for trait in Trait.select().where(Trait.id.in_(trait_ids)):
            traits_dict[str(trait.id)] = trait
        return traits_dict

    def exists_by_adjective(
        self, adjective: str, exclude_id: Optional[str] = None
    ) -> bool:
        """Check if trait with adjective exists (case-insensitive).

        Args:
            adjective: The adjective to check
            exclude_id: Optional trait ID to exclude from check
        """
        if not adjective:
            return False
        query = Trait.select().where(fn.LOWER(Trait.adjective) == adjective.lower())
        if exclude_id is not None:
            query = query.where(Trait.id != exclude_id)
        return query.exists()

    def create(
        self,
        trait_id: str,
        adjective: str,
        case_template: Optional[str] = None,
        category: Optional[str] = None,
        valence: Optional[int] = None,
        is_active: bool = True,
    ) -> Trait:
        """Create a new trait."""
        return Trait.create(
            id=trait_id,
            adjective=adjective,
            case_template=case_template,
            category=category,
            valence=valence,
            is_active=is_active,
        )

    def update(
        self,
        trait: Trait,
        adjective: str,
        case_template: Optional[str] = None,
        category: Optional[str] = None,
        valence: Optional[int] = None,
    ) -> Trait:
        """Update an existing trait."""
        trait.adjective = adjective
        trait.case_template = case_template
        trait.category = category
        trait.valence = valence
        trait.save()
        return trait

    def set_active(self, trait: Trait, is_active: bool) -> Trait:
        """Set trait active status."""
        trait.is_active = is_active
        trait.save()
        return trait

    def delete(self, trait: Trait) -> None:
        """Delete a trait."""
        trait.delete_instance()

    def count_linked_results(self, trait_id: str) -> int:
        """Count benchmark results linked to a trait."""
        return (
            BenchmarkResult.select().where(BenchmarkResult.case_id == trait_id).count()
        )

    def get_all_linked_result_counts(self) -> Dict[str, int]:
        """Get result counts for all traits using SQL aggregation.

        Returns:
            Dict mapping trait_id to result count
        """
        # Use SQL GROUP BY instead of fetching all rows
        query = BenchmarkResult.select(
            BenchmarkResult.case_id,
            fn.COUNT(BenchmarkResult.id).alias("count"),
        ).group_by(BenchmarkResult.case_id)
        return {str(row.case_id): int(row.count) for row in query}

    def list_categories(self) -> List[str]:
        """List all distinct non-empty trait categories."""
        query = (
            Trait.select(Trait.category)
            .where((Trait.category.is_null(False)) & (Trait.category != ""))
            .distinct()
            .order_by(Trait.category.asc())
        )
        return [str(row.category) for row in query if row.category]

    def generate_next_id(self) -> str:
        """Generate the next trait ID in the form g%d.

        Increments the max present number in IDs matching pattern g\\d+.
        """
        pat = re.compile(r"^g(\d+)$")
        max_n = 0
        for c in Trait.select(Trait.id):
            m = pat.match(str(c.id))
            if m:
                try:
                    n = int(m.group(1))
                except ValueError:
                    continue
                if n > max_n:
                    max_n = n
        return f"g{max_n + 1}"
