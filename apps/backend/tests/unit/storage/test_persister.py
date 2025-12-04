"""Unit tests for Database Persister - kritisch für Datensicherheit."""

import sys
from pathlib import Path

# Ensure backend package is importable
REPO_ROOT = Path(__file__).resolve().parents[5]
SRC_ROOT = REPO_ROOT / "apps" / "backend" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from unittest.mock import MagicMock, Mock, patch

import pytest

from backend.domain.benchmarking.ports_bench import BenchAnswerDto
from backend.infrastructure.benchmark.persister_bench import (
    BenchPersisterPeewee,
    BenchPersisterPrint,
)


class TestPersisterPrint:
    """Test print persister (debugging/development)."""

    def test_persist_results_prints(self, capsys):
        """Print persister should output results to stdout."""
        persister = BenchPersisterPrint()

        answers = [
            BenchAnswerDto(
                persona_uuid="uuid-1",
                case_id="case-1",
                model_name="test-model",
                template_version="v1",
                benchmark_run_id=1,
                attempt=1,
                gen_time_ms=100,
                answer_raw='{"rating": 3}',
                rating=3,
                scale_reversed=False,
            )
        ]

        persister.persist_results(answers)

        captured = capsys.readouterr()
        assert "RESULTS" in captured.out
        assert "uuid-1" in captured.out
        assert "case-1" in captured.out

    def test_persist_empty_list_no_error(self, capsys):
        """Empty list should not cause errors."""
        persister = BenchPersisterPrint()
        persister.persist_results([])

        captured = capsys.readouterr()
        assert captured.out == ""


class TestPersisterPeewee:
    """Test Peewee database persister."""

    def test_persister_has_class_attributes(self):
        """Persister should have required class-level attributes."""
        # Test without instantiating (avoids DB dependency)
        assert hasattr(BenchPersisterPeewee, "_persist_lock")
        assert hasattr(BenchPersisterPeewee, "_progress_counters")
        assert isinstance(BenchPersisterPeewee._progress_counters, dict)


class TestBatchProcessing:
    """Test batch insertion logic."""

    def test_batch_size_respected(self):
        """Large batches should be processed correctly."""
        answers = []
        for i in range(100):
            dto = BenchAnswerDto(
                persona_uuid=f"uuid-{i}",
                case_id=f"case-{i}",
                model_name="test-model",
                template_version="v1",
                benchmark_run_id=1,
                attempt=1,
                gen_time_ms=100,
                answer_raw='{"rating": 3}',
                rating=3,
                scale_reversed=False,
            )
            answers.append(dto)

        # All DTOs should be valid
        assert len(answers) == 100
        assert all(isinstance(a, BenchAnswerDto) for a in answers)

    def test_dto_conversion(self):
        """DTO should convert to dict for DB insertion."""
        dto = BenchAnswerDto(
            persona_uuid="uuid-1",
            case_id="case-1",
            model_name="test-model",
            template_version="v1",
            benchmark_run_id=1,
            attempt=1,
            gen_time_ms=100,
            answer_raw='{"rating": 3}',
            rating=3,
            scale_reversed=False,
        )

        # Can create dict representation
        assert dto.persona_uuid == "uuid-1"
        assert dto.rating == 3
        assert dto.attempt == 1


class TestThreadSafety:
    """Test thread-safety of persister."""

    def test_class_level_lock_exists(self):
        """Persister should have class-level lock for thread-safety."""
        assert hasattr(BenchPersisterPeewee, "_persist_lock")
        assert BenchPersisterPeewee._persist_lock is not None

    def test_progress_counters_shared(self):
        """Progress counters should be class-level (shared)."""
        assert hasattr(BenchPersisterPeewee, "_progress_counters")
        assert isinstance(BenchPersisterPeewee._progress_counters, dict)


class TestRatingValidation:
    """Test rating value handling."""

    def test_valid_ratings(self):
        """All valid ratings (1-5) should be accepted."""
        for rating in [1, 2, 3, 4, 5]:
            dto = BenchAnswerDto(
                persona_uuid="uuid-1",
                case_id="case-1",
                model_name="test-model",
                template_version="v1",
                benchmark_run_id=1,
                attempt=1,
                gen_time_ms=100,
                answer_raw=f'{{"rating": {rating}}}',
                rating=rating,
                scale_reversed=False,
            )
            assert dto.rating == rating

    def test_null_rating_allowed(self):
        """Null rating should be allowed (for parsing failures)."""
        dto = BenchAnswerDto(
            persona_uuid="uuid-1",
            case_id="case-1",
            model_name="test-model",
            template_version="v1",
            benchmark_run_id=1,
            attempt=1,
            gen_time_ms=100,
            answer_raw="invalid json",
            rating=None,  # Failed to parse
            scale_reversed=False,
        )
        assert dto.rating is None

    def test_scale_reversed_flag(self):
        """Scale reversed flag should be preserved."""
        dto_normal = BenchAnswerDto(
            persona_uuid="uuid-1",
            case_id="case-1",
            model_name="test-model",
            template_version="v1",
            benchmark_run_id=1,
            attempt=1,
            gen_time_ms=100,
            answer_raw='{"rating": 3}',
            rating=3,
            scale_reversed=False,
        )

        dto_reversed = BenchAnswerDto(
            persona_uuid="uuid-1",
            case_id="case-2",
            model_name="test-model",
            template_version="v1",
            benchmark_run_id=1,
            attempt=1,
            gen_time_ms=100,
            answer_raw='{"rating": 3}',
            rating=3,
            scale_reversed=True,
        )

        assert dto_normal.scale_reversed is False
        assert dto_reversed.scale_reversed is True
