"""Detailed test to understand retry mechanism."""

import os
import sys
import tempfile
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
SRC_ROOT = REPO_ROOT / "apps" / "backend" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def test_db():
    """Setup test database."""
    from backend.infrastructure.storage.db import (
        create_tables,
        drop_tables,
        init_database,
    )
    from backend.infrastructure.storage.models import Country, Trait

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_url = f"sqlite:///{db_file.name}"

    init_database(db_url)
    drop_tables()
    create_tables()

    Country.create(
        id=1, country_en="Germany", country_de="Deutschland", country_code_alpha2="DE"
    )

    Trait.create(
        id="trait_test",
        adjective="testbar",
        case_template="Wie testbar wirkt die Person?",
        category="test",
    )

    yield db_url

    try:
        os.unlink(db_file.name)
    except Exception:
        pass


def test_retry_mechanism_with_max_attempts_3(test_db):
    """Test genau wie oft der LLM bei max_attempts=3 aufgerufen wird."""
    from backend.domain.benchmarking.adapters.postprocess.postprocessor_likert import (
        LikertPostProcessor,
    )
    from backend.domain.benchmarking.adapters.prompting.likert_factory import (
        LikertPromptFactory,
    )
    from backend.domain.benchmarking.benchmark import run_benchmark_pipeline
    from backend.domain.benchmarking.ports_bench import LLMResult
    from backend.infrastructure.benchmark.persister_bench import BenchPersisterPeewee
    from backend.infrastructure.benchmark.repository.persona_repository import (
        FullPersonaRepositoryByDataset,
    )
    from backend.infrastructure.benchmark.repository.trait import TraitRepository
    from backend.infrastructure.storage.models import (
        BenchmarkRun,
        Dataset,
        DatasetPersona,
        FailLog,
        Model,
        Persona,
    )

    class CountingLLM:
        """LLM that counts attempts and always fails."""

        def __init__(self):
            self.attempts_per_item = {}

        def run_stream(self, specs):
            spec_list = list(specs)
            for spec in spec_list:
                key = (spec.work.persona_uuid, spec.work.case_id)

                if key not in self.attempts_per_item:
                    self.attempts_per_item[key] = []

                self.attempts_per_item[key].append(spec.attempt)

                print(
                    f"[LLM] Called with attempt={spec.attempt} for {key[0][:8]}/{key[1]}"
                )

                # Always return invalid JSON to trigger retry
                yield LLMResult(spec=spec, raw_text="ALWAYS FAIL", gen_time_ms=100)

    # Create dataset
    test_uuid = str(uuid.uuid4())
    dataset = Dataset.create(name="test-retry-count", kind="test", config_json="{}")

    persona = Persona.create(
        uuid=test_uuid,
        age=30,
        gender="male",
        education="primary",
        occupation="worker",
        marriage_status="single",
        migration_status="native",
        origin_id=1,
        religion="christian",
        sexuality="heterosexual",
    )
    DatasetPersona.create(dataset_id=dataset.id, persona_id=persona.uuid)

    model = Model.get_or_create(name="counting-model")[0]
    bench_run = BenchmarkRun.create(
        dataset_id=dataset.id,
        model_id=model.id,
        batch_size=1,
        max_attempts=3,  # CRITICAL: 3 attempts
        include_rationale=False,
    )

    llm = CountingLLM()

    # Run pipeline
    run_benchmark_pipeline(
        dataset_id=dataset.id,
        trait_repo=TraitRepository(),
        persona_repo=FullPersonaRepositoryByDataset(
            dataset_id=dataset.id,
            model_name="counting-model",
            attr_generation_run_id=None,
        ),
        prompt_factory=LikertPromptFactory(include_rationale=False),
        llm=llm,
        post=LikertPostProcessor(include_rationale=False),
        persist=BenchPersisterPeewee(),
        model_name="counting-model",
        template_version="v1",
        benchmark_run_id=bench_run.id,
        max_attempts=3,
        persona_count_override=1,
        scale_mode="in",
        dual_fraction=None,
    )

    # Analyze attempts
    print("\n=== Retry Mechanism Analysis ===")
    for key, attempts in llm.attempts_per_item.items():
        print(f"Item {key[0][:8]}/{key[1]}: attempts={attempts}")
        print(f"  Total calls: {len(attempts)}")
        print(f"  Attempt numbers: {attempts}")

    # Check FailLog entries
    failures = list(FailLog.select().where(FailLog.benchmark_run_id == bench_run.id))

    print(f"\nFailLog entries: {len(failures)}")
    for failure in failures:
        print(f"  - attempt={failure.attempt}, error_kind={failure.error_kind}")

    # ASSERTIONS
    # With max_attempts=3, we expect the LLM to be called 3 times per item
    for key, attempts in llm.attempts_per_item.items():
        assert len(attempts) == 3, (
            f"Expected 3 LLM calls with max_attempts=3, got {len(attempts)}. "
            f"Attempts were: {attempts}"
        )
        assert attempts == [1, 2, 3], f"Expected attempts [1, 2, 3], got {attempts}"

    # Should have 1 FailLog entry with attempt=3 (last attempt) for max_attempts_exceeded
    # Plus possibly 2 more for the earlier failed attempts
    assert len(failures) >= 1, "Expected at least 1 FailLog entry"

    # Find the max_attempts_exceeded entry
    max_exceeded = [f for f in failures if f.error_kind == "max_attempts_exceeded"]
    assert len(max_exceeded) >= 1, "Expected at least 1 'max_attempts_exceeded' entry"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
