"""Service for benchmark run lifecycle management.

Handles:
- Listing and retrieving benchmark runs
- Starting, cancelling, and deleting runs
- Progress tracking and status queries
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List

import peewee as pw

from backend.infrastructure.benchmark import data_loader, progress_tracker
from backend.infrastructure.benchmark.executor import execute_benchmark_run
from backend.infrastructure.storage.models import (
    AttrGenerationRun,
    BenchmarkResult,
    BenchmarkRun,
    DatasetPersona,
    Model,
)


class BenchmarkRunService:
    """Service for managing benchmark run lifecycle."""

    def list_runs(self) -> List[Dict[str, Any]]:
        """List all benchmark runs."""
        out: List[Dict[str, Any]] = []
        for r in BenchmarkRun.select().join(Model).order_by(BenchmarkRun.id.desc()):
            out.append(
                {
                    "id": int(r.id),
                    "model_name": str(r.model_id.name),
                    "include_rationale": bool(r.include_rationale),
                    "system_prompt": str(r.system_prompt) if r.system_prompt else None,
                    "dataset_id": int(r.dataset_id.id) if r.dataset_id else None,
                    "created_at": str(r.created_at),
                    "n_results": BenchmarkResult.select()
                    .where(BenchmarkResult.benchmark_run_id == r.id)
                    .count(),
                }
            )
        return out

    def get_run(self, run_id: int) -> Dict[str, Any]:
        """Get details of a benchmark run."""
        r = BenchmarkRun.get_or_none(BenchmarkRun.id == run_id)
        if not r:
            return {
                "id": run_id,
                "model_name": "unknown",
                "include_rationale": False,
                "dataset": None,
                "created_at": None,
            }
        return {
            "id": int(r.id),
            "model_name": str(r.model_id.name),
            "include_rationale": bool(r.include_rationale),
            "system_prompt": str(r.system_prompt) if r.system_prompt else None,
            "n_results": BenchmarkResult.select()
            .where(BenchmarkResult.benchmark_run_id == r.id)
            .count(),
            "dataset": (
                {
                    "id": int(r.dataset_id.id) if r.dataset_id else None,
                    "name": str(r.dataset_id.name) if r.dataset_id else None,
                    "kind": str(r.dataset_id.kind) if r.dataset_id else None,
                }
                if r.dataset_id
                else None
            ),
            "created_at": str(r.created_at),
        }

    def list_models(self) -> List[str]:
        """List all models."""
        return [m.name for m in Model.select()]

    def start_benchmark(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start a benchmark run.

        Args:
            params: Dict with dataset_id, model_name, and optional parameters

        Returns:
            Dict with ok=True and run_id on success
        """
        ds_id = int(params["dataset_id"])
        resume_run_id = params.get("resume_run_id")
        include_rationale = bool(params.get("include_rationale", False))
        llm = params.get("llm", "vllm")
        batch_size = int(params.get("batch_size", 2))
        vllm_base_url = params.get("vllm_base_url")
        attrgen_run_id = params.get("attrgen_run_id")
        max_new_tokens = int(params.get("max_new_tokens", 256))
        max_attempts = int(params.get("max_attempts", 3))
        system_prompt = params.get("system_prompt")
        vllm_api_key = params.get("vllm_api_key")
        scale_mode = params.get("scale_mode")
        dual_fraction = params.get("dual_fraction")

        if resume_run_id is not None:
            rec = BenchmarkRun.get_by_id(int(resume_run_id))
            if int(rec.dataset_id.id) != ds_id:
                raise ValueError("resume_run_id gehört zu einem anderen Dataset")
            rec.include_rationale = (
                include_rationale
                if "include_rationale" in params
                else rec.include_rationale
            )
            rec.batch_size = batch_size or rec.batch_size
            rec.max_attempts = max_attempts or rec.max_attempts
            rec.system_prompt = (
                system_prompt if system_prompt is not None else rec.system_prompt
            )
            if scale_mode in ("in", "rev", "random50"):
                try:
                    rec.scale_mode = scale_mode
                except Exception:
                    pass
            if isinstance(dual_fraction, (int, float)):
                try:
                    rec.dual_fraction = float(dual_fraction)
                except Exception:
                    pass
            rec.save()
            run_id = int(rec.id)
            progress_tracker.set_progress(
                run_id,
                {
                    "status": "queued",
                    "dataset_id": ds_id,
                    "llm": llm,
                    "batch_size": batch_size,
                    "vllm_base_url": vllm_base_url,
                    "vllm_api_key": vllm_api_key,
                    "max_new_tokens": max_new_tokens,
                    "skip_completed": True,
                    "scale_mode": scale_mode,
                    "dual_fraction": (
                        float(dual_fraction)
                        if isinstance(dual_fraction, (int, float))
                        else None
                    ),
                    "attrgen_run_id": (
                        int(attrgen_run_id) if attrgen_run_id is not None else None
                    ),
                    "cancel_requested": False,
                },
            )
        else:
            model_name = str(params["model_name"])
            model_entry, _ = Model.get_or_create(name=model_name)
            rec = BenchmarkRun.create(
                dataset_id=ds_id,
                model_id=model_entry.id,
                include_rationale=include_rationale,
                batch_size=batch_size,
                max_attempts=max_attempts,
                system_prompt=system_prompt,
                scale_mode=scale_mode,
                dual_fraction=(
                    float(dual_fraction)
                    if isinstance(dual_fraction, (int, float))
                    else None
                ),
            )
            run_id = int(rec.id)
            if attrgen_run_id is not None:
                try:
                    r = AttrGenerationRun.get_by_id(int(attrgen_run_id))
                    if int(r.dataset_id.id) != ds_id:
                        raise ValueError(
                            "attrgen_run_id gehört zu einem anderen Dataset"
                        )
                except Exception as e:
                    return {"ok": False, "error": str(e)}
            progress_tracker.set_progress(
                run_id,
                {
                    "status": "queued",
                    "dataset_id": ds_id,
                    "llm": llm,
                    "batch_size": batch_size,
                    "vllm_base_url": vllm_base_url,
                    "vllm_api_key": vllm_api_key,
                    "max_new_tokens": max_new_tokens,
                    "scale_mode": scale_mode,
                    "dual_fraction": (
                        float(dual_fraction)
                        if isinstance(dual_fraction, (int, float))
                        else None
                    ),
                    "attrgen_run_id": (
                        int(attrgen_run_id) if attrgen_run_id is not None else None
                    ),
                    "cancel_requested": False,
                },
            )

        t = threading.Thread(
            target=execute_benchmark_run,
            args=(
                run_id,
                progress_tracker.set_progress,
                progress_tracker.get_progress,
                progress_tracker.update_progress,
                progress_tracker.get_completed_keys,
            ),
            daemon=False,
            name=f"BenchmarkRun-{run_id}",
        )
        t.start()
        try:
            t_poll = threading.Thread(
                target=progress_tracker.progress_poller,
                args=(run_id, ds_id),
                daemon=True,
                name=f"ProgressPoller-{run_id}",
            )
            t_poll.start()
        except Exception:
            pass
        return {"ok": True, "run_id": run_id}

    def get_status(self, run_id: int) -> Dict[str, Any]:
        """Get status of a benchmark run."""
        info = progress_tracker.get_progress(run_id)

        # If no progress info in memory, check if it's an old completed run
        if not info:
            try:
                rec = BenchmarkRun.get_by_id(run_id)
                ds_id = int(rec.dataset_id.id)

                from backend.infrastructure.benchmark.repository.trait import (
                    TraitRepository,
                )

                traits_n = TraitRepository().count()
                personas_n = (
                    DatasetPersona.select()
                    .where(DatasetPersona.dataset_id == ds_id)
                    .count()
                )
                dual_frac = float(rec.dual_fraction or 0.0)
                total = int(personas_n * traits_n * (1.0 + dual_frac))

                result_count = (
                    BenchmarkResult.select(
                        BenchmarkResult.persona_uuid_id,
                        BenchmarkResult.case_id,
                        BenchmarkResult.scale_order,
                    )
                    .where(BenchmarkResult.benchmark_run_id == run_id)
                    .distinct()
                    .count()
                )

                failed_count = 0
                try:
                    from backend.infrastructure.storage.models import FailLog

                    failed_count = (
                        FailLog.select(FailLog.persona_uuid_id, FailLog.case_id)
                        .where(
                            (FailLog.benchmark_run_id == run_id)
                            & (FailLog.error_kind == "max_attempts_exceeded")
                        )
                        .distinct()
                        .count()
                    )
                except Exception:
                    pass

                done = result_count + failed_count

                if done > 0:
                    status = "done" if (total > 0 and done >= total) else "partial"
                    pct = (done / total * 100.0) if total > 0 else 0.0

                    info = {
                        "status": status,
                        "dataset_id": ds_id,
                        "done": done,
                        "total": total,
                        "pct": pct,
                    }
                else:
                    info = {"status": "unknown"}

            except Exception:
                info = {"status": "unknown"}
        else:
            status = info.get("status", "unknown")
            if status in {"queued", "running", "cancelling"}:
                try:
                    rec = BenchmarkRun.get_by_id(run_id)
                    ds_id = int(rec.dataset_id.id)
                    progress_tracker.update_progress(run_id, ds_id)
                    info = progress_tracker.get_progress(run_id)
                except Exception:
                    pass
            elif status in {"done", "partial"}:
                try:
                    done = int(info.get("done") or 0)
                    total = int(info.get("total") or 0)
                    if total == 0 or done >= total:
                        info["status"] = "done"
                except Exception:
                    pass

        return {"ok": True, **(info or {})}

    def cancel_benchmark(self, run_id: int) -> Dict[str, Any]:
        """Cancel a running benchmark."""
        info = progress_tracker.get_progress(run_id)
        if not info:
            return {
                "ok": False,
                "error": "Benchmark-Run unbekannt oder bereits beendet",
            }
        state = info.get("status")
        if state not in {"queued", "running", "partial", "cancelling"}:
            return {
                "ok": False,
                "error": f"Benchmark ist nicht aktiv (Status: {state})",
            }
        if state == "cancelling":
            return {"ok": True}
        info["cancel_requested"] = True
        info["status"] = "cancelling"
        progress_tracker.set_progress(run_id, info)
        return {"ok": True}

    def get_active_benchmark(self, dataset_id: int) -> Dict[str, Any]:
        """Get active benchmark for a dataset."""
        ds_id = int(dataset_id)
        for run_id in list(progress_tracker._BENCH_PROGRESS.keys()):
            info = progress_tracker.get_progress(run_id)
            if info.get("dataset_id") != ds_id:
                continue
            status = info.get("status", "unknown")
            if status not in {"queued", "running", "cancelling"}:
                continue
            try:
                progress_tracker.update_progress(run_id, ds_id)
                info = progress_tracker.get_progress(run_id)
                status = info.get("status", "unknown")
                if status not in {"queued", "running", "cancelling"}:
                    continue
            except Exception:
                pass
            return {
                "ok": True,
                "active": True,
                "run_id": run_id,
                "status": info.get("status"),
                "done": info.get("done"),
                "total": info.get("total"),
                "pct": info.get("pct"),
                "error": info.get("error"),
            }
        return {"ok": True, "active": False}

    def delete_run(self, run_id: int) -> Dict[str, Any]:
        """Delete a benchmark run and all results."""
        progress_tracker.clear_progress(run_id)
        try:
            deleted = BenchmarkRun.delete().where(BenchmarkRun.id == run_id).execute()
            data_loader.clear_cache()
            return {"ok": True, "deleted": int(deleted)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_missing(self, run_id: int) -> Dict[str, Any]:
        """Get missing benchmark results."""
        from backend.infrastructure.benchmark.repository.trait import TraitRepository

        rec = BenchmarkRun.get_or_none(BenchmarkRun.id == run_id)
        if not rec:
            return {"ok": False, "error": "run_not_found"}
        dataset_id = int(rec.dataset_id.id)

        traits_n = TraitRepository().count()
        personas_n = (
            DatasetPersona.select()
            .where(DatasetPersona.dataset_id == dataset_id)
            .count()
        )
        dual_frac = float(rec.dual_fraction or 0.0)
        total = int(personas_n * traits_n * (1.0 + dual_frac))
        done = (
            BenchmarkResult.select(
                BenchmarkResult.persona_uuid_id,
                BenchmarkResult.case_id,
                BenchmarkResult.scale_order,
            )
            .where(BenchmarkResult.benchmark_run_id == run_id)
            .distinct()
            .count()
        )

        failed_count = 0
        try:
            from backend.infrastructure.storage.models import FailLog

            failed_query = (
                FailLog.select(FailLog.persona_uuid_id, FailLog.case_id)
                .where(
                    (FailLog.benchmark_run_id == run_id)
                    & (FailLog.error_kind == "max_attempts_exceeded")
                )
                .distinct()
            )
            failed_count = failed_query.count()
            done += failed_count
        except Exception:
            pass

        MAX_DIRECT_SCAN = 500_000
        skip_heavy_scan = bool(total and total > MAX_DIRECT_SCAN)
        missing = max(0, (total or 0) - (done or 0))
        samples: List[Dict[str, Any]] = []
        sampling_limited = skip_heavy_scan

        if not skip_heavy_scan:
            from backend.infrastructure.storage.models import Trait

            trait_alias = Trait.alias()

            try:
                pct_missing = missing / total if total > 0 else 0
                if pct_missing > 0.05:
                    raise TimeoutError("Too many missing items to scan efficiently")

                if dual_frac > 0 or rec.scale_mode in ("random50", "in", "rev"):
                    raise TimeoutError(
                        "Complex scale mode - skipping exact missing scan"
                    )

                cnt_query = (
                    DatasetPersona.select(pw.fn.COUNT(1))
                    .join(trait_alias, pw.JOIN.CROSS)
                    .switch(DatasetPersona)
                    .join(
                        BenchmarkResult,
                        pw.JOIN.LEFT_OUTER,
                        on=(
                            (BenchmarkResult.benchmark_run_id == run_id)
                            & (
                                BenchmarkResult.persona_uuid_id
                                == DatasetPersona.persona_id
                            )
                            & (BenchmarkResult.case_id == trait_alias.id)
                        ),
                    )
                    .where(
                        (DatasetPersona.dataset_id == dataset_id)
                        & (BenchmarkResult.id.is_null(True))
                        & (trait_alias.is_active == True)
                    )
                )
                missing = int(cnt_query.scalar() or 0)
            except Exception:
                missing = max(0, (total or 0) - (done or 0))
                sampling_limited = True

            if not sampling_limited:
                try:
                    sample_query = (
                        DatasetPersona.select(
                            DatasetPersona.persona_id,
                            trait_alias.id.alias("case_id"),
                            trait_alias.adjective.alias("adjective"),
                        )
                        .join(trait_alias, pw.JOIN.CROSS)
                        .switch(DatasetPersona)
                        .join(
                            BenchmarkResult,
                            pw.JOIN.LEFT_OUTER,
                            on=(
                                (BenchmarkResult.benchmark_run_id == run_id)
                                & (
                                    BenchmarkResult.persona_uuid_id
                                    == DatasetPersona.persona_id
                                )
                                & (BenchmarkResult.case_id == trait_alias.id)
                            ),
                        )
                        .where(
                            (DatasetPersona.dataset_id == dataset_id)
                            & (BenchmarkResult.id.is_null(True))
                            & (trait_alias.is_active == True)
                        )
                        .limit(20)
                        .tuples()
                    )
                    for pid, cid, adj in sample_query:
                        samples.append(
                            {
                                "persona_uuid": str(pid),
                                "case_id": str(cid),
                                "adjective": str(adj) if adj is not None else None,
                            }
                        )
                except Exception:
                    samples = []

        return {
            "ok": True,
            "dataset_id": dataset_id,
            "total": total,
            "done": done,
            "missing": missing,
            "failed": failed_count,
            "samples": samples,
            "sampling_limited": sampling_limited,
        }
