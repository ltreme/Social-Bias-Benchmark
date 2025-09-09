import os
import sys
import unittest


# Ensure src packages are importable when running via unittest discover
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PATHS = [
    os.path.join(REPO_ROOT, "apps/persona_generator/src"),
    os.path.join(REPO_ROOT, "apps/benchmark/src"),
    os.path.join(REPO_ROOT, "apps/shared/src"),
]
for p in PATHS:
    if p not in sys.path:
        sys.path.insert(0, p)


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
        # Lower HF logging verbosity to hide "invalid generation flags" info logs
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        # Allow opting-in to the slow integration test
        flag = os.getenv("INTEGRATION_FULL", "0").lower()
        cls.enabled = flag in ("1", "true", "yes")
        if not cls.enabled:
            return

        # Init + create tables
        from shared.storage.db import init_database, create_tables
        init_database(os.getenv("DB_URL"))
        create_tables()

        # Prefill lookup tables (idempotent)
        from shared.storage.prefill_db import DBFiller
        DBFiller().fill_all()

    def setUp(self):
        if not getattr(self, "enabled", False):
            self.skipTest("Set INTEGRATION_FULL=1 to run the end-to-end test.")

    def test_full_pipeline_with_real_db(self):
        # Choose LLM backend from env; default to fake to keep it fast by default
        llm_kind = os.getenv("INTEGRATION_LLM", "fake").lower()
        hf_model = os.getenv("HF_MODEL")
        if llm_kind == "hf" and not hf_model:
            self.skipTest("HF model requested but HF_MODEL env var not set.")

        # 1) Generate personas and obtain gen_id
        from shared.storage.db import init_database, create_tables
        from persona_generator.main import sample_personas, persist_run_and_personas

        init_database(os.getenv("DB_URL"))
        create_tables()

        n = int(os.getenv("N_PERSONAS", "2"))
        params = dict(
            age_min=18, age_max=80, age_temperature=0.0,
            education_temperature=0.0, education_exclude=None,
            gender_temperature=0.0, gender_exclude=None,
            occupation_exclude=None,
            marriage_status_temperature=0.0, marriage_status_exclude=None,
            migration_status_temperature=0.0, migration_status_exclude=None,
            origin_temperature=0.0, origin_exclude=None,
            religion_temperature=0.0, religion_exclude=None,
            sexuality_temperature=0.0, sexuality_exclude=None,
        )
        sampled = sample_personas(n=n, **params)
        gen_id = persist_run_and_personas(n=n, params=params, sampled=sampled)
        # keep for teardown cleanup
        self._gen_id = gen_id

        # 2) Preprocessing stage
        from benchmark.cli.run_preprocessing import main as preprocess_main
        pre_args = [f"--gen-id={gen_id}", "--persist=peewee", "--llm=fake"]
        if llm_kind == "hf":
            pre_args = [f"--gen-id={gen_id}", "--persist=peewee", "--llm=hf", f"--hf-model={hf_model}"]
        rc = preprocess_main(pre_args)
        self.assertEqual(rc, 0, "Preprocessing pipeline failed")

        # 3) Primary benchmark stage
        from benchmark.cli.run_primary_benchmark import main as bench_main
        # Use a small questions file for faster runs
        small_q_path = os.path.join(REPO_ROOT, "out", "questions", "smoke-uuid.csv")
        # Enable benchmark debug to see OK/Retry/Fail counts in logs
        os.environ.setdefault("BENCH_DEBUG", "1")
        max_new = int(os.getenv("MAX_NEW_TOKENS", "160"))
        bench_args = [
            f"--gen-id={gen_id}",
            "--persist=peewee",
            "--llm=fake",
            f"--max-new-tokens={max_new}",
            f"--question-file={small_q_path}",
        ]
        if llm_kind == "hf":
            bench_args = [
                f"--gen-id={gen_id}",
                "--persist=peewee",
                "--llm=hf",
                f"--hf-model={hf_model}",
                f"--max-new-tokens={max_new}",
                f"--question-file={small_q_path}",
            ]
        rc = bench_main(bench_args)
        self.assertEqual(rc, 0, "Benchmark pipeline failed")

        # 4) Verify persisted rows for this gen_id exist
        from shared.storage.models import Persona, AdditionalPersonaAttributes, BenchmarkResult, FailLog
        persona_count = Persona.select().where(Persona.gen_id == gen_id).count()
        attr_count = (
            AdditionalPersonaAttributes
            .select()
            .join(Persona)
            .where(Persona.gen_id == gen_id)
            .count()
        )
        bench_count = (
            BenchmarkResult
            .select()
            .join(Persona)
            .where(Persona.gen_id == gen_id)
            .count()
        )
        fail_count = (
            FailLog
            .select()
            .join(Persona)
            .where(Persona.gen_id == gen_id)
            .count()
        )

        # Expect exactly 3 attributes per persona
        self.assertGreaterEqual(persona_count, n)
        self.assertEqual(attr_count, persona_count * 3, "Expected exactly 3 attributes per persona")

        # Expected benchmark rows = personas * number_of_questions (from our small file)
        # Count lines minus header
        with open(small_q_path, "r", encoding="utf-8") as f:
            num_questions = sum(1 for _ in f) - 1
        expected = persona_count * num_questions
        if bench_count != expected:
            # Provide helpful context before failing
            msg = (
                f"Unexpected number of benchmark results: got={bench_count} expected={expected} "
                f"personas={persona_count} questions={num_questions} fails={fail_count}"
            )
            self.fail(msg)

    def tearDown(self):
        # Remove generated data for the created gen_id to keep the DB clean
        if getattr(self, "enabled", False) and hasattr(self, "_gen_id"):
            try:
                from shared.storage.db import init_database
                from shared.storage.models import PersonaGeneratorRun
                init_database(os.getenv("DB_URL"))
                # CASCADE: removes Personas, AdditionalPersonaAttributes, BenchmarkResult, FailLog
                PersonaGeneratorRun.delete().where(
                    PersonaGeneratorRun.gen_id == self._gen_id
                ).execute()
            except Exception:
                # Don't fail the test run because of cleanup issues
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
