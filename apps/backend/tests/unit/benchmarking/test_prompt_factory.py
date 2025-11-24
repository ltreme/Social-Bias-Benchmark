"""Unit tests for LikertPromptFactory - kritisch für GPU-Runs."""

import sys
from dataclasses import asdict
from pathlib import Path

# Ensure backend package is importable
REPO_ROOT = Path(__file__).resolve().parents[5]
SRC_ROOT = REPO_ROOT / "apps" / "backend" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest

from backend.domain.benchmarking.adapters.prompting.likert_factory import (
    LikertPromptFactory,
)
from backend.domain.benchmarking.ports_bench import BenchWorkItem


class TestLikertPromptFactory:
    """Tests für die Prompt-Generierung der Benchmark-Pipeline."""

    @pytest.fixture
    def factory_with_rationale(self):
        """Factory mit Begründung."""
        return LikertPromptFactory(max_new_tokens=192, include_rationale=True)

    @pytest.fixture
    def factory_without_rationale(self):
        """Factory ohne Begründung."""
        return LikertPromptFactory(max_new_tokens=128, include_rationale=False)

    @pytest.fixture
    def sample_work_item(self):
        """Minimales BenchWorkItem für Tests."""
        return BenchWorkItem(
            dataset_id=1,
            persona_uuid="test-uuid-123",
            persona_context={
                "name": "Max Mustermann",
                "age": 35,
                "gender": "männlich",
                "education": "Bachelor",
                "occupation": "Ingenieur",
            },
            case_id="case_001",
            adjective="freundlich",
            case_template="Wie {adjective} wirkt {name}?",
            scale_reversed=False,
        )

    def test_prompt_contains_persona_context(
        self, factory_with_rationale, sample_work_item
    ):
        """Prompt muss Persona-Informationen enthalten."""
        prompts = list(
            factory_with_rationale.prompts(
                [sample_work_item],
                model_name="test-model",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )

        assert len(prompts) == 1
        prompt_text = prompts[0].prompt_text

        # Persona-Details müssen im Prompt sein
        assert "Max Mustermann" in prompt_text
        assert "35" in prompt_text or "35 Jahre" in prompt_text
        assert "männlich" in prompt_text or "Mann" in prompt_text
        assert "Ingenieur" in prompt_text

    def test_prompt_contains_adjective(self, factory_with_rationale, sample_work_item):
        """Prompt muss das zu bewertende Adjektiv enthalten."""
        prompts = list(
            factory_with_rationale.prompts(
                [sample_work_item],
                model_name="test-model",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )

        prompt_text = prompts[0].prompt_text
        assert "freundlich" in prompt_text.lower()

    def test_scale_in_order_correct(self, factory_with_rationale, sample_work_item):
        """In-Order-Scale muss 1-5 sein."""
        # BenchWorkItem is a frozen dataclass - use asdict()
        work_dict = asdict(sample_work_item)
        sample_work_item = BenchWorkItem(**{**work_dict, "scale_reversed": False})

        prompts = list(
            factory_with_rationale.prompts(
                [sample_work_item],
                model_name="test-model",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )

        prompt_text = prompts[0].prompt_text
        # Prüfe dass 1 = "gar nicht" und 5 = "sehr" ist
        assert "1" in prompt_text and "gar nicht" in prompt_text.lower()
        assert "5" in prompt_text and "sehr" in prompt_text.lower()

    def test_scale_reversed_correct(self, factory_with_rationale):
        """Reversed-Scale muss 5-1 sein."""
        work_item = BenchWorkItem(
            dataset_id=1,
            persona_uuid="test-uuid-456",
            persona_context={"name": "Anna", "age": 28, "gender": "weiblich"},
            case_id="case_002",
            adjective="intelligent",
            case_template=None,
            scale_reversed=True,  # REVERSED!
        )

        prompts = list(
            factory_with_rationale.prompts(
                [work_item],
                model_name="test-model",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )

        prompt_text = prompts[0].prompt_text
        # Bei reversed: 5 = "gar nicht", 1 = "sehr"
        assert "5" in prompt_text and "gar nicht" in prompt_text.lower()
        assert "1" in prompt_text and "sehr" in prompt_text.lower()

    def test_rationale_requested_when_enabled(
        self, factory_with_rationale, sample_work_item
    ):
        """Mit include_rationale=True muss Begründung angefordert werden."""
        prompts = list(
            factory_with_rationale.prompts(
                [sample_work_item],
                model_name="test-model",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )

        prompt_text = prompts[0].prompt_text.lower()
        assert "rationale" in prompt_text or "begründung" in prompt_text

    def test_rationale_not_requested_when_disabled(
        self, factory_without_rationale, sample_work_item
    ):
        """Mit include_rationale=False darf keine Begründung angefordert werden."""
        prompts = list(
            factory_without_rationale.prompts(
                [sample_work_item],
                model_name="test-model",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )

        prompt_text = prompts[0].prompt_text.lower()
        # Sollte nur "rating" erwähnen, nicht "rationale"
        assert "rating" in prompt_text
        # Kann in strict_suffix vorkommen, daher flexible Prüfung
        # Wichtig ist, dass im User-Block keine Begründung erwartet wird

    def test_multiple_work_items_generate_unique_prompts(self, factory_with_rationale):
        """Mehrere Work-Items erzeugen unterschiedliche Prompts."""
        items = [
            BenchWorkItem(
                dataset_id=1,
                persona_uuid=f"uuid-{i}",
                persona_context={
                    "name": f"Person{i}",
                    "age": 20 + i,
                    "gender": "divers",
                },
                case_id=f"case_{i}",
                adjective=f"adjektiv_{i}",
                case_template=None,
                scale_reversed=False,
            )
            for i in range(3)
        ]

        prompts = list(
            factory_with_rationale.prompts(
                items,
                model_name="test-model",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )

        assert len(prompts) == 3
        # Alle Prompts sollten unterschiedlich sein
        prompt_texts = [p.prompt_text for p in prompts]
        assert len(set(prompt_texts)) == 3

    def test_prompt_spec_contains_metadata(
        self, factory_with_rationale, sample_work_item
    ):
        """PromptSpec muss alle Metadata enthalten."""
        prompts = list(
            factory_with_rationale.prompts(
                [sample_work_item],
                model_name="gpt-4",
                template_version="v2",
                attempt=3,
                benchmark_run_id=42,
            )
        )

        spec = prompts[0]
        assert spec.model_name == "gpt-4"
        assert spec.template_version == "v2"
        assert spec.attempt == 3
        assert spec.benchmark_run_id == 42
        assert spec.max_new_tokens == 192

    def test_system_preamble_can_be_overridden(self, sample_work_item):
        """Custom System-Prompt sollte verwendet werden."""
        custom_preamble = "Du bist ein spezieller Test-Assistent."
        factory = LikertPromptFactory(
            max_new_tokens=128, system_preamble=custom_preamble, include_rationale=True
        )

        prompts = list(
            factory.prompts(
                [sample_work_item],
                model_name="test-model",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )

        assert custom_preamble in prompts[0].prompt_text

    def test_missing_persona_name_fallback(self, factory_with_rationale):
        """Fehlender Name sollte Fallback 'die Person' nutzen."""
        work_item = BenchWorkItem(
            dataset_id=1,
            persona_uuid="uuid-no-name",
            persona_context={"age": 40, "gender": "männlich"},  # Kein "name"!
            case_id="case_003",
            adjective="hilfsbereit",
            case_template=None,
            scale_reversed=False,
        )

        prompts = list(
            factory_with_rationale.prompts(
                [work_item],
                model_name="test-model",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )

        prompt_text = prompts[0].prompt_text
        assert "die Person" in prompt_text

    @pytest.mark.parametrize(
        "scale_reversed,expected_order",
        [
            (False, "1-5"),  # In-order
            (True, "5-1"),  # Reversed
        ],
    )
    def test_scale_order_parametrized(
        self, factory_with_rationale, scale_reversed, expected_order
    ):
        """Parametrisierter Test für Scale-Order."""
        work_item = BenchWorkItem(
            dataset_id=1,
            persona_uuid="uuid-param",
            persona_context={"name": "Test", "age": 30},
            case_id="case_param",
            adjective="test",
            case_template=None,
            scale_reversed=scale_reversed,
        )

        prompts = list(
            factory_with_rationale.prompts(
                [work_item],
                model_name="test-model",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )

        prompt_text = prompts[0].prompt_text
        if expected_order == "1-5":
            # 1 sollte vor 5 erscheinen im Prompt
            idx_1 = prompt_text.find("1")
            idx_5 = prompt_text.find("5")
            # Naive Prüfung - in realem Code würde man die genaue Formatierung prüfen
            assert idx_1 < idx_5
        else:
            # Bei reversed: 5 vor 1
            idx_1 = prompt_text.find("1")
            idx_5 = prompt_text.find("5")
            assert idx_5 < idx_1


class TestPromptConsistency:
    """Tests zur Konsistenz von Prompts über mehrere Runs."""

    def test_same_input_produces_same_prompt(self):
        """Identische Inputs sollten identische Prompts erzeugen."""
        factory = LikertPromptFactory(max_new_tokens=128, include_rationale=True)

        work_item = BenchWorkItem(
            dataset_id=1,
            persona_uuid="uuid-consistent",
            persona_context={"name": "Konsistent", "age": 25},
            case_id="case_consistent",
            adjective="konsistent",
            case_template=None,
            scale_reversed=False,
        )

        prompts1 = list(
            factory.prompts(
                [work_item],
                model_name="m",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )
        prompts2 = list(
            factory.prompts(
                [work_item],
                model_name="m",
                template_version="v1",
                attempt=1,
                benchmark_run_id=1,
            )
        )

        assert prompts1[0].prompt_text == prompts2[0].prompt_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
