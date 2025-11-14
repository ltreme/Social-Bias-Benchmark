import os
import sys
import unittest
from pathlib import Path

# Ensure src packages are importable when running via unittest discover
REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "apps" / "backend" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


class TestEndToEndPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Soften noisy 3rd-party deprecations (Python 3.12 + SWIG)
        import warnings

        warnings.filterwarnings(
            "ignore",
            message=r"builtin type .*has no __module__ attribute",
            category=DeprecationWarning,
        )
        # Allow opting-in to the slow integration test
        flag = os.getenv("INTEGRATION_FULL", "0").lower()
        cls.enabled = flag in ("1", "true", "yes")
        if not cls.enabled:
            return

        # Init + create tables
        from backend.infrastructure.storage.db import (
            create_tables,
            drop_tables,
            init_database,
        )

        init_database(os.getenv("DB_URL"))
        drop_tables()
        create_tables()

        # Prefill lookup tables (idempotent)
        from backend.infrastructure.storage.prefill_db import DBFiller

        DBFiller().fill_all()

    def setUp(self):
        if not getattr(self, "enabled", False):
            self.skipTest("Set INTEGRATION_FULL=1 to run the end-to-end test.")

    def test_full_pipeline_with_real_db(self):
        # Choose LLM backend from env; default to vllm for integration testing
        llm_kind = os.getenv("INTEGRATION_LLM", "vllm").lower()
        if llm_kind not in ("fake", "vllm"):
            self.skipTest(
                f"Unsupported INTEGRATION_LLM={llm_kind}, use 'fake' or 'vllm'"
            )

        # 1) Generate personas and obtain dataset_id
        from backend.domain.persona.persona_generator.main import (
            persist_run_and_personas,
            sample_personas,
        )
        from backend.infrastructure.storage.db import create_tables, init_database

        init_database(os.getenv("DB_URL"))
        create_tables()

        n = int(os.getenv("N_PERSONAS", "2"))
        params = dict(
            age_min=18,
            age_max=80,
            age_temperature=0.0,
            education_temperature=0.0,
            education_exclude=None,
            gender_temperature=0.0,
            gender_exclude=None,
            occupation_exclude=None,
            marriage_status_temperature=0.0,
            marriage_status_exclude=None,
            migration_status_temperature=0.0,
            migration_status_exclude=None,
            origin_temperature=0.0,
            origin_exclude=None,
            religion_temperature=0.0,
            religion_exclude=None,
            sexuality_temperature=0.0,
            sexuality_exclude=None,
        )
        sampled = sample_personas(n=n, **params)
        dataset_id = persist_run_and_personas(n=n, params=params, sampled=sampled)
        # keep for teardown cleanup
        self._dataset_id = dataset_id

        # 2) Preprocessing stage
        from backend.application.cli.run_attr_generation import main as attr_gen_main

        pre_args = [f"--dataset-id={dataset_id}", "--llm=fake"]
        if llm_kind == "vllm":
            pre_args = [
                f"--dataset-id={dataset_id}",
                "--llm=vllm",
                "--vllm-model=Qwen/Qwen2.5-1.5B-Instruct",
            ]
        rc = attr_gen_main(pre_args)
        self.assertEqual(rc, 0, "Attribute generation pipeline failed")

        # 3) Core benchmark stage
        from backend.application.cli.run_core_benchmark import main as bench_main

        # Enable benchmark debug to see OK/Retry/Fail counts in logs
        os.environ.setdefault("BENCH_DEBUG", "1")
        max_new = int(os.getenv("MAX_NEW_TOKENS", "160"))
        bench_args = [
            f"--dataset-id={dataset_id}",
            "--llm=fake",
            f"--max-new-tokens={max_new}",
        ]
        if llm_kind == "vllm":
            bench_args = [
                f"--dataset-id={dataset_id}",
                "--llm=vllm",
                "--vllm-model=Qwen/Qwen2.5-1.5B-Instruct",
                f"--max-new-tokens={max_new}",
            ]
        rc = bench_main(bench_args)
        self.assertEqual(rc, 0, "Benchmark pipeline failed")

        # 4) Verify persisted rows for this dataset_id exist
        from backend.infrastructure.storage.models import (
            AdditionalPersonaAttributes,
            BenchmarkResult,
            DatasetPersona,
            FailLog,
            Persona,
        )

        persona_count = (
            DatasetPersona.select()
            .where(DatasetPersona.dataset_id == dataset_id)
            .count()
        )
        attr_count = (
            AdditionalPersonaAttributes.select()
            .join(Persona)
            .join(DatasetPersona, on=(DatasetPersona.persona_id == Persona.uuid))
            .where(DatasetPersona.dataset_id == dataset_id)
            .count()
        )
        bench_count = (
            BenchmarkResult.select()
            .join(Persona)
            .join(DatasetPersona, on=(DatasetPersona.persona_id == Persona.uuid))
            .where(DatasetPersona.dataset_id == dataset_id)
            .count()
        )
        fail_count = (
            FailLog.select()
            .join(Persona)
            .join(DatasetPersona, on=(DatasetPersona.persona_id == Persona.uuid))
            .where(DatasetPersona.dataset_id == dataset_id)
            .count()
        )
        # Get total number of cases from database
        from backend.infrastructure.storage.models import Case

        question_count = Case.select().count()

        # Expect exactly 3 attributes per persona
        self.assertGreaterEqual(persona_count, n)
        self.assertEqual(
            attr_count, persona_count * 3, "Expected exactly 3 attributes per persona"
        )

        # Expected benchmark rows = personas * number_of_questions
        expected = persona_count * question_count
        if bench_count != expected:
            # Provide helpful context before failing
            msg = (
                f"Unexpected number of benchmark results: got={bench_count} expected={expected} "
                f"personas={persona_count} questions={question_count} fails={fail_count}"
            )
            self.fail(msg)

    def tearDown(self):
        # Remove generated data for the created dataset_id to keep the DB clean
        if getattr(self, "enabled", False) and hasattr(self, "_dataset_id"):
            try:
                from backend.infrastructure.storage.db import init_database
                from backend.infrastructure.storage.models import Dataset

                init_database(os.getenv("DB_URL"))
                # CASCADE: removes DatasetPersona, Personas, AdditionalPersonaAttributes, BenchmarkResult, FailLog
                Dataset.delete().where(Dataset.id == self._dataset_id).execute()
            except Exception:
                # Don't fail the test run because of cleanup issues
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
