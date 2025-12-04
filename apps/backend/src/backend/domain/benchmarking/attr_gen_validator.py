"""Domain logic for attribute generation validation and business rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.infrastructure.storage.models import AttrGenerationRun


# Required persona attributes that must be generated for completion
REQUIRED_PERSONA_ATTRIBUTES = ("name", "appearance", "biography")


class AttrGenValidationError(Exception):
    """Raised when attribute generation validation fails."""

    pass


class AttrGenValidator:
    """Validates attribute generation operations according to business rules."""

    @staticmethod
    def validate_run_deletion(
        run: AttrGenerationRun,
        run_status: str | None,
        has_dependent_benchmarks: bool,
    ) -> None:
        """Validate if an attribute generation run can be safely deleted.

        Args:
            run: The AttrGenerationRun to validate
            run_status: Current status from progress tracker ('queued', 'running', 'done', etc.)
            has_dependent_benchmarks: Whether benchmark runs exist that depend on this attrgen run

        Raises:
            AttrGenValidationError: If deletion is not safe
        """
        # Rule 1: Cannot delete running or queued jobs
        if run_status in {"queued", "running"}:
            raise AttrGenValidationError(
                "Run läuft noch oder ist in der Warteschlange – Löschen nicht möglich"
            )

        # Rule 2: Cannot delete if benchmark runs depend on this data
        if has_dependent_benchmarks:
            raise AttrGenValidationError(
                "Es existieren Benchmarks für dieses Dataset/Modell nach diesem Attr-Run – Löschen gesperrt"
            )

    @staticmethod
    def validate_resume_run(run: AttrGenerationRun, requested_dataset_id: int) -> None:
        """Validate if a run can be resumed with the given dataset.

        Args:
            run: The AttrGenerationRun to resume
            requested_dataset_id: Dataset ID from the request

        Raises:
            AttrGenValidationError: If resume is not valid
        """
        run_dataset_id = int(run.dataset_id.id) if run.dataset_id else None
        if run_dataset_id != requested_dataset_id:
            raise AttrGenValidationError(
                "resume_run_id gehört zu einem anderen Dataset"
            )
