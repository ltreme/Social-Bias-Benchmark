"""Unit tests for LikertPostProcessor - Output-Parsing ist kritisch."""

import sys
from pathlib import Path

# Ensure backend package is importable
REPO_ROOT = Path(__file__).resolve().parents[5]
SRC_ROOT = REPO_ROOT / "apps" / "backend" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest

from backend.domain.benchmarking.adapters.postprocess.postprocessor_likert import (
    LikertPostProcessor,
)
from backend.domain.benchmarking.ports_bench import (
    BenchPromptSpec,
    BenchWorkItem,
    FailDecision,
    LLMResult,
    OkDecision,
    RetryDecision,
)


class TestLikertPostProcessorValid:
    """Tests für gültige Antworten."""

    @pytest.fixture
    def processor_with_rationale(self):
        return LikertPostProcessor(include_rationale=True)

    @pytest.fixture
    def processor_without_rationale(self):
        return LikertPostProcessor(include_rationale=False)

    @pytest.fixture
    def sample_spec(self):
        """Minimale BenchPromptSpec für Tests."""
        work = BenchWorkItem(
            dataset_id=1,
            persona_uuid="test-uuid",
            persona_context={"name": "Test"},
            case_id="case_001",
            adjective="freundlich",
            case_template=None,
            scale_reversed=False,
        )
        return BenchPromptSpec(
            work=work,
            prompt_text="Test prompt",
            max_new_tokens=128,
            attempt=1,
            model_name="test-model",
            template_version="v1",
            benchmark_run_id=1,
        )

    def test_valid_json_with_rationale(self, processor_with_rationale, sample_spec):
        """Gültiges JSON mit Rationale sollte OkDecision zurückgeben."""
        raw_text = '{"rating": 4, "rationale": "Person wirkt sehr freundlich."}'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor_with_rationale.decide(result)

        assert isinstance(decision, OkDecision)
        assert len(decision.answers) == 1
        assert decision.answers[0].rating == 4
        assert decision.answers[0].persona_uuid == "test-uuid"
        assert decision.answers[0].case_id == "case_001"

    def test_valid_json_without_rationale(
        self, processor_without_rationale, sample_spec
    ):
        """Gültiges JSON ohne Rationale sollte OkDecision zurückgeben."""
        raw_text = '{"rating": 3}'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=80)

        decision = processor_without_rationale.decide(result)

        assert isinstance(decision, OkDecision)
        assert decision.answers[0].rating == 3

    @pytest.mark.parametrize(
        "rating_value,expected",
        [
            (1, 1),
            (2, 2),
            (3, 3),
            (4, 4),
            (5, 5),
        ],
    )
    def test_all_valid_ratings(
        self, processor_with_rationale, sample_spec, rating_value, expected
    ):
        """Alle Ratings 1-5 sollten akzeptiert werden."""
        raw_text = f'{{"rating": {rating_value}, "rationale": "test"}}'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor_with_rationale.decide(result)

        assert isinstance(decision, OkDecision)
        assert decision.answers[0].rating == expected

    def test_float_rating_gets_rounded(self, processor_with_rationale, sample_spec):
        """Float-Ratings sollten gerundet werden."""
        test_cases = [
            (3.4, 3),
            (3.5, 4),  # Banker's rounding
            (4.6, 5),
            (1.2, 1),
        ]

        for float_val, expected in test_cases:
            raw_text = f'{{"rating": {float_val}, "rationale": "test"}}'
            result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

            decision = processor_with_rationale.decide(result)

            assert isinstance(decision, OkDecision), f"Failed for {float_val}"
            assert (
                decision.answers[0].rating == expected
            ), f"Expected {expected} for {float_val}"

    def test_scale_reversed_flag_preserved(self, processor_with_rationale):
        """scale_reversed Flag sollte in BenchAnswerDto übernommen werden."""
        work = BenchWorkItem(
            dataset_id=1,
            persona_uuid="uuid",
            persona_context={"name": "Test"},
            case_id="case",
            adjective="test",
            case_template=None,
            scale_reversed=True,  # REVERSED!
        )
        spec = BenchPromptSpec(
            work=work,
            prompt_text="test",
            max_new_tokens=128,
            attempt=1,
            model_name="model",
            template_version="v1",
            benchmark_run_id=1,
        )

        raw_text = '{"rating": 2, "rationale": "test"}'
        result = LLMResult(spec=spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor_with_rationale.decide(result)

        assert decision.answers[0].scale_reversed is True


class TestLikertPostProcessorInvalid:
    """Tests für ungültige/fehlerhafte Antworten."""

    @pytest.fixture
    def processor(self):
        return LikertPostProcessor(include_rationale=True)

    @pytest.fixture
    def sample_spec(self):
        work = BenchWorkItem(
            dataset_id=1,
            persona_uuid="uuid",
            persona_context={"name": "Test"},
            case_id="case",
            adjective="test",
            case_template=None,
            scale_reversed=False,
        )
        return BenchPromptSpec(
            work=work,
            prompt_text="test",
            max_new_tokens=128,
            attempt=1,
            model_name="model",
            template_version="v1",
            benchmark_run_id=1,
        )

    def test_invalid_json_returns_retry(self, processor, sample_spec):
        """Ungültiges JSON sollte RetryDecision zurückgeben."""
        raw_text = '{"rating": 3, "rationale": "incomplete'  # Fehlendes }
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        assert isinstance(decision, RetryDecision)

    def test_markdown_wrapped_json_gets_unwrapped(self, processor, sample_spec):
        """Markdown-Code-Blocks sollten entfernt werden."""
        raw_text = '```json\n{"rating": 4, "rationale": "test"}\n```'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        # Sollte erfolgreich geparst werden nach Sanitization
        assert isinstance(decision, OkDecision)
        assert decision.answers[0].rating == 4

    def test_rating_out_of_range_low(self, processor, sample_spec):
        """Rating < 1 sollte rejected werden."""
        raw_text = '{"rating": 0, "rationale": "test"}'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        # Sollte RetryDecision sein weil rating=None bleibt
        assert isinstance(decision, (RetryDecision, FailDecision))

    def test_rating_out_of_range_high(self, processor, sample_spec):
        """Rating > 5 sollte rejected werden."""
        raw_text = '{"rating": 6, "rationale": "test"}'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        assert isinstance(decision, (RetryDecision, FailDecision))

    def test_missing_rating_key(self, processor, sample_spec):
        """Fehlendes 'rating' sollte RetryDecision zurückgeben."""
        raw_text = '{"rationale": "only rationale, no rating"}'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        assert isinstance(decision, (RetryDecision, FailDecision))

    def test_prose_instead_of_json(self, processor, sample_spec):
        """Prosa-Antwort sollte RetryDecision zurückgeben."""
        raw_text = "Die Person wirkt sehr freundlich, daher würde ich 4 geben."
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        assert isinstance(decision, RetryDecision)

    def test_string_rating_value(self, processor, sample_spec):
        """String-Rating sollte versucht werden zu konvertieren."""
        raw_text = '{"rating": "3", "rationale": "test"}'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        # Sollte fehlschlagen oder RetryDecision sein
        # (hängt von Implementation ab - Strings sollten nicht akzeptiert werden)
        assert (
            not isinstance(decision, OkDecision) or decision.answers[0].rating is None
        )


class TestRationaleLeakDetection:
    """Tests für Rationale-Leak-Detection (kritisch!)."""

    @pytest.fixture
    def processor_no_rationale(self):
        return LikertPostProcessor(include_rationale=False)

    @pytest.fixture
    def sample_spec(self):
        work = BenchWorkItem(
            dataset_id=1,
            persona_uuid="uuid",
            persona_context={"name": "Test"},
            case_id="case",
            adjective="test",
            case_template=None,
            scale_reversed=False,
        )
        return BenchPromptSpec(
            work=work,
            prompt_text="test",
            max_new_tokens=128,
            attempt=1,
            model_name="model",
            template_version="v1",
            benchmark_run_id=1,
        )

    def test_unexpected_rationale_logs_warning(
        self, processor_no_rationale, sample_spec, caplog
    ):
        """Unerwartete Rationale sollte geloggt werden (Cache-Pollution-Warnung)."""
        raw_text = '{"rating": 3, "rationale": "This should not be here!"}'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor_no_rationale.decide(result)

        # Sollte trotzdem OK sein (rating ist gültig)
        assert isinstance(decision, OkDecision)

        # Aber Warning sollte geloggt werden
        assert any(
            "UNEXPECTED RATIONALE" in record.message for record in caplog.records
        )

    def test_rationale_expected_but_missing_ok(self, sample_spec):
        """Fehlende Rationale bei include_rationale=True ist OK (nicht kritisch)."""
        processor = LikertPostProcessor(include_rationale=True)
        raw_text = '{"rating": 4}'  # Keine rationale
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        # Sollte OK sein - rating ist das wichtigste
        assert isinstance(decision, OkDecision)


class TestEdgeCases:
    """Edge-Cases und spezielle Szenarien."""

    @pytest.fixture
    def processor(self):
        return LikertPostProcessor(include_rationale=True)

    @pytest.fixture
    def sample_spec(self):
        work = BenchWorkItem(
            dataset_id=1,
            persona_uuid="uuid",
            persona_context={"name": "Test"},
            case_id="case",
            adjective="test",
            case_template=None,
            scale_reversed=False,
        )
        return BenchPromptSpec(
            work=work,
            prompt_text="test",
            max_new_tokens=128,
            attempt=1,
            model_name="model",
            template_version="v1",
            benchmark_run_id=1,
        )

    def test_extra_keys_ignored(self, processor, sample_spec):
        """Extra JSON-Keys sollten ignoriert werden."""
        raw_text = (
            '{"rating": 3, "rationale": "test", "extra": "ignored", "another": 123}'
        )
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        assert isinstance(decision, OkDecision)
        assert decision.answers[0].rating == 3

    def test_unicode_in_rationale(self, processor, sample_spec):
        """Unicode-Zeichen in Rationale sollten funktionieren."""
        raw_text = '{"rating": 5, "rationale": "Sehr 👍 freundlich! Émile würde 💯 zustimmen."}'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        assert isinstance(decision, OkDecision)

    def test_very_long_raw_text_truncated(self, processor, sample_spec):
        """Sehr lange raw_text sollte getrimmt werden (answer_raw max 2000)."""
        rationale = "x" * 3000  # Sehr lange Begründung
        raw_text = f'{{"rating": 2, "rationale": "{rationale}"}}'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        assert isinstance(decision, OkDecision)
        assert len(decision.answers[0].answer_raw) <= 2000

    def test_empty_string_response(self, processor, sample_spec):
        """Leere Response sollte RetryDecision zurückgeben."""
        raw_text = ""
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        assert isinstance(decision, RetryDecision)

    def test_null_rating(self, processor, sample_spec):
        """null-Rating sollte rejected werden."""
        raw_text = '{"rating": null, "rationale": "test"}'
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        assert isinstance(decision, (RetryDecision, FailDecision))

    def test_thinking_tags_stripped(self, processor, sample_spec):
        """<think>-Tags sollten entfernt werden (use_thinking_strip=True)."""
        raw_text = (
            '<think>Hmm, ich überlege...</think>\n{"rating": 4, "rationale": "gut"}'
        )
        result = LLMResult(spec=sample_spec, raw_text=raw_text, gen_time_ms=100)

        decision = processor.decide(result)

        # Sollte trotzdem geparst werden nach Stripping
        assert isinstance(decision, OkDecision)
        assert decision.answers[0].rating == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
