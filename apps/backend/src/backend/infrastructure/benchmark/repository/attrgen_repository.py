"""Repository for attribute generation data access."""

from __future__ import annotations

from typing import Set

import peewee as pw

from backend.domain.benchmarking.attr_gen_validator import REQUIRED_PERSONA_ATTRIBUTES
from backend.infrastructure.storage.models import (
    AdditionalPersonaAttributes,
    AttrGenerationRun,
    BenchmarkRun,
    DatasetPersona,
)


class AttrGenRepository:
    """Handles database queries for attribute generation."""

    def get_incomplete_persona_uuids(self, run_id: int, dataset_id: int) -> Set[str]:
        """Get UUIDs of personas missing at least one required attribute for this run.

        Args:
            run_id: The attribute generation run ID
            dataset_id: The dataset ID

        Returns:
            Set of persona UUIDs that are incomplete
        """
        query = (
            DatasetPersona.select(
                DatasetPersona.persona_id.alias("pid"),
                pw.fn.COUNT(AdditionalPersonaAttributes.id).alias("c"),
            )
            .join(
                AdditionalPersonaAttributes,
                pw.JOIN.LEFT_OUTER,
                on=(
                    (
                        AdditionalPersonaAttributes.persona_uuid_id
                        == DatasetPersona.persona_id
                    )
                    & (AdditionalPersonaAttributes.attr_generation_run_id == run_id)
                    & (
                        AdditionalPersonaAttributes.attribute_key.in_(
                            REQUIRED_PERSONA_ATTRIBUTES
                        )
                    )
                ),
            )
            .where(DatasetPersona.dataset_id == dataset_id)
            .group_by(DatasetPersona.persona_id)
            .having(
                pw.fn.COUNT(AdditionalPersonaAttributes.id)
                < len(REQUIRED_PERSONA_ATTRIBUTES)
            )
        )
        return {str(row.pid) for row in query}

    def count_completed_personas(self, run_id: int, dataset_id: int) -> int:
        """Count personas with all required attributes for this run.

        Args:
            run_id: The attribute generation run ID
            dataset_id: The dataset ID

        Returns:
            Number of personas with all required attributes
        """
        subquery = (
            AdditionalPersonaAttributes.select(
                AdditionalPersonaAttributes.persona_uuid_id,
                pw.fn.COUNT(AdditionalPersonaAttributes.id).alias("c"),
            )
            .where(
                (AdditionalPersonaAttributes.attr_generation_run_id == run_id)
                & (
                    AdditionalPersonaAttributes.attribute_key.in_(
                        REQUIRED_PERSONA_ATTRIBUTES
                    )
                )
            )
            .group_by(AdditionalPersonaAttributes.persona_uuid_id)
            .having(
                pw.fn.COUNT(AdditionalPersonaAttributes.id)
                >= len(REQUIRED_PERSONA_ATTRIBUTES)
            )
        )
        return subquery.count()

    def count_dataset_personas(self, dataset_id: int) -> int:
        """Count total personas in a dataset.

        Args:
            dataset_id: The dataset ID

        Returns:
            Total number of personas in the dataset
        """
        return (
            DatasetPersona.select()
            .where(DatasetPersona.dataset_id == dataset_id)
            .count()
        )

    def has_dependent_benchmark_runs(self, attrgen_run: AttrGenerationRun) -> bool:
        """Check if benchmark runs exist that depend on this attrgen run.

        A benchmark run is considered dependent if it uses the same dataset and model
        and was created at or after the attrgen run.

        Args:
            attrgen_run: The attribute generation run to check

        Returns:
            True if dependent benchmark runs exist
        """
        try:
            dataset_id = (
                int(attrgen_run.dataset_id.id) if attrgen_run.dataset_id else None
            )
            model_id = int(attrgen_run.model_id.id) if attrgen_run.model_id else None

            if dataset_id is None or model_id is None:
                return False

            return (
                BenchmarkRun.select()
                .where(
                    (BenchmarkRun.dataset_id == dataset_id)
                    & (BenchmarkRun.model_id == model_id)
                    & (BenchmarkRun.created_at >= attrgen_run.created_at)
                )
                .limit(1)
                .exists()
            )
        except Exception:
            # Fail safe: assume dependencies exist
            return True

    def delete_run_attributes(self, run_id: int) -> int:
        """Delete all attributes associated with a run.

        Args:
            run_id: The attribute generation run ID

        Returns:
            Number of attributes deleted
        """
        return (
            AdditionalPersonaAttributes.delete()
            .where(AdditionalPersonaAttributes.attr_generation_run_id == run_id)
            .execute()
        )

    def get_run_by_id(self, run_id: int) -> AttrGenerationRun | None:
        """Get an attribute generation run by ID.

        Args:
            run_id: The run ID

        Returns:
            AttrGenerationRun or None if not found
        """
        return AttrGenerationRun.get_or_none(AttrGenerationRun.id == run_id)

    def get_latest_run_for_dataset(self, dataset_id: int) -> AttrGenerationRun | None:
        """Get the most recent attribute generation run for a dataset.

        Args:
            dataset_id: The dataset ID

        Returns:
            Most recent AttrGenerationRun or None
        """
        return (
            AttrGenerationRun.select()
            .where(AttrGenerationRun.dataset_id == dataset_id)
            .order_by(AttrGenerationRun.id.desc())
            .first()
        )

    def list_runs_for_dataset(
        self, dataset_id: int, limit: int = 25
    ) -> list[AttrGenerationRun]:
        """List attribute generation runs for a dataset.

        Args:
            dataset_id: The dataset ID
            limit: Maximum number of runs to return

        Returns:
            List of AttrGenerationRun ordered by most recent first
        """
        return list(
            AttrGenerationRun.select()
            .where(AttrGenerationRun.dataset_id == dataset_id)
            .order_by(AttrGenerationRun.id.desc())
            .limit(limit)
        )
