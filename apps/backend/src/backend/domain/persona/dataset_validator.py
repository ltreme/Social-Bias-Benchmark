"""Domain validation logic for dataset operations."""

from __future__ import annotations


class DatasetValidationError(Exception):
    """Raised when dataset validation fails."""

    pass


class DatasetValidator:
    """Validates dataset operations according to business rules."""

    @staticmethod
    def validate_dataset_build_params(
        n: int, temperature: float, age_from: int, age_to: int
    ) -> None:
        """Validate parameters for dataset building.

        Args:
            n: Number of personas to generate
            temperature: Sampling temperature
            age_from: Minimum age
            age_to: Maximum age

        Raises:
            DatasetValidationError: If validation fails
        """
        if n <= 0:
            raise DatasetValidationError("n muss größer als 0 sein")
        if n > 1_000_000:
            raise DatasetValidationError("n darf nicht größer als 1.000.000 sein")
        if temperature < 0 or temperature > 10:
            raise DatasetValidationError("temperature muss zwischen 0 und 10 liegen")
        if age_from < 0 or age_from > 150:
            raise DatasetValidationError("age_from muss zwischen 0 und 150 liegen")
        if age_to < age_from or age_to > 150:
            raise DatasetValidationError("age_to muss >= age_from und <= 150 sein")

    @staticmethod
    def validate_balanced_params(dataset_id: int, n: int, seed: int) -> None:
        """Validate parameters for balanced dataset creation.

        Args:
            dataset_id: Source dataset ID
            n: Target number of personas
            seed: Random seed

        Raises:
            DatasetValidationError: If validation fails
        """
        if dataset_id <= 0:
            raise DatasetValidationError("dataset_id muss größer als 0 sein")
        if n <= 0:
            raise DatasetValidationError("n muss größer als 0 sein")
        if n > 100_000:
            raise DatasetValidationError("n darf nicht größer als 100.000 sein")

    @staticmethod
    def validate_pagination_params(limit: int, offset: int) -> None:
        """Validate pagination parameters.

        Args:
            limit: Number of items per page
            offset: Offset for pagination

        Raises:
            DatasetValidationError: If validation fails
        """
        if limit < 1 or limit > 10000:
            raise DatasetValidationError("limit muss zwischen 1 und 10.000 liegen")
        if offset < 0:
            raise DatasetValidationError("offset muss >= 0 sein")
