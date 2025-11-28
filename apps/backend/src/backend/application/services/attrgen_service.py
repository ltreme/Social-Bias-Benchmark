"""Service for attribute generation orchestration."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from backend.domain.benchmarking.adapters.postprocess.postprocessor_attr import (
    AttributePostProcessor,
)
from backend.domain.benchmarking.adapters.prompting import AttributePromptFactory
from backend.domain.benchmarking.attr_gen import run_attr_gen_pipeline
from backend.domain.benchmarking.attr_gen_validator import (
    AttrGenValidationError,
    AttrGenValidator,
)
from backend.infrastructure.benchmark.attrgen_progress_tracker import (
    InMemoryProgressTracker,
    ProgressInfo,
)
from backend.infrastructure.benchmark.persister_sqlite import PersisterPeewee
from backend.infrastructure.benchmark.repository.attrgen_repository import (
    AttrGenRepository,
)
from backend.infrastructure.benchmark.repository.persona_repository import (
    PersonaRepositoryByDataset,
)
from backend.infrastructure.common.background_jobs import (
    PeriodicPoller,
    ThreadedJobRunner,
)
from backend.infrastructure.llm import LlmClientFake, LlmClientVLLM
from backend.infrastructure.llm.vllm_connection import select_vllm_base_for_model
from backend.infrastructure.storage.models import AttrGenerationRun, Model

_LOG = logging.getLogger(__name__)


class AttrGenService:
    """Service for managing attribute generation runs."""

    def __init__(
        self,
        repository: AttrGenRepository | None = None,
        progress_tracker: InMemoryProgressTracker | None = None,
        job_runner: ThreadedJobRunner | None = None,
        validator: AttrGenValidator | None = None,
    ):
        """Initialize the service.

        Args:
            repository: Repository for data access (default: new instance)
            progress_tracker: Progress tracker (default: new instance)
            job_runner: Background job runner (default: new instance)
            validator: Validator for business rules (default: new instance)
        """
        self.repository = repository or AttrGenRepository()
        self.progress_tracker = progress_tracker or InMemoryProgressTracker()
        self.job_runner = job_runner or ThreadedJobRunner()
        self.validator = validator or AttrGenValidator()

    def start_attr_generation(self, params: Dict[str, Any]) -> Dict[str, int]:
        """Start an attribute generation run.

        Args:
            params: Dictionary with:
                - dataset_id (int): Dataset to process
                - model_name (str): Model to use
                - batch_size (int, optional): Batch size (default: 2)
                - max_new_tokens (int, optional): Max tokens (default: 192)
                - max_attempts (int, optional): Max retry attempts (default: 3)
                - system_prompt (str, optional): System prompt
                - llm (str, optional): LLM backend ('hf'|'vllm'|'fake', default: 'hf')
                - vllm_base_url (str, optional): vLLM server URL
                - resume_run_id (int, optional): Resume existing run
                - skip_completed (bool, optional): Skip already completed personas

        Returns:
            Dictionary with run_id

        Raises:
            AttrGenValidationError: If validation fails
        """
        dataset_id = int(params["dataset_id"])
        model_name = str(params["model_name"])
        batch_size = int(params.get("batch_size", 2))
        max_new_tokens = int(params.get("max_new_tokens", 192))
        max_attempts = int(params.get("max_attempts", 3))
        system_prompt = params.get("system_prompt")
        llm_backend = params.get("llm", "hf")
        vllm_base_url = params.get("vllm_base_url")
        resume_run_id = params.get("resume_run_id")
        skip_completed = bool(params.get("skip_completed", bool(resume_run_id)))

        # Handle resume or create new run
        if resume_run_id is not None:
            run = self.repository.get_run_by_id(int(resume_run_id))
            if not run:
                raise AttrGenValidationError("resume_run_id nicht gefunden")
            self.validator.validate_resume_run(run, dataset_id)
            # Update runtime parameters
            run.batch_size = batch_size
            run.max_new_tokens = max_new_tokens
            run.max_attempts = max_attempts
            run.system_prompt = system_prompt
            run.save()
        else:
            model_entry, _ = Model.get_or_create(name=model_name)
            run = AttrGenerationRun.create(
                dataset_id=dataset_id,
                model_id=model_entry.id,
                batch_size=batch_size,
                max_new_tokens=max_new_tokens,
                max_attempts=max_attempts,
                system_prompt=system_prompt,
            )

        run_id = int(run.id)

        # Initialize progress tracking
        self.progress_tracker.set_progress(
            run_id,
            ProgressInfo(
                status="queued",
                llm=llm_backend,
                vllm_base_url=vllm_base_url,
                skip_completed=skip_completed,
            ),
        )

        # Start pipeline in background
        self.job_runner.run_async(self._run_pipeline, run_id)

        # Start progress polling
        poller = PeriodicPoller(
            target=lambda: self._update_progress(run_id, dataset_id),
            condition=lambda: (
                self.progress_tracker.get_progress(run_id).status
                in {"queued", "running"}
                if self.progress_tracker.get_progress(run_id)
                else False
            ),
        )
        poller.run_async(self.job_runner)

        return {"run_id": run_id}

    def _update_progress(self, run_id: int, dataset_id: int) -> bool:
        """Update progress for a run by querying the database.

        Args:
            run_id: The run ID
            dataset_id: The dataset ID

        Returns:
            True to continue polling, False to stop
        """
        try:
            done = self.repository.count_completed_personas(run_id, dataset_id)
            total = self.repository.count_dataset_personas(dataset_id)
            self.progress_tracker.compute_and_update_progress(run_id, total, done)
            return True
        except Exception:
            return False

    def _run_pipeline(self, run_id: int) -> None:
        """Execute the attribute generation pipeline.

        Args:
            run_id: The run ID
        """
        try:
            run = self.repository.get_run_by_id(run_id)
            if not run:
                self.progress_tracker.update_progress(
                    run_id, status="failed", error="Run nicht gefunden"
                )
                return

            dataset_id = int(run.dataset_id.id) if run.dataset_id else None
            model_name = str(run.model_id.name)

            # Get progress metadata
            progress = self.progress_tracker.get_progress(run_id)
            llm_backend = progress.extra.get("llm", "hf") if progress else "hf"
            vllm_base_url = progress.extra.get("vllm_base_url") if progress else None
            skip_completed = (
                progress.extra.get("skip_completed", False) if progress else False
            )

            # Setup components
            persona_repo = PersonaRepositoryByDataset(dataset_id=dataset_id)
            prompt_factory = AttributePromptFactory(
                max_new_tokens=int(run.max_new_tokens or 160),
                system_preamble=run.system_prompt,
            )
            post_processor = AttributePostProcessor()
            persister = PersisterPeewee()
            batch_size = int(run.batch_size or 2)

            # Select LLM backend
            if llm_backend == "fake":
                llm = LlmClientFake(batch_size=batch_size)
            else:
                try:
                    selected_url = select_vllm_base_for_model(model_name, vllm_base_url)
                except Exception as e:
                    self.progress_tracker.update_progress(
                        run_id, status="failed", error=str(e)
                    )
                    return

                llm = LlmClientVLLM(
                    base_url=selected_url,
                    model=model_name,
                    api_key=None,
                    batch_size=batch_size,
                    max_new_tokens_cap=int(run.max_new_tokens or 192),
                )

            # Update status to running
            self.progress_tracker.update_progress(
                run_id, status="running", done=0, total=0, pct=0.0
            )

            _LOG.info(
                f"[AttrGen] Pipeline setup: run_id={run_id}, dataset_id={dataset_id}, "
                f"model={model_name}, skip_completed={skip_completed}, "
                f"batch_size={batch_size}"
            )

            # Filter to incomplete personas if needed
            if skip_completed and dataset_id is not None:
                allowed_uuids = self.repository.get_incomplete_persona_uuids(
                    run_id, dataset_id
                )
                _LOG.info(
                    f"[AttrGen] Filtering to {len(allowed_uuids)} incomplete personas "
                    f"(skip_completed=True)"
                )

                # Create filtering wrapper
                class FilteredPersonaRepo:
                    def __init__(self, base, allowed: set[str]):
                        self.base = base
                        self.allowed = allowed

                    def iter_personas(self, ds_id: int):
                        for persona in self.base.iter_personas(ds_id):
                            if str(persona.persona_uuid) in self.allowed:
                                yield persona

                persona_repo = FilteredPersonaRepo(persona_repo, allowed_uuids)

            # Run the pipeline
            run_attr_gen_pipeline(
                dataset_id=dataset_id,
                persona_repo=persona_repo,
                prompt_factory=prompt_factory,
                llm=llm,
                post=post_processor,
                persist=persister,
                model_name=model_name,
                max_attempts=int(run.max_attempts or 3),
                persist_buffer_size=256,
                total_personas_override=None,
                attr_generation_run_id=run_id,
            )

            # Final progress update
            self._update_progress(run_id, dataset_id)
            self.progress_tracker.update_progress(run_id, status="done")

        except Exception as e:
            self.progress_tracker.update_progress(run_id, status="failed", error=str(e))

    def get_run_status(self, run_id: int) -> Dict[str, Any]:
        """Get status of an attribute generation run.

        Args:
            run_id: The run ID

        Returns:
            Dictionary with status information
        """
        progress = self.progress_tracker.get_progress(run_id)

        if not progress:
            # Try to compute from database
            run = self.repository.get_run_by_id(run_id)
            if run:
                dataset_id = int(run.dataset_id.id) if run.dataset_id else None
                if dataset_id is not None:
                    self._update_progress(run_id, dataset_id)
                    progress = self.progress_tracker.get_progress(run_id)

        if not progress:
            return {"status": "unknown"}

        return progress.to_dict()

    def get_latest_run(self, dataset_id: int) -> Dict[str, Any]:
        """Get the latest attribute generation run for a dataset.

        Args:
            dataset_id: The dataset ID

        Returns:
            Dictionary with run information or {"found": False}
        """
        run = self.repository.get_latest_run_for_dataset(dataset_id)
        if not run:
            return {"found": False}

        run_id = int(run.id)
        self._update_progress(run_id, dataset_id)
        progress = self.progress_tracker.get_progress(run_id)

        status = progress.status if progress else "unknown"

        return {
            "found": True,
            "run_id": run_id,
            "status": status,
            "done": progress.done if progress else 0,
            "total": progress.total if progress else 0,
            "pct": progress.pct if progress else 0.0,
            "error": progress.error if progress else None,
        }

    def list_runs(self, dataset_id: int, limit: int = 25) -> List[Dict[str, Any]]:
        """List attribute generation runs for a dataset.

        Args:
            dataset_id: The dataset ID
            limit: Maximum number of runs to return

        Returns:
            List of run dictionaries
        """
        runs = self.repository.list_runs_for_dataset(dataset_id, limit)
        result = []

        for run in runs:
            run_id = int(run.id)
            self._update_progress(run_id, dataset_id)
            progress = self.progress_tracker.get_progress(run_id)

            total = progress.total if progress else 0
            done = progress.done if progress else 0
            status = progress.status if progress else "unknown"

            # Infer status if not set
            if not status or status == "unknown":
                status = "done" if total and done >= total else "unknown"

            result.append(
                {
                    "id": run_id,
                    "created_at": str(run.created_at),
                    "batch_size": int(run.batch_size or 0),
                    "max_new_tokens": int(run.max_new_tokens or 0),
                    "max_attempts": int(run.max_attempts or 0),
                    "system_prompt": run.system_prompt,
                    "model_name": run.model_id.name if run.model_id else None,
                    "status": status,
                    "done": done,
                    "total": total,
                    "pct": progress.pct if progress else 0.0,
                    "error": progress.error if progress else None,
                }
            )

        return result

    def delete_run(self, run_id: int) -> Dict[str, int]:
        """Delete an attribute generation run.

        Args:
            run_id: The run ID to delete

        Returns:
            Dictionary with number of deleted attributes

        Raises:
            AttrGenValidationError: If deletion is not safe
        """
        run = self.repository.get_run_by_id(run_id)
        if not run:
            raise AttrGenValidationError("AttrGen-Run nicht gefunden")

        # Get current status
        progress = self.progress_tracker.get_progress(run_id)
        status = progress.status if progress else None

        # Check for dependent benchmarks
        has_dependent = self.repository.has_dependent_benchmark_runs(run)

        # Validate deletion
        self.validator.validate_run_deletion(run, status, has_dependent)

        # Delete attributes and run
        deleted_attrs = self.repository.delete_run_attributes(run_id)
        run.delete_instance()

        # Cleanup progress tracking
        self.progress_tracker.delete_progress(run_id)

        return {"deleted_attributes": deleted_attrs}
