"""Service for benchmark analytics and metrics.

Handles:
- Rating metrics and histograms
- Order effect analysis
- Bias analysis (deltas, means, forest plots)
- Cache warming
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from backend.domain.analytics.benchmarks import analytics as bench_ana
from backend.domain.analytics.benchmarks.analytics import (
    benjamini_hochberg,
    mann_whitney_cliffs,
)
from backend.domain.analytics.benchmarks.metrics import (
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
from backend.infrastructure.storage import benchmark_cache
from backend.infrastructure.storage.models import Trait

METRICS_CACHE_VERSION = (
    5  # Bump when changing metrics structure (histograms now use rating_raw)
)
ORDER_CACHE_VERSION = 4  # Bump: now uses rating_raw instead of rating_pre_valence


class BenchmarkAnalyticsService:
    """Service for benchmark analytics and metrics."""

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
                "age_group",
                "origin_region",
                "origin_subregion",
                "religion",
                "sexuality",
                "marriage_status",
                "education",
                "occupation",
                "occupation_category",
                "migration_status",
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
        ck = benchmark_cache.cache_key(run_id, "order", {"v": ORDER_CACHE_VERSION})
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
            # Use rating_raw for order effect analysis (raw values before any transformation)
            rating_col = "rating_raw" if "rating_raw" in work.columns else "rating"
            sub = work.loc[
                work["scale_order"].isin(["in", "rev"]) & work[rating_col].notna(),
                ["persona_uuid", "case_id", rating_col, "scale_order"],
            ]
            if not sub.empty:
                piv = sub.pivot_table(
                    index=["persona_uuid", "case_id"],
                    columns="scale_order",
                    values=rating_col,
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
                                trait_map[str(r.id)] = str(r.adjective)
                                trait_cat_map[str(r.id)] = str(r.category or "")
                        except Exception:
                            pass

                        by_case = (
                            pairs.groupby("case_id")
                            .agg(
                                n=("in", "count"),
                                mean_in=("in", "mean"),
                                mean_rev=("rev", "mean"),
                                abs_diff_mean=("abs_diff", "mean"),
                            )
                            .reset_index()
                        )

                        for _, row in by_case.iterrows():
                            cid = str(row["case_id"])
                            expected_rev = 6.0 - row["mean_in"]
                            rma_case = (
                                row["mean_rev"] - expected_rev
                                if row["mean_rev"] == row["mean_rev"]
                                else None
                            )
                            rows.append(
                                {
                                    "case_id": cid,
                                    "label": trait_map.get(cid, cid),
                                    "trait_category": trait_cat_map.get(cid, ""),
                                    "n": int(row["n"]),
                                    "mean_in": (
                                        float(row["mean_in"])
                                        if row["mean_in"] == row["mean_in"]
                                        else None
                                    ),
                                    "mean_rev": (
                                        float(row["mean_rev"])
                                        if row["mean_rev"] == row["mean_rev"]
                                        else None
                                    ),
                                    "abs_diff": (
                                        float(row["abs_diff_mean"])
                                        if row["abs_diff_mean"] == row["abs_diff_mean"]
                                        else None
                                    ),
                                    "rma": (
                                        float(rma_case)
                                        if rma_case is not None and rma_case == rma_case
                                        else None
                                    ),
                                }
                            )

                        metrics["by_case"] = rows

                        # Aggregate by trait category
                        by_cat = (
                            pairs.merge(
                                pd.DataFrame(
                                    [
                                        {"case_id": k, "trait_category": v}
                                        for k, v in trait_cat_map.items()
                                    ]
                                ),
                                on="case_id",
                                how="left",
                            )
                            .groupby("trait_category")
                            .agg(
                                n=("in", "count"),
                                abs_diff_mean=("abs_diff", "mean"),
                            )
                            .reset_index()
                        )
                        metrics["by_trait_category"] = [
                            {
                                "trait_category": str(row["trait_category"]),
                                "n": int(row["n"]),
                                "abs_diff": (
                                    float(row["abs_diff_mean"])
                                    if row["abs_diff_mean"] == row["abs_diff_mean"]
                                    else None
                                ),
                            }
                            for _, row in by_cat.iterrows()
                        ]

        # Ensure by_case and by_trait_category are always present
        if "by_case" not in metrics:
            metrics["by_case"] = []
        if "by_trait_category" not in metrics:
            metrics["by_trait_category"] = []

        payload = {"ok": True, **metrics}
        benchmark_cache.put_cached(run_id, "order", ck, payload)
        return payload

    def get_all_means(self, run_id: int) -> Dict[str, Any]:
        """Get means for all standard attributes."""
        attributes = [
            "gender",
            "age_group",
            "origin_subregion",
            "religion",
            "migration_status",
            "sexuality",
            "marriage_status",
            "education",
            "occupation_category",
        ]
        results = {}
        for attr in attributes:
            res = self.get_means(run_id, attr)
            if res.get("ok"):
                results[attr] = res.get("rows", [])
            else:
                results[attr] = []
        return {"ok": True, "data": results}

    def get_all_deltas(
        self, run_id: int, trait_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get deltas for all standard attributes, optionally filtered by trait category."""
        attributes = [
            "gender",
            "age_group",
            "origin_subregion",
            "religion",
            "migration_status",
            "sexuality",
            "marriage_status",
            "education",
            "occupation_category",
        ]
        results = {}
        for attr in attributes:
            res = self.get_deltas(run_id, attr, trait_category=trait_category)
            if res.get("ok"):
                results[attr] = res
            else:
                results[attr] = {"ok": False}
        return {"ok": True, "data": results}

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
        rating_col = (
            "rating_pre_valence" if "rating_pre_valence" in work.columns else "rating"
        )
        work[attribute] = work[attribute].fillna("Unknown").astype(str)
        if baseline is None:
            s = work.groupby(attribute)[rating_col].size().sort_values(ascending=False)
            baseline = str(s.index[0]) if not s.empty else "Unknown"
        if target is None:
            s2 = (
                work.loc[work[attribute] != baseline]
                .groupby(attribute)[rating_col]
                .size()
                .sort_values(ascending=False)
            )
            target = str(s2.index[0]) if not s2.empty else None

        agg = (
            work.groupby(["case_id", "trait_category", attribute])[rating_col]
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

            # Compute Mann-Whitney + Cliff's Delta per trait
            for row in merged.itertuples(index=False):
                case_id = str(row.case_id)
                # Get raw ratings for this trait
                base_ratings = pd.to_numeric(
                    work.loc[
                        (work[attribute] == baseline) & (work["case_id"] == case_id),
                        rating_col,
                    ],
                    errors="coerce",
                ).dropna()
                cat_ratings = pd.to_numeric(
                    work.loc[
                        (work[attribute] == cat) & (work["case_id"] == case_id),
                        rating_col,
                    ],
                    errors="coerce",
                ).dropna()

                # Mann-Whitney U test + Cliff's Delta
                if len(base_ratings) >= 2 and len(cat_ratings) >= 2:
                    _, p_val, cliffs_d = mann_whitney_cliffs(base_ratings, cat_ratings)
                else:
                    p_val = float("nan")
                    cliffs_d = float("nan")

                rows_list.append(
                    {
                        "case_id": case_id,
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
                        "p_value": float(p_val) if np.isfinite(p_val) else None,
                        "cliffs_delta": (
                            float(cliffs_d) if np.isfinite(cliffs_d) else None
                        ),
                    }
                )

        labels_map: Dict[str, str] = {
            str(c.id): str(c.adjective) for c in Trait.select()
        }
        valence_map: Dict[str, int | None] = {
            str(c.id): c.valence for c in Trait.select()
        }
        for r in rows_list:
            r["label"] = labels_map.get(r["case_id"], r["case_id"])
            r["valence"] = valence_map.get(r["case_id"])

        # Apply FDR correction (Benjamini-Hochberg) to p-values
        if rows_list:
            p_values = [
                r.get("p_value") if r.get("p_value") is not None else float("nan")
                for r in rows_list
            ]
            try:
                q_values = benjamini_hochberg(p_values)
            except Exception:
                q_values = [float("nan")] * len(rows_list)

            for r, q_val in zip(rows_list, q_values):
                r["q_value"] = float(q_val) if np.isfinite(q_val) else None
                # Significant after FDR correction at alpha=0.05
                p_val = r.get("p_value")
                r["significant"] = bool(
                    q_val is not None and np.isfinite(q_val) and q_val < 0.05
                )
                # Also store uncorrected significance for reference
                r["significant_uncorrected"] = bool(
                    p_val is not None and np.isfinite(p_val) and p_val < 0.05
                )

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
            self.get_kruskal_wallis,
            self.get_kruskal_wallis_by_trait_category,
        )
        return {"ok": True, **job}

    def get_warm_cache_status(self, run_id: int) -> Dict[str, Any]:
        """Get warm cache job status."""
        job = cache_warming.get_warm_cache_job(run_id)
        return cache_warming.warm_job_snapshot(run_id, job)

    def get_missing(self, run_id: int) -> Dict[str, Any]:
        """Delegate to run service for cache warming compatibility."""
        from backend.application.services.benchmark_run_service import (
            BenchmarkRunService,
        )

        return BenchmarkRunService().get_missing(run_id)

    def get_kruskal_wallis(self, run_id: int) -> Dict[str, Any]:
        """Kruskal-Wallis H-Test für alle demographischen Attribute.

        Führt einen Omnibus-Test durch, der prüft, ob sich die Verteilung
        der Antworten zwischen den Gruppen eines Attributs signifikant
        unterscheidet.

        Returns:
            Dict mit:
            - attributes: Liste der Testergebnisse pro Attribut
                - attribute: Name des Attributs
                - h_stat: Kruskal-Wallis H-Statistik
                - p_value: p-Wert
                - eta_squared: Effektstärke η²
                - n_groups: Anzahl der Gruppen
                - n_total: Gesamtanzahl Beobachtungen
                - significant: bool (p < 0.05)
                - effect_interpretation: "klein"/"mittel"/"groß"
            - summary: Übersicht (anzahl signifikant, total)
        """
        from backend.domain.analytics.benchmarks.analytics import (
            kruskal_wallis_all_attributes,
        )

        # Check cache first
        ck = "all"
        cached = benchmark_cache.get_cached(run_id, "kruskal_wallis", ck)
        if cached is not None:
            return cached

        # Load data using the same loader as other methods
        df = data_loader.df_for_read(run_id, progress_tracker.get_progress)
        if df is None or df.empty:
            return {"attributes": [], "summary": {"significant_count": 0, "total": 0}}

        # Ensure rating column exists (used by kruskal_wallis_by_attribute)
        if "rating" not in df.columns and "rating_pre_valence" not in df.columns:
            return {"attributes": [], "summary": {"significant_count": 0, "total": 0}}

        # Run Kruskal-Wallis test for all attributes
        results = kruskal_wallis_all_attributes(df)

        # Interpret effect sizes
        def interpret_eta_squared(eta_sq: float) -> str:
            """Cohen's benchmarks for η²."""
            if eta_sq < 0.01:
                return "vernachlässigbar"
            elif eta_sq < 0.06:
                return "klein"
            elif eta_sq < 0.14:
                return "mittel"
            else:
                return "groß"

        attributes = []
        significant_count = 0

        for attr, data in results.items():
            # Skip entries with errors
            if "error" in data:
                continue

            p_val = data.get("p_value")
            if p_val is None:
                continue

            is_sig = p_val < 0.05
            if is_sig:
                significant_count += 1

            h_stat = data.get("h_statistic", 0.0)
            eta_sq = data.get("effect_size_eta2", 0.0)

            attributes.append(
                {
                    "attribute": attr,
                    "h_stat": round(h_stat, 3) if h_stat else 0.0,
                    "p_value": p_val,
                    "eta_squared": round(eta_sq, 4) if eta_sq else 0.0,
                    "n_groups": data.get("n_groups", 0),
                    "n_total": data.get("n_total", 0),
                    "significant": is_sig,
                    "effect_interpretation": (
                        interpret_eta_squared(eta_sq) if eta_sq else "vernachlässigbar"
                    ),
                }
            )

        # Sort by effect size descending
        attributes.sort(key=lambda x: x["eta_squared"], reverse=True)

        payload = {
            "attributes": attributes,
            "summary": {
                "significant_count": significant_count,
                "total": len(attributes),
            },
        }

        benchmark_cache.put_cached(run_id, "kruskal_wallis", ck, payload)
        return payload

    def get_kruskal_wallis_by_trait_category(self, run_id: int) -> Dict[str, Any]:
        """Kruskal-Wallis H-Test pro Trait-Kategorie.

        Führt den Omnibus-Test separat für jede Trait-Kategorie durch
        (z.B. Kompetenz, Wärme, Moral, etc.).

        Returns:
            Dict mit:
            - categories: Dict mapping trait_category -> results
                - attributes: Liste der Testergebnisse pro Attribut
                - summary: Übersicht für diese Kategorie
        """
        from backend.domain.analytics.benchmarks.analytics import (
            kruskal_wallis_by_trait_category,
        )

        # Check cache first
        ck = "all"
        cached = benchmark_cache.get_cached(run_id, "kruskal_wallis", ck)
        if cached is not None:
            return cached

        # Load data using the same loader as other methods
        df = data_loader.df_for_read(run_id, progress_tracker.get_progress)
        if df is None or df.empty:
            return {"attributes": [], "summary": {"significant_count": 0, "total": 0}}

        # Ensure rating column exists (used by kruskal_wallis_by_attribute)
        if "rating" not in df.columns and "rating_pre_valence" not in df.columns:
            return {"attributes": [], "summary": {"significant_count": 0, "total": 0}}

        # Run Kruskal-Wallis test for all attributes
        results = kruskal_wallis_all_attributes(df)

        # Interpret effect sizes
        def interpret_eta_squared(eta_sq: float) -> str:
            """Cohen's benchmarks for η²."""
            if eta_sq < 0.01:
                return "vernachlässigbar"
            elif eta_sq < 0.06:
                return "klein"
            elif eta_sq < 0.14:
                return "mittel"
            else:
                return "groß"

        attributes = []
        significant_count = 0

        for attr, data in results.items():
            # Skip entries with errors
            if "error" in data:
                continue

            p_val = data.get("p_value")
            if p_val is None:
                continue

            is_sig = p_val < 0.05
            if is_sig:
                significant_count += 1

            h_stat = data.get("h_statistic", 0.0)
            eta_sq = data.get("effect_size_eta2", 0.0)

            attributes.append(
                {
                    "attribute": attr,
                    "h_stat": round(h_stat, 3) if h_stat else 0.0,
                    "p_value": p_val,
                    "eta_squared": round(eta_sq, 4) if eta_sq else 0.0,
                    "n_groups": data.get("n_groups", 0),
                    "n_total": data.get("n_total", 0),
                    "significant": is_sig,
                    "effect_interpretation": (
                        interpret_eta_squared(eta_sq) if eta_sq else "vernachlässigbar"
                    ),
                }
            )

        # Sort by effect size descending
        attributes.sort(key=lambda x: x["eta_squared"], reverse=True)

        payload = {
            "attributes": attributes,
            "summary": {
                "significant_count": significant_count,
                "total": len(attributes),
            },
        }

        benchmark_cache.put_cached(run_id, "kruskal_wallis", ck, payload)
        return payload

    def get_kruskal_wallis_by_trait_category(self, run_id: int) -> Dict[str, Any]:
        """Kruskal-Wallis H-Test pro Trait-Kategorie.

        Führt den Omnibus-Test separat für jede Trait-Kategorie durch
        (z.B. Kompetenz, Wärme, Moral, etc.).

        Returns:
            Dict mit:
            - categories: Dict mapping trait_category -> results
                - attributes: Liste der Testergebnisse pro Attribut
                - summary: Übersicht für diese Kategorie
        """
        from backend.domain.analytics.benchmarks.analytics import (
            kruskal_wallis_by_trait_category,
        )

        # Check cache first
        ck = "by_trait_category"
        cached = benchmark_cache.get_cached(run_id, "kruskal_wallis", ck)
        if cached is not None:
            return cached

        # Load data
        df = data_loader.df_for_read(run_id, progress_tracker.get_progress)
        if df is None or df.empty:
            return {"categories": {}}

        # Ensure required columns exist
        if "rating" not in df.columns and "rating_pre_valence" not in df.columns:
            return {"categories": {}}
        if "trait_category" not in df.columns:
            return {"categories": {}}

        # Run Kruskal-Wallis test per trait category
        results_by_cat = kruskal_wallis_by_trait_category(df)

        # Interpret effect sizes
        def interpret_eta_squared(eta_sq: float) -> str:
            """Cohen's benchmarks for η²."""
            if eta_sq < 0.01:
                return "vernachlässigbar"
            elif eta_sq < 0.06:
                return "klein"
            elif eta_sq < 0.14:
                return "mittel"
            else:
                return "groß"

        # Format results
        categories_output = {}

        for trait_cat, attr_results in results_by_cat.items():
            attributes = []
            significant_count = 0

            for attr, data in attr_results.items():
                # Skip entries with errors
                if "error" in data:
                    continue

                p_val = data.get("p_value")
                if p_val is None:
                    continue

                is_sig = p_val < 0.05
                if is_sig:
                    significant_count += 1

                h_stat = data.get("h_statistic", 0.0)
                eta_sq = data.get("effect_size_eta2", 0.0)

                attributes.append(
                    {
                        "attribute": attr,
                        "h_stat": round(h_stat, 3) if h_stat else 0.0,
                        "p_value": p_val,
                        "eta_squared": round(eta_sq, 4) if eta_sq else 0.0,
                        "n_groups": data.get("n_groups", 0),
                        "n_total": data.get("n_total", 0),
                        "significant": is_sig,
                        "effect_interpretation": (
                            interpret_eta_squared(eta_sq)
                            if eta_sq
                            else "vernachlässigbar"
                        ),
                    }
                )

            # Sort by effect size descending
            attributes.sort(key=lambda x: x["eta_squared"], reverse=True)

            categories_output[trait_cat] = {
                "attributes": attributes,
                "summary": {
                    "significant_count": significant_count,
                    "total": len(attributes),
                },
            }

        payload = {"categories": categories_output}
        benchmark_cache.put_cached(run_id, "kruskal_wallis", ck, payload)
        return payload

    # ========================================================================
    # Multi-Run Comparison Methods
    # ========================================================================

    def get_multi_run_metrics(self, run_ids: List[int]) -> Dict[str, Any]:
        """Get aggregated metrics across multiple runs.

        Combines rating distributions and basic statistics.
        """
        if not run_ids:
            return {"ok": False, "error": "No run IDs provided"}

        all_ratings = []
        run_metadata = []
        total_n = 0

        for run_id in run_ids:
            df = data_loader.df_for_read(run_id, progress_tracker.get_progress)
            if df.empty:
                continue

            # Get run info
            run_info = self._get_run_info(run_id)
            run_metadata.append(
                {
                    "run_id": run_id,
                    "model": run_info.get("model_name", "Unknown"),
                    "n": len(df),
                }
            )

            all_ratings.extend(df["rating_raw"].dropna().tolist())
            total_n += len(df)

        if not all_ratings:
            return {
                "ok": True,
                "n": 0,
                "runs": run_metadata,
                "hist": {"bins": [], "shares": [], "counts": []},
                "mean": None,
                "median": None,
            }

        # Create combined dataframe for histogram
        # compute_rating_histogram expects 'rating' column
        combined_df = pd.DataFrame({"rating": all_ratings, "rating_raw": all_ratings})
        hist = compute_rating_histogram(combined_df)

        return {
            "ok": True,
            "n": total_n,
            "runs": run_metadata,
            "hist": hist,
            "mean": float(np.mean(all_ratings)),
            "median": float(np.median(all_ratings)),
        }

    def get_multi_run_order_metrics(self, run_ids: List[int]) -> Dict[str, Any]:
        """Get aggregated order consistency metrics across multiple runs."""
        if not run_ids:
            return {"ok": False, "error": "No run IDs provided"}

        all_metrics = []

        for run_id in run_ids:
            try:
                metrics = self.get_order_metrics(run_id)
                if metrics.get("ok"):
                    run_info = self._get_run_info(run_id)

                    # Extract scalar metrics only, skip nested dicts
                    run_data = {
                        "run_id": run_id,
                        "model": run_info.get("model_name", "Unknown"),
                        "n_pairs": metrics.get("n_pairs", 0),
                    }

                    # Extract RMA metrics (exact_rate is the main metric)
                    if isinstance(metrics.get("rma"), dict):
                        run_data["rma"] = metrics["rma"].get("exact_rate")
                        run_data["rma_mae"] = metrics["rma"].get("mae")
                        run_data["rma_cliff_delta"] = metrics["rma"].get("cliffs_delta")
                    else:
                        run_data["rma"] = metrics.get("rma")
                        run_data["rma_mae"] = None
                        run_data["rma_cliff_delta"] = None

                    # Extract correlation (use Spearman as default)
                    if isinstance(metrics.get("correlation"), dict):
                        run_data["correlation"] = metrics["correlation"].get("spearman")
                        run_data["correlation_pearson"] = metrics["correlation"].get(
                            "pearson"
                        )
                        run_data["correlation_kendall"] = metrics["correlation"].get(
                            "kendall"
                        )
                    else:
                        run_data["correlation"] = metrics.get("correlation")
                        run_data["correlation_pearson"] = None
                        run_data["correlation_kendall"] = None

                    # Extract test-retest metrics
                    if isinstance(metrics.get("test_retest"), dict):
                        run_data["mae"] = metrics["test_retest"].get("mean_abs_diff")
                        run_data["within1_rate"] = metrics["test_retest"].get(
                            "within1_rate"
                        )
                    else:
                        run_data["mae"] = None
                        run_data["within1_rate"] = None

                    all_metrics.append(run_data)
            except Exception as e:
                # Log error but continue with other runs
                print(f"Error processing run {run_id}: {e}")
                continue

        if not all_metrics:
            return {"ok": False, "error": "No valid order metrics found"}

        # Aggregate metrics - filter out None values
        def safe_mean(values):
            filtered = [
                v for v in values if v is not None and isinstance(v, (int, float))
            ]
            return float(np.mean(filtered)) if filtered else None

        aggregated = {
            "ok": True,
            "runs": all_metrics,
            "summary": {
                "n_runs": len(all_metrics),
                "avg_rma": safe_mean([m.get("rma") for m in all_metrics]),
                "avg_rma_mae": safe_mean([m.get("rma_mae") for m in all_metrics]),
                "avg_correlation": safe_mean(
                    [m.get("correlation") for m in all_metrics]
                ),
                "avg_mae": safe_mean([m.get("mae") for m in all_metrics]),
                "avg_within1_rate": safe_mean(
                    [m.get("within1_rate") for m in all_metrics]
                ),
            },
        }

        return aggregated

    def get_multi_run_deltas(
        self, run_ids: List[int], trait_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get aggregated bias deltas across multiple runs.

        Returns bias intensity scores for all standard attributes,
        aggregated across the selected runs.

        Uses the same bias intensity formula as single-run analysis:
        Score = 100 × (0.6 × min(Max|d| × 4.0, 1) + 0.4 × min(Avg|d| × 4.0, 1))
        """
        if not run_ids:
            return {"ok": False, "error": "No run IDs provided"}

        # Standard attributes to analyze
        attributes = [
            "gender",
            "age_group",
            "origin_subregion",
            "religion",
            "migration_status",
            "sexuality",
            "marriage_status",
            "education",
        ]

        # Cliff's Delta scale factor (same as frontend)
        CLIFFS_SCALE_FACTOR = 4.0

        result = {
            "ok": True,
            "trait_category": trait_category or "all",
            "n_runs": len(run_ids),
            "data": {},
        }

        for attr in attributes:
            attr_deltas = []

            for run_id in run_ids:
                try:
                    # Get all deltas for this attribute
                    delta_data = self.get_all_deltas(
                        run_id, trait_category=trait_category
                    )

                    if delta_data.get("ok") and attr in delta_data.get("data", {}):
                        attr_data = delta_data["data"][attr]

                        # Extract cliff delta values for aggregation
                        if attr_data.get("ok") and "rows" in attr_data:
                            for delta_entry in attr_data["rows"]:
                                if delta_entry.get("cliffs_delta") is not None:
                                    attr_deltas.append(abs(delta_entry["cliffs_delta"]))
                except Exception:
                    continue

            if attr_deltas:
                max_cliffs = float(np.max(attr_deltas))
                avg_cliffs = float(np.mean(attr_deltas))

                # Apply same scaling and formula as single-run analysis
                scaled_max = min(max_cliffs * CLIFFS_SCALE_FACTOR, 1.0)
                scaled_avg = min(avg_cliffs * CLIFFS_SCALE_FACTOR, 1.0)
                bias_intensity = (0.6 * scaled_max + 0.4 * scaled_avg) * 100

                result["data"][attr] = {
                    "n_comparisons": len(attr_deltas),
                    "max_delta": max_cliffs,
                    "avg_delta": avg_cliffs,
                    "median_delta": float(np.median(attr_deltas)),
                    "bias_intensity": float(bias_intensity),
                }
            else:
                result["data"][attr] = {
                    "n_comparisons": 0,
                    "max_delta": None,
                    "avg_delta": None,
                    "median_delta": None,
                    "bias_intensity": None,
                }

        return result

    def _get_run_info(self, run_id: int) -> Dict[str, Any]:
        """Get basic run information."""
        from backend.infrastructure.storage.models import BenchmarkRun

        run = BenchmarkRun.get_or_none(BenchmarkRun.id == run_id)
        if not run:
            return {"model_name": "Unknown", "created_at": None}

        return {
            "model_name": str(run.model_id.name) if run.model_id else "Unknown",
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
