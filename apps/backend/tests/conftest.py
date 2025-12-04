"""Shared pytest fixtures für alle Tests."""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root():
    """Root-Verzeichnis des Repositories."""
    return Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def setup_pythonpath(repo_root):
    """Stelle sicher dass backend-Package importierbar ist."""
    import sys

    src_root = repo_root / "apps" / "backend" / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))


@pytest.fixture(scope="function")
def test_db(setup_pythonpath):
    """Temporäre SQLite-DB pro Test."""
    from backend.infrastructure.storage.db import (
        create_tables,
        drop_tables,
        init_database,
    )

    # Create temp file
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_url = f"sqlite:///{db_file.name}"

    # Initialize
    init_database(db_url)
    drop_tables()
    create_tables()

    # Prefill lookup tables
    from backend.infrastructure.storage.prefill_db import DBFiller

    DBFiller().fill_all()

    yield db_url

    # Cleanup
    try:
        os.unlink(db_file.name)
    except Exception:
        pass


@pytest.fixture
def fake_llm_client():
    """Fake LLM-Client für Unit-Tests."""
    from backend.infrastructure.benchmark.adapters.llm.fake_clients import (
        LlmClientFakeBench,
    )

    return LlmClientFakeBench(batch_size=2)


@pytest.fixture
def sample_persona_context():
    """Standard-Persona-Context für Tests."""
    return {
        "name": "Max Mustermann",
        "age": 35,
        "gender": "männlich",
        "education": "Bachelor",
        "occupation": "Ingenieur",
        "marriage_status": "verheiratet",
        "origin_country": "Deutschland",
        "religion": "keine Angabe",
        "sexuality": "heterosexuell",
    }


@pytest.fixture
def sample_work_item(sample_persona_context):
    """Standard BenchWorkItem für Tests."""
    from backend.domain.benchmarking.ports_bench import BenchWorkItem

    return BenchWorkItem(
        dataset_id=1,
        persona_uuid="test-uuid-123",
        persona_context=sample_persona_context,
        case_id="case_001",
        adjective="freundlich",
        case_template=None,
        scale_reversed=False,
    )


@pytest.fixture
def sample_prompt_spec(sample_work_item):
    """Standard BenchPromptSpec für Tests."""
    from backend.domain.benchmarking.ports_bench import BenchPromptSpec

    return BenchPromptSpec(
        work=sample_work_item,
        prompt_text="Test prompt",
        max_new_tokens=128,
        attempt=1,
        model_name="test-model",
        template_version="v1",
        benchmark_run_id=1,
    )


@pytest.fixture
def likert_processor_with_rationale():
    """LikertPostProcessor mit Rationale."""
    from backend.domain.benchmarking.adapters.postprocess.postprocessor_likert import (
        LikertPostProcessor,
    )

    return LikertPostProcessor(include_rationale=True)


@pytest.fixture
def likert_processor_without_rationale():
    """LikertPostProcessor ohne Rationale."""
    from backend.domain.benchmarking.adapters.postprocess.postprocessor_likert import (
        LikertPostProcessor,
    )

    return LikertPostProcessor(include_rationale=False)


@pytest.fixture
def prompt_factory_with_rationale():
    """LikertPromptFactory mit Rationale."""
    from backend.domain.benchmarking.adapters.prompting.likert_factory import (
        LikertPromptFactory,
    )

    return LikertPromptFactory(max_new_tokens=192, include_rationale=True)


@pytest.fixture
def prompt_factory_without_rationale():
    """LikertPromptFactory ohne Rationale."""
    from backend.domain.benchmarking.adapters.prompting.likert_factory import (
        LikertPromptFactory,
    )

    return LikertPromptFactory(max_new_tokens=128, include_rationale=False)


@pytest.fixture
def minimal_dataset(test_db, setup_pythonpath):
    """Minimales Dataset mit 2 Personas und 3 Traits."""
    from backend.infrastructure.storage.db import init_database
    from backend.infrastructure.storage.models import (
        Dataset,
        DatasetPersona,
        Model,
        Persona,
    )

    init_database(test_db)

    # Create dataset
    dataset = Dataset.create(name="test-minimal-dataset", kind="test", config_json="{}")

    # Create 2 personas
    personas = []
    for i in range(2):
        persona = Persona.create(
            persona_uuid=f"test-persona-{i}",
            age=25 + i * 5,
            gender_id=1 + (i % 2),
            education_id=1,
            occupation_id=1,
            marriage_status_id=1,
            migration_status_id=1,
            origin_country_id=1,
            religion_id=1,
            sexuality_id=1,
            seed=10000 + i,
        )
        DatasetPersona.create(dataset=dataset, persona=persona)
        personas.append(persona)

    # Create model
    model = Model.get_or_create(name="test-model")[0]

    return {"dataset": dataset, "personas": personas, "model": model}


@pytest.fixture
def trait_repository(setup_pythonpath):
    """TraitRepository für Tests."""
    from backend.infrastructure.benchmark.repository.trait import TraitRepository

    return TraitRepository()


@pytest.fixture
def mock_vllm_response_valid():
    """Standard vLLM-Response (gültiges JSON)."""
    return {
        "id": "cmpl-123",
        "object": "text_completion",
        "created": 1234567890,
        "model": "test-model",
        "choices": [
            {
                "text": '{"rating": 4, "rationale": "Person wirkt freundlich."}',
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }


@pytest.fixture
def mock_vllm_response_invalid():
    """Invalide vLLM-Response (broken JSON)."""
    return {
        "id": "cmpl-456",
        "object": "text_completion",
        "created": 1234567890,
        "model": "test-model",
        "choices": [
            {
                "text": '{"rating": 4, "rationale": "incomplete',
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop",
            }
        ],
    }


# Marker für langsame Tests
def pytest_configure(config):
    """Registriere custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: integration tests requiring DB")
    config.addinivalue_line("markers", "e2e: end-to-end tests")
    config.addinivalue_line("markers", "performance: performance benchmarks")
    config.addinivalue_line("markers", "requires_vllm: requires running vLLM server")


# Auto-Skip für Tests die vLLM benötigen
def pytest_runtest_setup(item):
    """Skip tests that require vLLM if not available."""
    if "requires_vllm" in item.keywords:
        vllm_available = os.getenv("VLLM_BASE_URL") is not None
        if not vllm_available:
            pytest.skip("Test requires vLLM server (set VLLM_BASE_URL)")
