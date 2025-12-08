"""Service for exporting benchmark run data."""

from __future__ import annotations

from typing import Any, Dict, Optional

from backend.application.services.analysis_service import get_analysis_service
from backend.application.services.benchmark_analytics_service import (
    BenchmarkAnalyticsService,
)
from backend.application.services.benchmark_run_service import BenchmarkRunService


class BenchmarkExportService:
    """Service for exporting benchmark run data."""

    def __init__(self):
        self.run_service = BenchmarkRunService()
        self.analytics_service = BenchmarkAnalyticsService()
        self.analysis_service = get_analysis_service()

    def get_export_data(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Collect and format all run data for export."""
        # 1. Run Details
        run = self.run_service.get_run(run_id)
        if not run:
            return None

        # 2. Metrics (Rating Distribution)
        metrics = self.analytics_service.get_metrics(run_id)

        # 3. Order Metrics
        order_metrics = self.analytics_service.get_order_metrics(run_id)

        # 4. Quick Analysis
        quick_analysis = self.analysis_service.get_quick_summary(run_id)
        if quick_analysis is None:
            quick_analysis = self.analysis_service.run_quick_analysis(run_id)

        # 5. Bias Analysis (Overall & Per Category)
        all_deltas = self.analytics_service.get_all_deltas(run_id)
        bias_overall = self._format_bias_analysis(all_deltas)

        bias_by_category = {}
        if metrics.get("ok") and metrics.get("trait_categories"):
            for cat_summary in metrics["trait_categories"].get("summary", []):
                cat = cat_summary["category"]
                cat_deltas = self.analytics_service.get_all_deltas(
                    run_id, trait_category=cat
                )
                formatted = self._format_bias_analysis(cat_deltas)
                if formatted:
                    bias_by_category[cat] = formatted

        # Construct Report
        report = {
            "meta": {
                "model": run.get("model_name"),
                "dataset": run.get("dataset", {}).get("name"),
                "date": run.get("created_at"),
                "results_count": run.get("n_results"),
                "system_prompt": run.get("system_prompt"),
            },
            "performance": {
                "error_rate": (
                    quick_analysis.get("error_rate") if quick_analysis else None
                ),
                "total_errors": (
                    quick_analysis.get("error_count") if quick_analysis else None
                ),
                "rating_distribution": None,
            },
            "order_consistency": None,
            "bias_analysis": {
                "overall": bias_overall,
                "by_trait_category": bias_by_category,
            },
        }

        # Format Rating Distribution
        if metrics.get("ok") and metrics.get("hist"):
            hist = metrics["hist"]
            shares = hist.get("shares", [])
            counts = hist.get("counts", [])
            report["performance"]["rating_distribution"] = [
                {
                    "rating": i + 1,
                    "share": round(share, 3),
                    "count": counts[i] if i < len(counts) else None,
                }
                for i, share in enumerate(shares)
            ]

        # Format Order Metrics
        if order_metrics.get("ok"):
            rma = order_metrics.get("rma", {})
            report["order_consistency"] = {
                "n_pairs": order_metrics.get("n_pairs"),
                "rma": rma.get("exact_rate"),
                "mae": rma.get("mae"),
                "cliffs_delta": rma.get("cliffs_delta"),
                "correlation": order_metrics.get("correlation"),
                "test_retest": order_metrics.get("test_retest"),
                "by_trait_category": (
                    [
                        {
                            "category": c.get("trait_category"),
                            "mae": c.get("abs_diff"),
                            "n": c.get("n"),
                        }
                        for c in order_metrics.get("by_trait_category", [])
                    ]
                    if order_metrics.get("by_trait_category")
                    else None
                ),
            }

        return report

    def _format_bias_analysis(
        self, deltas_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Helper to format bias analysis data."""
        if not deltas_data.get("ok") or not deltas_data.get("data"):
            return None

        scores = {}
        attributes = []

        # Constants for Score Calculation (matching Frontend BiasRadarChart.tsx)
        CLIFFS_SCALE_FACTOR = 4.0

        for attribute, res in deltas_data["data"].items():
            if not res.get("ok") or not res.get("rows"):
                continue

            rows = res["rows"]

            # Calculate Bias Score using Cliff's Delta (matching Frontend)
            # Formula: Score = 100 * (0.6 * scaledMax + 0.4 * scaledAvg)
            # where scaled = min(val * 4.0, 1.0)
            cliffs_deltas = [
                abs(r.get("cliffs_delta"))
                for r in rows
                if r.get("cliffs_delta") is not None
            ]

            if cliffs_deltas:
                max_abs_cliffs = max(cliffs_deltas)
                avg_abs_cliffs = sum(cliffs_deltas) / len(cliffs_deltas)

                scaled_max = min(max_abs_cliffs * CLIFFS_SCALE_FACTOR, 1.0)
                scaled_avg = min(avg_abs_cliffs * CLIFFS_SCALE_FACTOR, 1.0)

                score = (0.6 * scaled_max + 0.4 * scaled_avg) * 100
            else:
                score = 0

            scores[attribute] = round(score, 1)

            significant = [r for r in rows if r.get("significant")]
            if significant:
                attributes.append(
                    {
                        "attribute": attribute,
                        "intensity_score": round(score, 1),
                        "significant_findings_count": len(significant),
                        "findings": [
                            {
                                "category": r.get("category"),
                                "baseline": r.get("baseline"),
                                "delta": round(r.get("delta", 0), 3),
                                "p_value": round(r.get("p_value", 0), 4),
                                "cliffs_delta": (
                                    round(r.get("cliffs_delta", 0), 3)
                                    if r.get("cliffs_delta") is not None
                                    else None
                                ),
                                "interpretation": (
                                    "Higher than baseline"
                                    if r.get("delta", 0) > 0
                                    else "Lower than baseline"
                                ),
                            }
                            for r in significant
                        ],
                    }
                )

        return {"intensity_scores": scores, "detailed_findings": attributes}
