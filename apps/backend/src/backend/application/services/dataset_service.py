"""Service for dataset management and orchestration."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, List, Optional

from backend.domain.persona.dataset_validator import (
    DatasetValidationError,
    DatasetValidator,
)
from backend.domain.persona.datasets.builder import (
    build_balanced_dataset_from_pool,
    build_counterfactuals_from_dataset,
    build_random_subset_from_pool,
)
from backend.domain.persona.persona_generator.main import (
    persist_run_and_personas,
    sample_personas,
)
from backend.infrastructure.benchmark.dataset_progress_tracker import (
    DatasetProgressTracker,
)
from backend.infrastructure.benchmark.repository.dataset_repository import (
    DatasetRepository,
)
from backend.infrastructure.benchmark.repository.persona_repository_extended import (
    PersonaFilter,
    PersonaRepositoryExtended,
)
from backend.infrastructure.common.background_jobs import ThreadedJobRunner
from backend.infrastructure.export.csv_exporter import PersonaCSVExporter
from backend.infrastructure.storage.models import Dataset


class DatasetOut:
    """Output model for dataset information."""

    def __init__(
        self,
        id: int,
        name: str,
        kind: str,
        size: int,
        created_at: str | None = None,
        seed: int | None = None,
        config_json: Dict[str, Any] | None = None,
        additional_attributes_n: int = 0,
        name_n: int = 0,
        appearances_n: int = 0,
        biographies_n: int = 0,
        enriched_percentage: float = 0.0,
    ):
        """Initialize dataset output."""
        self.id = id
        self.name = name
        self.kind = kind
        self.size = size
        self.created_at = created_at
        self.seed = seed
        self.config_json = config_json
        self.additional_attributes_n = additional_attributes_n
        self.name_n = name_n
        self.appearances_n = appearances_n
        self.biographies_n = biographies_n
        self.enriched_percentage = enriched_percentage

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "size": self.size,
            "created_at": self.created_at,
            "seed": self.seed,
            "config_json": self.config_json,
            "additional_attributes_n": self.additional_attributes_n,
            "name_n": self.name_n,
            "appearances_n": self.appearances_n,
            "biographies_n": self.biographies_n,
            "enriched_percentage": self.enriched_percentage,
        }


class DatasetService:
    """Service for managing datasets and related operations."""

    def __init__(
        self,
        dataset_repo: DatasetRepository | None = None,
        persona_repo: PersonaRepositoryExtended | None = None,
        progress_tracker: DatasetProgressTracker | None = None,
        job_runner: ThreadedJobRunner | None = None,
        validator: DatasetValidator | None = None,
    ):
        """Initialize the service.

        Args:
            dataset_repo: Dataset repository (default: new instance)
            persona_repo: Extended persona repository (default: new instance)
            progress_tracker: Progress tracker (default: new instance)
            job_runner: Background job runner (default: new instance)
            validator: Validator for business rules (default: new instance)
        """
        self.dataset_repo = dataset_repo or DatasetRepository()
        self.persona_repo = persona_repo or PersonaRepositoryExtended()
        self.progress_tracker = progress_tracker or DatasetProgressTracker()
        self.job_runner = job_runner or ThreadedJobRunner()
        self.validator = validator or DatasetValidator()

    def list_datasets(self) -> List[DatasetOut]:
        """List all datasets.

        Returns:
            List of DatasetOut objects
        """
        datasets = self.dataset_repo.list_all_datasets()
        result = []

        for ds in datasets:
            size = self.dataset_repo.count_personas_in_dataset(ds.id)
            config = self.dataset_repo.parse_config_json(ds)
            result.append(
                DatasetOut(
                    id=ds.id,
                    name=ds.name,
                    kind=ds.kind,
                    size=size,
                    created_at=ds.created_at.isoformat() if ds.created_at else None,
                    seed=ds.seed,
                    config_json=config,
                )
            )

        return result

    def get_dataset(self, dataset_id: int) -> DatasetOut:
        """Get detailed dataset information.

        Args:
            dataset_id: The dataset ID

        Returns:
            DatasetOut object with enrichment stats
        """
        ds = self.dataset_repo.get_dataset_by_id(dataset_id)
        if not ds:
            return DatasetOut(id=0, name="Unknown", kind="unknown", size=0)

        size = self.dataset_repo.count_personas_in_dataset(dataset_id)
        enrichment = self.dataset_repo.get_enrichment_stats(dataset_id)

        name_n = enrichment.get("name_n", 0)
        appearances_n = enrichment.get("appearance_n", 0)
        biographies_n = enrichment.get("biography_n", 0)
        additional_attributes_n = name_n + appearances_n + biographies_n
        enriched_percentage = (
            (additional_attributes_n / (size * 3) * 100) if size > 0 else 0.0
        )

        config = self.dataset_repo.parse_config_json(ds)

        return DatasetOut(
            id=ds.id,
            name=ds.name,
            kind=ds.kind,
            size=size,
            created_at=ds.created_at.isoformat() if ds.created_at else None,
            seed=ds.seed,
            config_json=config,
            additional_attributes_n=additional_attributes_n,
            name_n=name_n,
            appearances_n=appearances_n,
            biographies_n=biographies_n,
            enriched_percentage=enriched_percentage,
        )

    def get_dataset_runs(self, dataset_id: int) -> List[Dict[str, Any]]:
        """Get benchmark runs for a dataset.

        Args:
            dataset_id: The dataset ID

        Returns:
            List of run dictionaries with progress info
        """
        from backend.infrastructure.benchmark import progress_tracker

        runs = self.dataset_repo.list_benchmark_runs_for_dataset(dataset_id)
        result = []

        for run in runs:
            info = progress_tracker.get_progress(int(run.id))
            if info and info.get("dataset_id") != dataset_id:
                info = None
            if info is None:
                info = {"status": "done", "dataset_id": dataset_id}
                progress_tracker.set_progress(int(run.id), info)

            try:
                progress_tracker.update_progress(int(run.id), dataset_id)
            except Exception:
                pass

            status = info.get("status", "unknown")
            done = info.get("done")
            total = info.get("total")
            pct = info.get("pct")

            result.append(
                {
                    "id": int(run.id),
                    "model_name": str(run.model_id.name),
                    "include_rationale": bool(run.include_rationale),
                    "created_at": str(run.created_at),
                    "status": status,
                    "done": done,
                    "total": total,
                    "pct": pct,
                }
            )

        return result

    def get_dataset_composition(self, dataset_id: int) -> Dict[str, Any]:
        """Get composition statistics for a dataset.

        Args:
            dataset_id: The dataset ID

        Returns:
            Dictionary with composition stats and age pyramid
        """
        stats = self.persona_repo.get_composition_stats(dataset_id)
        return {"ok": True, **stats}

    def list_personas(
        self,
        dataset_id: int,
        limit: int = 50,
        offset: int = 0,
        sort: str = "created_at",
        order: str = "desc",
        attrgen_run_id: int | None = None,
        filters: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """List personas in a dataset with filtering and pagination.

        Args:
            dataset_id: The dataset ID
            limit: Number of results per page
            offset: Offset for pagination
            sort: Field to sort by
            order: 'asc' or 'desc'
            attrgen_run_id: Optional attribute generation run ID
            filters: Optional filter dictionary

        Returns:
            Dictionary with personas and metadata
        """
        self.validator.validate_pagination_params(limit, offset)

        # Build filter criteria
        filter_criteria = None
        if filters:
            filter_criteria = PersonaFilter(
                gender=filters.get("gender"),
                religion=filters.get("religion"),
                sexuality=filters.get("sexuality"),
                education=filters.get("education"),
                marriage_status=filters.get("marriage_status"),
                migration_status=filters.get("migration_status"),
                origin_subregion=filters.get("origin_subregion"),
                min_age=filters.get("min_age"),
                max_age=filters.get("max_age"),
            )

        personas, total = self.persona_repo.list_personas_in_dataset(
            dataset_id, filter_criteria, sort, order, limit, offset
        )

        # Fetch additional attributes if needed
        add_map: Dict[str, Dict[str, Any]] = {}
        if personas and attrgen_run_id is not None:
            uuids = [str(p.uuid) for p in personas]
            add_map = self.persona_repo.get_additional_attributes_for_personas(
                uuids, attrgen_run_id
            )

        # Build response
        items = []
        for persona in personas:
            items.append(
                {
                    "uuid": str(persona.uuid),
                    "created_at": (
                        str(persona.created_at) if persona.created_at else None
                    ),
                    "age": int(persona.age) if persona.age is not None else None,
                    "gender": persona.gender,
                    "education": persona.education,
                    "occupation": persona.occupation,
                    "marriage_status": persona.marriage_status,
                    "migration_status": persona.migration_status,
                    "religion": persona.religion,
                    "sexuality": persona.sexuality,
                    "origin_country": getattr(persona.origin_id, "country_en", None),
                    "origin_region": getattr(persona.origin_id, "region", None),
                    "origin_subregion": getattr(persona.origin_id, "subregion", None),
                    "additional_attributes": add_map.get(str(persona.uuid), {}),
                }
            )

        return {"ok": True, "total": total, "items": items}

    def export_personas_csv(
        self, dataset_id: int, attrgen_run_id: int | None = None
    ) -> tuple[Iterable[bytes], str]:
        """Export personas as CSV stream.

        Args:
            dataset_id: The dataset ID
            attrgen_run_id: Optional attribute generation run ID

        Returns:
            Tuple of (streaming iterator, filename)
        """
        exporter = PersonaCSVExporter(dataset_id, attrgen_run_id)
        return exporter.stream_rows(), exporter.get_filename()

    def build_balanced_dataset(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build a balanced dataset from an existing dataset.

        Args:
            params: Dictionary with dataset_id, n, seed, name

        Returns:
            Dictionary with new dataset id and name
        """
        dataset_id = int(params["dataset_id"])
        n = int(params.get("n", 2000))
        seed = int(params.get("seed", 42))
        name = params.get("name")

        self.validator.validate_balanced_params(dataset_id, n, seed)

        ds = build_balanced_dataset_from_pool(
            dataset_id=dataset_id,
            axes=["gender", "age", "origin"],
            n_target=n,
            seed=seed,
            name=name,
        )
        return {"id": int(ds.id), "name": str(ds.name)}

    def build_random_subset(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build a random subset from an existing dataset.

        Args:
            params: Dictionary with dataset_id, n, seed, name

        Returns:
            Dictionary with new dataset id and name
        """
        dataset_id = int(params["dataset_id"])
        n = int(params.get("n", 500))
        seed = int(params.get("seed", 42))
        name = params.get("name")

        ds = build_random_subset_from_pool(
            dataset_id=dataset_id, n=n, seed=seed, name=name
        )
        return {"id": int(ds.id), "name": str(ds.name)}

    def build_counterfactuals(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Build counterfactual dataset from an existing dataset.

        Args:
            params: Dictionary with dataset_id, seed, name

        Returns:
            Dictionary with new dataset id and name
        """
        dataset_id = int(params["dataset_id"])
        seed = int(params.get("seed", 42))
        name = params.get("name")

        ds = build_counterfactuals_from_dataset(
            dataset_id=dataset_id, seed=seed, name=name
        )
        return {"id": int(ds.id), "name": str(ds.name)}

    def generate_pool_sync(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a pool dataset synchronously.

        Args:
            params: Dictionary with n, temperature, age_from, age_to, name

        Returns:
            Dictionary with dataset id and name
        """
        n = int(params["n"])
        temperature = float(params["temperature"])
        age_from = int(params["age_from"])
        age_to = int(params["age_to"])
        name = params.get("name")

        self.validator.validate_dataset_build_params(n, temperature, age_from, age_to)

        sampling_params = self._build_sampling_params(temperature, age_from, age_to)
        sampled = sample_personas(n=n, **sampling_params)
        ds_id = persist_run_and_personas(
            n=n, params=sampling_params, sampled=sampled, export_csv_path=None
        )
        ds = Dataset.get_by_id(ds_id)

        if name:
            ds.name = str(name)
            ds.save()

        return {"id": int(ds.id), "name": str(ds.name)}

    def start_pool_generation(self, params: Dict[str, Any]) -> Dict[str, int]:
        """Start pool generation in background.

        Args:
            params: Dictionary with n, temperature, age_from, age_to, name

        Returns:
            Dictionary with job_id
        """
        n = int(params["n"])
        temperature = float(params["temperature"])
        age_from = int(params["age_from"])
        age_to = int(params["age_to"])
        name = params.get("name")

        self.validator.validate_dataset_build_params(n, temperature, age_from, age_to)

        job_id = self.progress_tracker.create_pool_job(
            status="queued", total=n, done=0, pct=0.0
        )

        def run_job():
            self._run_pool_generation(job_id, n, temperature, age_from, age_to, name)

        self.job_runner.run_async(run_job)
        return {"job_id": job_id}

    def _run_pool_generation(
        self,
        job_id: int,
        n: int,
        temperature: float,
        age_from: int,
        age_to: int,
        name: str | None,
    ) -> None:
        """Execute pool generation job."""
        try:
            self.progress_tracker.update_pool_progress(job_id, status="sampling")
            sampling_params = self._build_sampling_params(temperature, age_from, age_to)
            t0 = time.time()
            sampled = sample_personas(n=n, **sampling_params)

            self.progress_tracker.update_pool_progress(
                job_id, status="inserting", started_at=t0
            )

            def progress_callback(done: int, total: int, phase: str):
                now = time.time()
                dt = max(1e-6, now - t0)
                rate = done / dt
                remaining = max(0, total - done)
                eta = remaining / rate if rate > 0 else None
                self.progress_tracker.update_pool_progress(
                    job_id,
                    done=done,
                    total=total,
                    pct=(done / total * 100.0) if total else 0.0,
                    eta_sec=int(eta) if eta is not None else None,
                    phase=phase,
                )

            ds_id = persist_run_and_personas(
                n=n,
                params=sampling_params,
                sampled=sampled,
                export_csv_path=None,
                progress_cb=progress_callback,
            )
            ds = Dataset.get_by_id(ds_id)

            if name:
                ds.name = str(name)
                ds.save()

            self.progress_tracker.update_pool_progress(
                job_id, status="done", dataset_id=int(ds.id), pct=100.0, done=n
            )
        except Exception as e:
            self.progress_tracker.update_pool_progress(
                job_id, status="failed", error=str(e)
            )

    def get_pool_status(self, job_id: int) -> Dict[str, Any]:
        """Get status of a pool generation job."""
        progress = self.progress_tracker.get_pool_progress(job_id)
        if not progress:
            return {"status": "unknown"}
        return progress.to_dict()

    def start_balanced_generation(self, params: Dict[str, Any]) -> Dict[str, int]:
        """Start balanced dataset generation in background."""
        dataset_id = int(params["dataset_id"])
        n = int(params.get("n", 2000))
        seed = int(params.get("seed", 42))
        name = params.get("name")

        self.validator.validate_balanced_params(dataset_id, n, seed)

        job_id = self.progress_tracker.create_balanced_job(
            status="queued", total=n, done=0, pct=0.0
        )

        def run_job():
            self._run_balanced_generation(job_id, dataset_id, n, seed, name)

        self.job_runner.run_async(run_job)
        return {"job_id": job_id}

    def _run_balanced_generation(
        self, job_id: int, dataset_id: int, n: int, seed: int, name: str | None
    ) -> None:
        """Execute balanced generation job."""
        try:
            self.progress_tracker.update_balanced_progress(job_id, status="selecting")
            t0 = time.time()

            ds = build_balanced_dataset_from_pool(
                dataset_id=dataset_id,
                axes=["gender", "age", "origin"],
                n_target=n,
                seed=seed,
                name=name,
            )

            self.progress_tracker.update_balanced_progress(
                job_id,
                status="done",
                dataset_id=int(ds.id),
                pct=100.0,
                done=n,
                eta_sec=0,
                started_at=t0,
            )
        except Exception as e:
            self.progress_tracker.update_balanced_progress(
                job_id, status="failed", error=str(e)
            )

    def get_balanced_status(self, job_id: int) -> Dict[str, Any]:
        """Get status of a balanced generation job."""
        progress = self.progress_tracker.get_balanced_progress(job_id)
        if not progress:
            return {"status": "unknown"}
        return progress.to_dict()

    def start_dataset_deletion(self, dataset_id: int) -> Dict[str, int]:
        """Start dataset deletion in background."""
        job_id = self.progress_tracker.create_delete_job(
            status="queued", done=0, total=None, pct=0.0
        )

        def run_job():
            self._run_dataset_deletion(job_id, dataset_id)

        self.job_runner.run_async(run_job)
        return {"job_id": job_id}

    def _run_dataset_deletion(self, job_id: int, dataset_id: int) -> None:
        """Execute dataset deletion job."""
        try:
            self.progress_tracker.update_delete_progress(job_id, status="deleting")
            t0 = time.time()

            # Use chunked deletion for large datasets
            stats = self.dataset_repo.delete_dataset_chunked(dataset_id)

            self.progress_tracker.update_delete_progress(
                job_id,
                status="done",
                pct=100.0,
                eta_sec=0,
                started_at=t0,
                done=stats.get("deleted_orphan_personas", 0),
            )
        except Exception as e:
            self.progress_tracker.update_delete_progress(
                job_id, status="failed", error=str(e)
            )

    def get_delete_status(self, job_id: int) -> Dict[str, Any]:
        """Get status of a dataset deletion job."""
        progress = self.progress_tracker.get_delete_progress(job_id)
        if not progress:
            return {"status": "unknown"}
        return progress.to_dict()

    def delete_dataset_sync(self, dataset_id: int) -> Dict[str, Any]:
        """Delete a dataset synchronously.

        Args:
            dataset_id: The dataset ID to delete

        Returns:
            Dictionary with deletion statistics
        """
        stats = self.dataset_repo.delete_dataset_with_cascade(dataset_id)
        return {"ok": True, **stats}

    def _build_sampling_params(
        self, temperature: float, age_from: int, age_to: int
    ) -> Dict[str, Any]:
        """Build sampling parameters dictionary."""
        return {
            "age_min": age_from,
            "age_max": age_to,
            "age_temperature": temperature,
            "education_temperature": temperature,
            "education_exclude": None,
            "gender_temperature": temperature,
            "gender_exclude": None,
            "occupation_exclude": None,
            "marriage_status_temperature": temperature,
            "marriage_status_exclude": None,
            "migration_status_temperature": temperature,
            "migration_status_exclude": None,
            "origin_temperature": temperature,
            "origin_exclude": None,
            "religion_temperature": temperature,
            "religion_exclude": None,
            "sexuality_temperature": temperature,
            "sexuality_exclude": None,
        }
