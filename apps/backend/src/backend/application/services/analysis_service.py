"""Analysis service for benchmark run analysis.

This service handles:
- Quick analysis (automatic after benchmark completion)
- Deep analysis (on-demand via queue)
- Analysis status tracking
- Result caching
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.infrastructure.storage.db import get_db
from backend.infrastructure.storage.models import (
    AnalysisJob,
    BenchmarkResult,
    BenchmarkRun,
)

_LOG = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_params(params: Optional[Dict[str, Any]]) -> Optional[str]:
    """Create a hash of analysis parameters for cache key."""
    if not params:
        return None
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]


class AnalysisService:
    """Service for benchmark run analysis."""

    def get_analysis_status(self, run_id: int) -> Dict[str, Any]:
        """Get status of all analyses for a run.

        Returns:
            Dict with analysis types and their status/summary
        """
        db = get_db()
        jobs = list(
            AnalysisJob.select()
            .where(AnalysisJob.run == run_id)
            .order_by(AnalysisJob.created_at)
            .dicts()
        )

        result = {
            "run_id": run_id,
            "analyses": {},
        }

        for job in jobs:
            key = job["analysis_type"]
            if job["params_hash"]:
                # For parameterized analyses (e.g., bias:gender)
                params = json.loads(job["params_json"]) if job["params_json"] else {}
                key = f"{job['analysis_type']}:{params.get('attribute', 'unknown')}"

            result["analyses"][key] = {
                "status": job["status"],
                "created_at": (
                    job["created_at"].isoformat() if job["created_at"] else None
                ),
                "completed_at": (
                    job["completed_at"].isoformat() if job["completed_at"] else None
                ),
                "duration_ms": job["duration_ms"],
                "error": job["error"],
                "summary": (
                    json.loads(job["summary_json"]) if job["summary_json"] else None
                ),
            }

        return result

    def run_quick_analysis(self, run_id: int) -> Dict[str, Any]:
        """Run quick analysis on a benchmark run.

        This is called automatically after benchmark completion.
        Should complete in <10 seconds.

        Returns:
            Dict with quick analysis results (for Telegram notification)
        """
        db = get_db()
        t0 = time.time()

        # Check if quick analysis already exists
        existing = (
            AnalysisJob.select()
            .where(
                (AnalysisJob.run == run_id)
                & (AnalysisJob.analysis_type == "quick")
                & (AnalysisJob.status == "completed")
            )
            .first()
        )
        if existing and existing.summary_json:
            _LOG.info(f"[Analysis] Quick analysis already exists for run {run_id}")
            return json.loads(existing.summary_json)

        # Create or update job record
        job, created = AnalysisJob.get_or_create(
            run=run_id,
            analysis_type="quick",
            params_hash=None,
            defaults={"status": "running", "started_at": _utcnow()},
        )
        if not created:
            job.status = "running"
            job.started_at = _utcnow()
            job.error = None
            job.save()

        try:
            result = self._compute_quick_analysis(run_id)

            # Save result
            job.status = "completed"
            job.completed_at = _utcnow()
            job.duration_ms = int((time.time() - t0) * 1000)
            job.summary_json = json.dumps(result)
            job.save()

            _LOG.info(
                f"[Analysis] Quick analysis completed for run {run_id} "
                f"in {job.duration_ms}ms"
            )
            return result

        except Exception as e:
            job.status = "failed"
            job.completed_at = _utcnow()
            job.duration_ms = int((time.time() - t0) * 1000)
            job.error = str(e)
            job.save()
            _LOG.error(f"[Analysis] Quick analysis failed for run {run_id}: {e}")
            raise

    def _compute_quick_analysis(self, run_id: int) -> Dict[str, Any]:
        """Compute quick analysis metrics.

        Fast operations only (<10 seconds total):
        - Result count
        - Rating distribution
        - Error rate
        - Sample order-consistency (on subset of dual pairs)
        """
        db = get_db()

        # Get run info
        run = BenchmarkRun.get_or_none(BenchmarkRun.id == run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        # Count results
        total_results = (
            BenchmarkResult.select()
            .where(BenchmarkResult.benchmark_run_id == run_id)
            .count()
        )

        # Rating distribution (fast aggregate query)
        import peewee as pw

        rating_dist_query = (
            BenchmarkResult.select(
                BenchmarkResult.rating, pw.fn.COUNT(BenchmarkResult.id).alias("count")
            )
            .where(
                (BenchmarkResult.benchmark_run_id == run_id)
                & (BenchmarkResult.rating.is_null(False))
            )
            .group_by(BenchmarkResult.rating)
            .dicts()
        )
        rating_dist = {r["rating"]: r["count"] for r in rating_dist_query}
        total_rated = sum(rating_dist.values())

        # Error rate (results without rating)
        error_count = (
            BenchmarkResult.select()
            .where(
                (BenchmarkResult.benchmark_run_id == run_id)
                & (BenchmarkResult.rating.is_null(True))
            )
            .count()
        )
        error_rate = error_count / total_results if total_results > 0 else 0.0

        # Sample order-consistency (fast: use SQL, limit to 1000 pairs)
        order_stats = self._sample_order_consistency(run_id, sample_size=1000)

        # Build result
        result = {
            "run_id": run_id,
            "total_results": total_results,
            "total_rated": total_rated,
            "error_count": error_count,
            "error_rate": round(error_rate, 4),
            "rating_distribution": rating_dist,
            "order_consistency_sample": order_stats,
            "computed_at": _utcnow().isoformat(),
        }

        return result

    def _sample_order_consistency(
        self, run_id: int, sample_size: int = 1000
    ) -> Dict[str, Any]:
        """Compute order-consistency on a sample of dual pairs.

        Uses raw SQL for speed - no DataFrame loading.
        """
        db = get_db()

        # Find dual pairs (personas with both 'in' and 'rev' for same case)
        # and compute agreement metrics on a sample
        sql = """
        WITH dual_pairs AS (
            SELECT 
                persona_uuid_id,
                case_id,
                MAX(CASE WHEN scale_order = 'in' THEN rating END) as rating_in,
                MAX(CASE WHEN scale_order = 'rev' THEN rating END) as rating_rev
            FROM benchmarkresult
            WHERE benchmark_run_id = %s
              AND scale_order IN ('in', 'rev')
              AND rating IS NOT NULL
            GROUP BY persona_uuid_id, case_id
            HAVING COUNT(DISTINCT scale_order) = 2
            LIMIT %s
        )
        SELECT 
            COUNT(*) as n_pairs,
            AVG(CASE WHEN rating_in = (6 - rating_rev) THEN 1.0 ELSE 0.0 END) as rma,
            AVG(ABS(rating_in - (6 - rating_rev))) as mae
        FROM dual_pairs
        """

        cursor = db.execute_sql(sql, (run_id, sample_size))
        row = cursor.fetchone()

        if row and row[0] and row[0] > 0:
            return {
                "n_pairs": row[0],
                "rma": round(float(row[1]), 4) if row[1] else 0.0,
                "mae": round(float(row[2]), 4) if row[2] else 0.0,
                "is_sample": row[0] >= sample_size,
            }

        return {
            "n_pairs": 0,
            "rma": None,
            "mae": None,
            "is_sample": False,
        }

    def get_quick_summary(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Get quick analysis summary if available.

        Returns None if not yet computed.
        """
        job = (
            AnalysisJob.select()
            .where(
                (AnalysisJob.run == run_id)
                & (AnalysisJob.analysis_type == "quick")
                & (AnalysisJob.status == "completed")
            )
            .first()
        )
        if job and job.summary_json:
            return json.loads(job.summary_json)
        return None

    def format_telegram_message(self, run_id: int, summary: Dict[str, Any]) -> str:
        """Format quick analysis summary for Telegram notification."""
        run = BenchmarkRun.get_or_none(BenchmarkRun.id == run_id)
        model_name = run.model.name if run and run.model else "Unknown"
        dataset_name = run.dataset.name if run and run.dataset else "Unknown"

        # Duration (if available from run)
        duration_str = ""
        if run and run.created_at:
            # Approximate duration based on created_at
            duration_str = ""  # Will be filled by caller if available

        total = summary.get("total_results", 0)
        errors = summary.get("error_count", 0)
        error_rate = summary.get("error_rate", 0) * 100

        order_stats = summary.get("order_consistency_sample", {})
        rma = order_stats.get("rma")
        mae = order_stats.get("mae")
        n_pairs = order_stats.get("n_pairs", 0)
        is_sample = order_stats.get("is_sample", False)

        # Build message
        lines = [
            f"✅ Benchmark #{run_id} abgeschlossen",
            "",
            f"📊 {model_name} auf {dataset_name}",
            f"📈 Results: {total:,}",
        ]

        if errors > 0:
            lines.append(f"⚠️ Errors: {errors} ({error_rate:.1f}%)")

        lines.append("")
        lines.append("Quick-Check:")

        if rma is not None:
            sample_note = " (Sample)" if is_sample else ""
            lines.append(
                f"• Order-Consistency: RMA={rma:.2f}, MAE={mae:.2f}{sample_note}"
            )
        else:
            lines.append("• Order-Consistency: Keine Dual-Paare")

        # Rating distribution summary
        dist = summary.get("rating_distribution", {})
        if dist:
            total_rated = sum(dist.values())
            if total_rated > 0:
                extremes = (dist.get(1, 0) + dist.get(5, 0)) / total_rated
                middle = dist.get(3, 0) / total_rated
                lines.append(
                    f"• Extreme (1/5): {extremes*100:.0f}%, Mitte (3): {middle*100:.0f}%"
                )

        return "\n".join(lines)

    def request_deep_analysis(
        self,
        run_id: int,
        analysis_type: str,
        params: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Request a deep analysis to be queued.

        Args:
            run_id: Benchmark run ID
            analysis_type: 'order' | 'bias' | 'export'
            params: Optional parameters (e.g., {"attribute": "gender"})
            force: If True, re-run even if already completed

        Returns:
            Dict with job_id and status
        """
        from backend.application.services.queue_service import QueueService

        db = get_db()
        params_hash = _hash_params(params)

        # Check if analysis already exists
        existing = (
            AnalysisJob.select()
            .where(
                (AnalysisJob.run == run_id)
                & (AnalysisJob.analysis_type == analysis_type)
                & (AnalysisJob.params_hash == params_hash)
            )
            .first()
        )

        job = None

        if existing:
            if not force:
                if existing.status == "completed":
                    return {
                        "job_id": existing.id,
                        "status": "completed",
                        "message": "Analysis already completed",
                    }
                elif existing.status == "running":
                    return {
                        "job_id": existing.id,
                        "status": "running",
                        "message": "Analysis already running",
                    }
                elif existing.status == "pending":
                    return {
                        "job_id": existing.id,
                        "status": "pending",
                        "message": "Analysis already queued",
                    }

            # Force re-run or failed status - reset the job
            existing.status = "pending"
            existing.error = None
            existing.started_at = None
            existing.completed_at = None
            existing.duration_ms = None
            existing.result_json = None
            existing.save()
            job = existing
        else:
            # Create new job record
            job = AnalysisJob.create(
                run=run_id,
                analysis_type=analysis_type,
                params_hash=params_hash,
                status="pending",
                params_json=json.dumps(params) if params else None,
            )

        # Add to queue
        queue_service = QueueService()
        task_config = {
            "analysis_job_id": job.id,
            "run_id": run_id,
            "analysis_type": analysis_type,
            "params": params,
        }

        task_result = queue_service.add_to_queue(
            task_type=f"analysis:{analysis_type}",
            config=task_config,
            label=f"Analyse: {analysis_type} für Run #{run_id}",
        )
        task_id = task_result["task_id"]

        return {
            "job_id": job.id,
            "task_id": task_id,
            "status": "pending",
            "message": f"Analysis queued (task #{task_id})",
        }

    def run_order_analysis(self, run_id: int) -> AnalysisJob:
        """Run full order-consistency analysis.

        Called by the queue executor. This is the deep analysis version
        that computes full order-consistency metrics on all dual pairs.

        Args:
            run_id: Benchmark run ID

        Returns:
            Updated AnalysisJob record
        """
        from backend.application.services.benchmark_analytics_service import (
            BenchmarkAnalyticsService,
        )

        db = get_db()
        t0 = time.time()

        # Get or create job record
        job, created = AnalysisJob.get_or_create(
            run=run_id,
            analysis_type="order",
            params_hash=None,
            defaults={"status": "running", "started_at": _utcnow()},
        )
        if not created:
            job.status = "running"
            job.started_at = _utcnow()
            job.error = None
            job.save()

        try:
            _LOG.info(f"[Analysis] Running full order analysis for run {run_id}")

            # Use BenchmarkAnalyticsService for metrics computation
            analytics_service = BenchmarkAnalyticsService()
            order_result = analytics_service.get_order_metrics(run_id)

            # Extract summary from order_metrics result
            # The result contains rma, mae, and by_case with per-case breakdown
            rma_data = order_result.get("rma", {})

            summary = {
                "run_id": run_id,
                "n_dual_pairs": order_result.get("n_pairs", 0),
                "rma": rma_data,  # Full RMA object with exact_rate, mae, cliffs_delta
                "mae": rma_data.get("mae") if isinstance(rma_data, dict) else None,
                "per_case": order_result.get("by_case", []),
                "full_result": order_result,  # Include full result for debugging
                "computed_at": _utcnow().isoformat(),
            }

            job.status = "completed"
            job.completed_at = _utcnow()
            job.duration_ms = int((time.time() - t0) * 1000)
            job.summary_json = json.dumps(summary)
            job.save()

            _LOG.info(
                f"[Analysis] Order analysis completed for run {run_id}: "
                f"RMA={summary['rma']}, MAE={summary['mae']} "
                f"({job.duration_ms}ms)"
            )
            return job

        except Exception as e:
            job.status = "failed"
            job.completed_at = _utcnow()
            job.duration_ms = int((time.time() - t0) * 1000)
            job.error = str(e)
            job.save()
            _LOG.error(f"[Analysis] Order analysis failed for run {run_id}: {e}")
            return job

    def run_bias_analysis(self, run_id: int, attribute: str) -> AnalysisJob:
        """Run bias analysis for a specific attribute.

        Called by the queue executor.

        Args:
            run_id: Benchmark run ID
            attribute: Attribute to analyze (e.g., 'gender', 'age_group')

        Returns:
            Updated AnalysisJob record
        """
        from backend.application.services.benchmark_analytics_service import (
            BenchmarkAnalyticsService,
        )

        db = get_db()
        t0 = time.time()
        params = {"attribute": attribute}
        params_hash = _hash_params(params)

        # Get or create job record
        job, created = AnalysisJob.get_or_create(
            run=run_id,
            analysis_type="bias",
            params_hash=params_hash,
            defaults={
                "status": "running",
                "started_at": _utcnow(),
                "params_json": json.dumps(params),
            },
        )
        if not created:
            job.status = "running"
            job.started_at = _utcnow()
            job.error = None
            job.save()

        try:
            _LOG.info(
                f"[Analysis] Running bias analysis ({attribute}) for run {run_id}"
            )

            # Use BenchmarkAnalyticsService for bias analysis
            analytics_service = BenchmarkAnalyticsService()
            means_result = analytics_service.get_means(run_id, attribute)

            # Extract group means from rows
            rows = means_result.get("rows", [])
            group_means = {row["category"]: row["mean"] for row in rows}
            means_list = [row["mean"] for row in rows if row.get("mean") is not None]
            overall_mean = sum(means_list) / len(means_list) if means_list else None
            max_diff = max(means_list) - min(means_list) if len(means_list) > 1 else 0

            summary = {
                "run_id": run_id,
                "attribute": attribute,
                "groups": {row["category"]: row for row in rows},
                "overall_mean": overall_mean,
                "group_means": group_means,
                "max_diff": max_diff,
                "computed_at": _utcnow().isoformat(),
            }

            job.status = "completed"
            job.completed_at = _utcnow()
            job.duration_ms = int((time.time() - t0) * 1000)
            job.summary_json = json.dumps(summary)
            job.save()

            _LOG.info(
                f"[Analysis] Bias analysis ({attribute}) completed for run {run_id} "
                f"({job.duration_ms}ms)"
            )
            return job

        except Exception as e:
            job.status = "failed"
            job.completed_at = _utcnow()
            job.duration_ms = int((time.time() - t0) * 1000)
            job.error = str(e)
            job.save()
            _LOG.error(
                f"[Analysis] Bias analysis ({attribute}) failed for run {run_id}: {e}"
            )
            return job

    def run_export(self, run_id: int, export_format: str = "csv") -> AnalysisJob:
        """Export benchmark results.

        Called by the queue executor.

        Args:
            run_id: Benchmark run ID
            export_format: Export format ('csv' or 'json')

        Returns:
            Updated AnalysisJob record
        """
        db = get_db()
        t0 = time.time()
        params = {"format": export_format}
        params_hash = _hash_params(params)

        # Get or create job record
        job, created = AnalysisJob.get_or_create(
            run=run_id,
            analysis_type="export",
            params_hash=params_hash,
            defaults={
                "status": "running",
                "started_at": _utcnow(),
                "params_json": json.dumps(params),
            },
        )
        if not created:
            job.status = "running"
            job.started_at = _utcnow()
            job.error = None
            job.save()

        try:
            _LOG.info(f"[Analysis] Running export ({export_format}) for run {run_id}")

            # Export logic - for now just mark completed
            # The actual export file generation would go here
            # For CSV: write to temp file, store path in summary
            # For JSON: store data directly in summary

            summary = {
                "run_id": run_id,
                "format": export_format,
                "status": "ready",
                "computed_at": _utcnow().isoformat(),
            }

            job.status = "completed"
            job.completed_at = _utcnow()
            job.duration_ms = int((time.time() - t0) * 1000)
            job.summary_json = json.dumps(summary)
            job.save()

            _LOG.info(
                f"[Analysis] Export ({export_format}) completed for run {run_id} "
                f"({job.duration_ms}ms)"
            )
            return job

        except Exception as e:
            job.status = "failed"
            job.completed_at = _utcnow()
            job.duration_ms = int((time.time() - t0) * 1000)
            job.error = str(e)
            job.save()
            _LOG.error(f"[Analysis] Export failed for run {run_id}: {e}")
            return job


# Singleton instance
_analysis_service: Optional[AnalysisService] = None


def get_analysis_service() -> AnalysisService:
    """Get or create the analysis service singleton."""
    global _analysis_service
    if _analysis_service is None:
        _analysis_service = AnalysisService()
    return _analysis_service
