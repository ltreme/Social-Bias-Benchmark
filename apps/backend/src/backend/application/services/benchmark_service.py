"""Benchmark service orchestrating use cases."""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import peewee as pw

from backend.domain.analytics.benchmarks import analytics as bench_ana
from backend.domain.analytics.benchmarks.metrics import (
    UNKNOWN_TRAIT_CATEGORY,
    compute_means_by_attribute,
    compute_order_effect_metrics,
    compute_rating_histogram,
    compute_trait_category_histograms,
    compute_trait_category_summary,
    filter_by_trait_category,
)
from backend.infrastructure.benchmark import (
    cache_warming,
    data_loader,
    progress_tracker,
)
from backend.infrastructure.benchmark.executor import execute_benchmark_run
from backend.infrastructure.storage import benchmark_cache
from backend.infrastructure.storage.models import (
    AttrGenerationRun,
    BenchmarkResult,
    BenchmarkRun,
    DatasetPersona,
    Model,
    Trait,
)

METRICS_CACHE_VERSION = 2


class BenchmarkService:
    """Service for managing benchmark runs and analysis."""

    def list_runs(self) -> List[Dict[str, Any]]:
        """List all benchmark runs."""
        out: List[Dict[str, Any]] = []
        for r in BenchmarkRun.select().join(Model).order_by(BenchmarkRun.id.desc()):
            out.append(
                {
                    "id": int(r.id),
                    "model_name": str(r.model_id.name),
                    "include_rationale": bool(r.include_rationale),
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
            daemon=True,
        )
        t.start()
        try:
            t_poll = threading.Thread(
                target=progress_tracker.progress_poller,
                args=(run_id, ds_id),
                daemon=True,
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

                # Check if there are any results for this run
                result_count = (
                    BenchmarkResult.select()
                    .where(BenchmarkResult.benchmark_run_id == run_id)
                    .count()
                )

                if result_count > 0:
                    # Run has results but no active progress -> it's done
                    info = {"status": "done", "dataset_id": ds_id}
                else:
                    # No results at all -> unknown/never started
                    info = {"status": "unknown"}

            except Exception:
                info = {"status": "unknown"}
        else:
            # Progress info exists - check if it's actually running or just cached
            status = info.get("status", "unknown")
            if status in {"queued", "running", "cancelling"}:
                # Actively running - update progress
                try:
                    rec = BenchmarkRun.get_by_id(run_id)
                    ds_id = int(rec.dataset_id.id)
                    progress_tracker.update_progress(run_id, ds_id)
                    info = progress_tracker.get_progress(run_id)
                except Exception:
                    pass
            elif status in {"done", "partial"}:
                # Was running before but finished - verify status
                try:
                    done = int(info.get("done") or 0)
                    total = int(info.get("total") or 0)
                    # If done >= total or total is 0, mark as done (not partial)
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
            # Only truly active statuses - not "partial" or "done"
            if status not in {"queued", "running", "cancelling"}:
                continue
            try:
                progress_tracker.update_progress(run_id, ds_id)
                info = progress_tracker.get_progress(run_id)
                # Re-check status after update
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

    def get_metrics(self, run_id: int) -> Dict[str, Any]:
        """Get comprehensive metrics for a run."""
        ck = benchmark_cache.cache_key(run_id, "metrics", {"v": METRICS_CACHE_VERSION})
        cached = benchmark_cache.get_cached(run_id, "metrics", ck)
        if cached:
            return cached

        df = data_loader.df_for_read(run_id, progress_tracker.get_progress)
        if df.empty:
            payload = {
                "ok": True,
                "n": 0,
                "hist": {"bins": [], "shares": []},
                "attributes": {},
            }
            benchmark_cache.put_cached(run_id, "metrics", ck, payload)
            return payload

        hist = compute_rating_histogram(df)

        def attr_meta(col: str) -> Dict[str, Any]:
            if col not in df.columns:
                return {"categories": [], "baseline": None}
            work = df.copy()
            work[col] = work[col].fillna("Unknown")
            tab = bench_ana.summarise_rating_by(work, col)[[col, "count", "mean"]]
            base = None
            if not tab.empty:
                base = str(tab.sort_values("count", ascending=False)[col].iloc[0])
            cats_meta = [
                {
                    "category": str(r[col]),
                    "count": int(r["count"]),
                    "mean": float(r["mean"]),
                }
                for _, r in tab.iterrows()
            ]
            return {"categories": cats_meta, "baseline": base}

        attrs = {
            k: attr_meta(k)
            for k in [
                "gender",
                "origin_region",
                "religion",
                "sexuality",
                "marriage_status",
                "education",
            ]
        }

        cat_hists = compute_trait_category_histograms(df)
        cat_summary = compute_trait_category_summary(df)

        payload = {
            "ok": True,
            "n": int(len(df)),
            "hist": hist,
            "trait_categories": {
                "histograms": cat_hists,
                "summary": cat_summary,
            },
            "attributes": attrs,
        }
        benchmark_cache.put_cached(run_id, "metrics", ck, payload)
        return payload

    def get_order_metrics(self, run_id: int) -> Dict[str, Any]:
        """Get order effect metrics."""
        ck = benchmark_cache.cache_key(run_id, "order", {})
        cached = benchmark_cache.get_cached(run_id, "order", ck)
        if cached:
            return cached

        df = data_loader.df_for_read(run_id, progress_tracker.get_progress)
        if df.empty:
            payload = {
                "ok": True,
                "n_pairs": 0,
                "rma": {},
                "obe": {},
                "usage": {},
                "test_retest": {},
                "correlation": {},
                "by_case": [],
            }
            benchmark_cache.put_cached(run_id, "order", ck, payload)
            return payload

        metrics = compute_order_effect_metrics(df)

        # Per-case breakdown
        if "scale_order" in df.columns:
            work = df.copy()
            sub = work.loc[
                work["scale_order"].isin(["in", "rev"]) & work["rating"].notna(),
                ["persona_uuid", "case_id", "rating", "scale_order"],
            ]
            if not sub.empty:
                piv = sub.pivot_table(
                    index=["persona_uuid", "case_id"],
                    columns="scale_order",
                    values="rating",
                    aggfunc="first",
                ).reset_index()
                if "in" in piv.columns and "rev" in piv.columns:
                    pairs = piv.dropna(subset=["in", "rev"]).copy()
                    if not pairs.empty:
                        pairs["abs_diff"] = (
                            pairs["in"].astype(float) - pairs["rev"].astype(float)
                        ).abs()

                        rows: List[Dict[str, Any]] = []
                        try:
                            trait_map = {}
                            trait_cat_map = {}
                            for r in Trait.select():
                                trait_map[str(r.id)] = r.adjective or str(r.id)
                                trait_cat_map[str(r.id)] = (
                                    r.category or UNKNOWN_TRAIT_CATEGORY
                                )
                        except Exception:
                            trait_map = {}
                            trait_cat_map = {}

                        for k, g in pairs.groupby("case_id"):
                            ad = float((g["abs_diff"] == 0).mean()) if len(g) else 0.0
                            rows.append(
                                {
                                    "case_id": str(k),
                                    "adjective": trait_map.get(str(k)),
                                    "trait_category": trait_cat_map.get(str(k))
                                    or UNKNOWN_TRAIT_CATEGORY,
                                    "n_pairs": int(len(g)),
                                    "exact_rate": ad,
                                    "mae": (
                                        float(g["abs_diff"].mean()) if len(g) else 0.0
                                    ),
                                }
                            )

                        # By category
                        by_cat = []
                        cat_stats: Dict[str, Dict[str, Any]] = {}
                        for r in rows:
                            cat = r.get("trait_category") or UNKNOWN_TRAIT_CATEGORY
                            entry = cat_stats.setdefault(
                                cat,
                                {
                                    "trait_category": cat,
                                    "n_pairs": 0,
                                    "exact_sum": 0.0,
                                    "mae_sum": 0.0,
                                },
                            )
                            n_pairs_case = int(r.get("n_pairs") or 0)
                            entry["n_pairs"] += n_pairs_case
                            entry["exact_sum"] += (
                                float(r.get("exact_rate") or 0.0) * n_pairs_case
                            )
                            entry["mae_sum"] += (
                                float(r.get("mae") or 0.0) * n_pairs_case
                            )
                        for cat, stat in cat_stats.items():
                            n_pairs_cat = stat["n_pairs"] or 0
                            if n_pairs_cat <= 0:
                                continue
                            by_cat.append(
                                {
                                    "trait_category": cat,
                                    "n_pairs": n_pairs_cat,
                                    "exact_rate": stat["exact_sum"] / n_pairs_cat,
                                    "mae": stat["mae_sum"] / n_pairs_cat,
                                }
                            )

                        metrics["by_case"] = rows
                        metrics["by_trait_category"] = by_cat

        payload = {"ok": True, **metrics}
        benchmark_cache.put_cached(run_id, "order", ck, payload)
        return payload

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
        total = personas_n * traits_n
        done = (
            BenchmarkResult.select(
                BenchmarkResult.persona_uuid_id, BenchmarkResult.case_id
            )
            .where(BenchmarkResult.benchmark_run_id == run_id)
            .distinct()
            .count()
        )

        MAX_DIRECT_SCAN = 500_000
        skip_heavy_scan = bool(total and total > MAX_DIRECT_SCAN)
        missing = max(0, (total or 0) - (done or 0))
        samples: List[Dict[str, Any]] = []
        sampling_limited = skip_heavy_scan

        if not skip_heavy_scan:
            trait_alias = Trait.alias()
            try:
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
                    )
                )
                missing = int(cnt_query.scalar() or 0)
            except Exception:
                missing = max(0, (total or 0) - (done or 0))

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
            "samples": samples,
            "sampling_limited": sampling_limited,
        }

    def get_deltas(
        self,
        run_id: int,
        attribute: str,
        baseline: Optional[str] = None,
        n_perm: int = 1000,
        alpha: float = 0.05,
        trait_category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get delta analysis."""
        ck = benchmark_cache.cache_key(
            run_id,
            "deltas",
            {
                "attribute": attribute,
                "baseline": baseline,
                "n_perm": int(n_perm),
                "alpha": float(alpha),
                "trait_category": trait_category,
            },
        )
        cached = benchmark_cache.get_cached(run_id, "deltas", ck)
        if cached:
            return cached

        df = filter_by_trait_category(
            data_loader.df_for_read(run_id, progress_tracker.get_progress),
            trait_category,
        )
        if df.empty or attribute not in df.columns:
            payload = {"ok": True, "n": 0, "rows": []}
            benchmark_cache.put_cached(run_id, "deltas", ck, payload)
            return payload

        result = bench_ana.build_deltas_payload(
            df, attribute, baseline=baseline, n_perm=n_perm, alpha=alpha
        )
        payload = {"ok": True, **result}
        benchmark_cache.put_cached(run_id, "deltas", ck, payload)
        return payload

    def get_means(
        self,
        run_id: int,
        attribute: str,
        top_n: Optional[int] = None,
        trait_category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get mean ratings by attribute."""
        ck = benchmark_cache.cache_key(
            run_id,
            "means",
            {"attribute": attribute, "top_n": top_n, "trait_category": trait_category},
        )
        cached = benchmark_cache.get_cached(run_id, "means", ck)
        if cached:
            return cached

        df = data_loader.df_for_read(run_id, progress_tracker.get_progress)
        if df.empty or attribute not in df.columns:
            payload = {"ok": True, "rows": []}
            benchmark_cache.put_cached(run_id, "means", ck, payload)
            return payload

        work = filter_by_trait_category(df, trait_category)
        if work.empty:
            payload = {"ok": True, "rows": []}
            benchmark_cache.put_cached(run_id, "means", ck, payload)
            return payload

        rows = compute_means_by_attribute(work, attribute, top_n)
        payload = {"ok": True, "rows": rows}
        benchmark_cache.put_cached(run_id, "means", ck, payload)
        return payload

    def get_forest(
        self,
        run_id: int,
        attribute: str,
        baseline: Optional[str] = None,
        target: Optional[str] = None,
        min_n: int = 1,
        trait_category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get forest plot data."""
        ck = benchmark_cache.cache_key(
            run_id,
            "forest",
            {
                "attribute": attribute,
                "baseline": baseline,
                "target": target,
                "min_n": int(min_n),
                "trait_category": trait_category,
            },
        )
        cached = benchmark_cache.get_cached(run_id, "forest", ck)
        if cached:
            return cached

        df = filter_by_trait_category(
            data_loader.df_for_read(run_id, progress_tracker.get_progress),
            trait_category,
        )
        if df.empty or attribute not in df.columns:
            payload = {"ok": True, "n": 0, "rows": []}
            benchmark_cache.put_cached(run_id, "forest", ck, payload)
            return payload

        work = df.copy()
        work[attribute] = work[attribute].fillna("Unknown").astype(str)
        if baseline is None:
            s = work.groupby(attribute)["rating"].size().sort_values(ascending=False)
            baseline = str(s.index[0]) if not s.empty else "Unknown"
        if target is None:
            s2 = (
                work.loc[work[attribute] != baseline]
                .groupby(attribute)["rating"]
                .size()
                .sort_values(ascending=False)
            )
            target = str(s2.index[0]) if not s2.empty else None

        agg = (
            work.groupby(["case_id", "trait_category", attribute])["rating"]
            .agg(count="count", mean="mean", std="std")
            .reset_index()
        )
        agg = agg.loc[agg["case_id"].astype(str).str.startswith("g")]
        if agg.empty:
            payload = {"ok": True, "n": 0, "rows": []}
            benchmark_cache.put_cached(run_id, "forest", ck, payload)
            return payload

        baseline_df = agg.loc[agg[attribute] == baseline].set_index(
            ["case_id", "trait_category"]
        )
        if baseline_df.empty:
            payload = {"ok": True, "n": 0, "rows": []}
            benchmark_cache.put_cached(run_id, "forest", ck, payload)
            return payload

        rows_list: List[Dict[str, Any]] = []
        cats = (
            [target]
            if target is not None
            else [
                c
                for c in agg[attribute].dropna().unique().tolist()
                if str(c) != str(baseline)
            ]
        )
        cats = [c for c in cats if c is not None]

        for cat in cats:
            cat_df = agg.loc[agg[attribute] == cat].set_index(
                ["case_id", "trait_category"]
            )
            merged = (
                baseline_df.join(
                    cat_df,
                    how="inner",
                    lsuffix="_base",
                    rsuffix="_cat",
                )
                .reset_index()
                .rename(columns={"index": "case_id"})
            )
            if merged.empty:
                continue
            merged = merged.loc[
                (merged["count_base"] >= min_n) & (merged["count_cat"] >= min_n)
            ].copy()
            if merged.empty:
                continue
            merged["delta"] = merged["mean_cat"] - merged["mean_base"]
            merged["se"] = np.sqrt(
                (merged["std_base"] ** 2) / merged["count_base"]
                + (merged["std_cat"] ** 2) / merged["count_cat"]
            )
            se_mask = (merged["count_base"] > 1) & (merged["count_cat"] > 1)
            merged.loc[~se_mask, "se"] = np.nan
            merged["ci_low"] = merged["delta"] - 1.96 * merged["se"]
            merged["ci_high"] = merged["delta"] + 1.96 * merged["se"]
            for row in merged.itertuples(index=False):
                rows_list.append(
                    {
                        "case_id": str(row.case_id),
                        "category": str(cat),
                        "baseline": str(baseline),
                        "trait_category": str(row.trait_category),
                        "n_base": int(row.count_base),
                        "n_cat": int(row.count_cat),
                        "delta": (
                            float(row.delta) if row.delta == row.delta else float("nan")
                        ),
                        "se": float(row.se) if row.se == row.se else None,
                        "ci_low": (
                            float(row.ci_low) if row.ci_low == row.ci_low else None
                        ),
                        "ci_high": (
                            float(row.ci_high) if row.ci_high == row.ci_high else None
                        ),
                    }
                )

        labels_map: Dict[str, str] = {
            str(c.id): str(c.adjective) for c in Trait.select()
        }
        for r in rows_list:
            r["label"] = labels_map.get(r["case_id"], r["case_id"])

        if rows_list:
            arr = pd.DataFrame(rows_list)
            if arr["se"].notna().any():
                sub = arr.loc[arr["se"].notna()].copy()
                w = 1.0 / (sub["se"] ** 2)
                w = w.replace([np.inf, -np.inf], np.nan).fillna(0.0)
                mu = (
                    float(np.nansum(w * sub["delta"]) / np.nansum(w))
                    if np.nansum(w) > 0
                    else float("nan")
                )
                se_mu = (
                    float(np.sqrt(1.0 / np.nansum(w)))
                    if np.nansum(w) > 0
                    else float("nan")
                )
                overall = {
                    "mean": mu if np.isfinite(mu) else None,
                    "ci_low": mu - 1.96 * se_mu if np.isfinite(se_mu) else None,
                    "ci_high": mu + 1.96 * se_mu if np.isfinite(se_mu) else None,
                }
            else:
                overall = {"mean": None, "ci_low": None, "ci_high": None}
        else:
            overall = {"mean": None, "ci_low": None, "ci_high": None}

        rows_list.sort(
            key=lambda r: (
                r["delta"] if (r["delta"] == r["delta"]) else float("inf"),
                (r.get("label") or r["case_id"]),
            )
        )
        payload = {
            "ok": True,
            "n": len(rows_list),
            "rows": rows_list,
            "overall": overall,
        }
        benchmark_cache.put_cached(run_id, "forest", ck, payload)
        return payload

    def start_warm_cache(self, run_id: int) -> Dict[str, Any]:
        """Start warm cache job."""
        job = cache_warming.start_warm_cache_job(
            run_id,
            self.get_metrics,
            self.get_missing,
            self.get_order_metrics,
            self.get_means,
            self.get_deltas,
            self.get_forest,
        )
        return {"ok": True, **job}

    def get_warm_cache_status(self, run_id: int) -> Dict[str, Any]:
        """Get warm cache job status."""
        job = cache_warming.get_warm_cache_job(run_id)
        return cache_warming.warm_job_snapshot(run_id, job)
