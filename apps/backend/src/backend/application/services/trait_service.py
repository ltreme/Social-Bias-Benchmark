"""Trait management service."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.infrastructure.storage.db import get_db
from backend.infrastructure.storage.trait_repository import TraitDatabaseRepository


class TraitService:
    """Service for managing traits (adjectives/cases)."""

    def __init__(self):
        self.repo = TraitDatabaseRepository()

    def list_traits(self) -> List[Dict[str, Any]]:
        """List all traits with metadata."""
        counts = self.repo.get_all_linked_result_counts()
        traits = []
        for trait in self.repo.list_all():
            traits.append(
                {
                    "id": str(trait.id),
                    "adjective": str(trait.adjective),
                    "case_template": (
                        str(trait.case_template)
                        if trait.case_template is not None
                        else None
                    ),
                    "category": (
                        str(trait.category) if trait.category is not None else None
                    ),
                    "valence": (
                        int(trait.valence) if trait.valence is not None else None
                    ),
                    "is_active": bool(trait.is_active),
                    "linked_results_n": int(counts.get(str(trait.id), 0)),
                }
            )
        return traits

    def get_trait(self, trait_id: str) -> Optional[Dict[str, Any]]:
        """Get a single trait by ID."""
        trait = self.repo.get_by_id(trait_id)
        if not trait:
            return None
        linked = self.repo.count_linked_results(trait_id)
        return {
            "id": str(trait.id),
            "adjective": str(trait.adjective),
            "case_template": trait.case_template,
            "category": trait.category,
            "valence": trait.valence,
            "is_active": bool(trait.is_active),
            "linked_results_n": int(linked),
        }

    def create_trait(
        self,
        adjective: str,
        case_template: Optional[str] = None,
        category: Optional[str] = None,
        valence: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new trait.

        Raises:
            ValueError: If adjective is empty or already exists
        """
        adjective = self._normalize_adjective(adjective)
        if not adjective:
            raise ValueError("Adjektiv ist erforderlich")
        if self.repo.exists_by_adjective(adjective):
            raise ValueError("Adjektiv existiert bereits")

        new_id = self.repo.generate_next_id()
        # Double-check uniqueness
        if self.repo.get_by_id(new_id):
            raise ValueError(f"Trait ID collision for {new_id}")

        trait = self.repo.create(
            trait_id=new_id,
            adjective=adjective,
            case_template=case_template,
            category=category,
            valence=valence,
            is_active=True,
        )
        return {
            "id": str(trait.id),
            "adjective": str(trait.adjective),
            "case_template": trait.case_template,
            "category": trait.category,
            "valence": trait.valence,
            "is_active": bool(trait.is_active),
            "linked_results_n": 0,
        }

    def update_trait(
        self,
        trait_id: str,
        adjective: str,
        case_template: Optional[str] = None,
        category: Optional[str] = None,
        valence: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update an existing trait.

        Raises:
            ValueError: If trait not found or adjective invalid/duplicate
        """
        trait = self.repo.get_by_id(trait_id)
        if not trait:
            raise ValueError("Trait not found")

        adjective = self._normalize_adjective(adjective)
        if not adjective:
            raise ValueError("Adjektiv ist erforderlich")
        if self.repo.exists_by_adjective(adjective, exclude_id=trait_id):
            raise ValueError("Adjektiv existiert bereits")

        trait = self.repo.update(trait, adjective, case_template, category, valence)
        linked = self.repo.count_linked_results(trait_id)
        return {
            "id": str(trait.id),
            "adjective": str(trait.adjective),
            "case_template": trait.case_template,
            "category": trait.category,
            "valence": trait.valence,
            "is_active": bool(trait.is_active),
            "linked_results_n": int(linked),
        }

    def delete_trait(self, trait_id: str) -> None:
        """Delete a trait.

        Raises:
            ValueError: If trait not found or has linked results
        """
        trait = self.repo.get_by_id(trait_id)
        if not trait:
            raise ValueError("Trait not found")

        linked = self.repo.count_linked_results(trait_id)
        if linked > 0:
            raise ValueError(
                "Trait ist mit Benchmark-Resultaten verknüpft und kann nicht gelöscht werden"
            )

        self.repo.delete(trait)

    def set_trait_active(self, trait_id: str, is_active: bool) -> Dict[str, Any]:
        """Set trait active status.

        Raises:
            ValueError: If trait not found
        """
        trait = self.repo.get_by_id(trait_id)
        if not trait:
            raise ValueError("Trait not found")

        trait = self.repo.set_active(trait, is_active)
        linked = self.repo.count_linked_results(trait_id)
        return {
            "id": str(trait.id),
            "adjective": str(trait.adjective),
            "case_template": trait.case_template,
            "category": trait.category,
            "valence": trait.valence,
            "is_active": bool(trait.is_active),
            "linked_results_n": int(linked),
        }

    def list_categories(self) -> List[str]:
        """List all distinct trait categories."""
        return self.repo.list_categories()

    def export_all_traits(self) -> Tuple[str, str]:
        """Export all traits as CSV.

        Returns:
            Tuple of (csv_content, filename)
        """
        buffer = io.StringIO()
        fieldnames = ["id", "adjective", "category", "valence"]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for trait in self.repo.list_all():
            writer.writerow(
                {
                    "id": str(trait.id),
                    "adjective": str(trait.adjective),
                    "category": (
                        str(trait.category) if trait.category is not None else ""
                    ),
                    "valence": trait.valence if trait.valence is not None else "",
                }
            )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"traits_{timestamp}.csv"
        return buffer.getvalue(), filename

    def export_filtered_traits(self, trait_ids: List[str]) -> Tuple[str, str]:
        """Export specific traits as CSV in given order.

        Args:
            trait_ids: List of trait IDs to export in order

        Returns:
            Tuple of (csv_content, filename)
        """
        buffer = io.StringIO()
        fieldnames = [
            "id",
            "adjective",
            "case_template",
            "category",
            "valence",
            "is_active",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()

        traits_dict = self.repo.get_by_ids(trait_ids)

        # Write rows in the order specified by trait_ids
        for trait_id in trait_ids:
            trait = traits_dict.get(trait_id)
            if trait:
                writer.writerow(
                    {
                        "id": str(trait.id),
                        "adjective": str(trait.adjective),
                        "case_template": (
                            str(trait.case_template)
                            if trait.case_template is not None
                            else ""
                        ),
                        "category": (
                            str(trait.category) if trait.category is not None else ""
                        ),
                        "valence": trait.valence if trait.valence is not None else "",
                        "is_active": "true" if trait.is_active else "false",
                    }
                )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"traits_filtered_{timestamp}.csv"
        return buffer.getvalue(), filename

    def import_traits(self, csv_content: str) -> Dict[str, Any]:
        """Import traits from CSV content.

        Args:
            csv_content: CSV file content as string

        Returns:
            Dict with import statistics and errors
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        if not reader.fieldnames:
            raise ValueError("CSV ohne Header")

        inserted = updated = skipped = 0
        errors: List[str] = []
        db = get_db()

        for idx, row in enumerate(reader, start=2):
            try:
                adjective = self._normalize_adjective(row.get("adjective"))
                if not adjective:
                    raise ValueError(f"Zeile {idx}: 'adjective' fehlt")

                row_id = (row.get("id") or "").strip() or None
                category = (row.get("category") or "").strip() or None
                valence = self._parse_valence((row.get("valence") or "").strip(), idx)

                with db.atomic():
                    target = self.repo.get_by_id(row_id) if row_id else None
                    if target:
                        if self.repo.exists_by_adjective(
                            adjective, exclude_id=target.id
                        ):
                            raise ValueError(f"Zeile {idx}: Adjektiv existiert bereits")
                        self.repo.update(target, adjective, None, category, valence)
                        updated += 1
                    else:
                        if self.repo.exists_by_adjective(adjective):
                            raise ValueError(f"Zeile {idx}: Adjektiv existiert bereits")
                        new_id = row_id or self.repo.generate_next_id()
                        if self.repo.get_by_id(new_id):
                            raise ValueError(
                                f"Zeile {idx}: ID '{new_id}' bereits vergeben"
                            )
                        self.repo.create(
                            trait_id=new_id,
                            adjective=adjective,
                            category=category,
                            valence=valence,
                            is_active=True,
                        )
                        inserted += 1
            except ValueError as exc:
                errors.append(str(exc))
                skipped += 1
            except Exception as exc:
                errors.append(f"Zeile {idx}: {exc}")
                skipped += 1

        return {
            "ok": True,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "total_rows": inserted + updated + skipped,
        }

    @staticmethod
    def _normalize_adjective(value: str | None) -> str:
        """Normalize adjective by stripping whitespace."""
        return (value or "").strip()

    @staticmethod
    def _parse_valence(raw: str | None, row: int) -> int | None:
        """Parse valence from CSV string.

        Raises:
            ValueError: If valence is invalid
        """
        if raw is None or raw == "":
            return None
        try:
            val = int(raw)
        except (TypeError, ValueError):
            raise ValueError(f"Zeile {row}: valence '{raw}' ist ungültig")
        if val < -1 or val > 1:
            raise ValueError(f"Zeile {row}: valence muss zwischen -1 und 1 liegen")
        return val
