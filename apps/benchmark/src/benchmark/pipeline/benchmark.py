from __future__ import annotations
from typing import Iterable, List, Optional, Tuple
import hashlib
import os, time

from .ports_bench import (
    BenchPersonaRepo,
    BenchPromptFactory,
    LLMClient,
    BenchPostProcessor,
    BenchPersister,
    BenchWorkItem,
    BenchPromptSpec,
    LLMResult,
    BenchAnswerDto,
)
from .ports import FailureDto  # reuse same FailureDto schema


_SNIP = 300


def _snippet(s: Optional[str], n: int = _SNIP) -> str:
    return s[:n] if s else ""


def _persist_fail(persist: BenchPersister, spec: BenchPromptSpec, kind: str, raw: str, reason: Optional[str] = None) -> None:
    persist.persist_failure(
        FailureDto(
            persona_uuid=spec.work.persona_uuid,
            model_name=spec.model_name,
            attempt=spec.attempt,
            error_kind=reason or kind,
            raw_text_snippet=_snippet(raw),
            prompt_snippet=_snippet(spec.prompt_text),
        )
    )


def run_benchmark_pipeline(
    *,
    dataset_id: int | None,
    question_repo,
    persona_repo: BenchPersonaRepo,
    prompt_factory: BenchPromptFactory,
    llm: LLMClient,
    post: BenchPostProcessor,
    persist: BenchPersister,
    model_name: str,
    template_version: str = "v1",
    benchmark_run_id: int,
    max_attempts: int = 3,
    persona_count_override: int | None = None,
    skip_completed_run_id: int | None = None,
    scale_mode: str | None = None,
    dual_fraction: float | None = None,
) -> None:
    """Primary benchmark pipeline.

    - Materializes the small set of questions once (≈30), keeping personas streamed.
    - Cross-joins lazily: for each persona, iterate over questions to yield work items.
    - Batches via the LLM client and persists in chunks.
    """

    # 1) Load cases once (small and stable)
    cases = list(question_repo.iter_all())
    # Persona count for total work estimation
    if persona_count_override is not None:
        persona_count = int(persona_count_override)
    else:
        try:
            if dataset_id is not None:
                from shared.storage.models import DatasetPersona
                persona_count = DatasetPersona.select().where(DatasetPersona.dataset_id == dataset_id).count()
            else:
                from shared.storage.models import Persona
                persona_count = Persona.select().count()
        except Exception:
            persona_count = 0
    total_items = persona_count * len(cases) if cases else 0
    # Determine progress frequency based on batch size with sensible defaults.
    def _compute_progress_every(batch_size: int | None, env_var: str, baseline: int = 10) -> int:
        # Allow explicit override via env var
        env_val = os.getenv(env_var)
        if env_val is not None:
            try:
                return max(1, int(env_val))
            except Exception:
                pass
        # Fallback: derive from batch size
        if not batch_size or batch_size <= 0:
            return baseline
        if batch_size >= baseline:
            return batch_size
        # Choose the multiple of batch_size closest to baseline; ties choose smaller
        # Using bankers rounding achieves the tie-break toward smaller for x.5
        k = max(1, round(baseline / batch_size))
        return max(1, batch_size * k)

    progress_every = _compute_progress_every(getattr(llm, "batch_size", None), "BENCH_PROGRESS_EVERY", 10)
    progress_log = os.getenv("BENCH_PROGRESS_LOG", "").lower() in ("1","true","yes")
    done_items: set[Tuple[str, str]] = set()  # (persona_uuid, case_id)
    t0 = time.perf_counter()

    def _fmt_dur(seconds: float) -> str:
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h{m:02d}m{s:02d}s"
        if m:
            return f"{m}m{s:02d}s"
        return f"{s}s"

    # Preload completed keys for skipping if requested
    completed_keys: set[tuple[str, str, str]] = set()
    if skip_completed_run_id is not None:
        try:
            from shared.storage.models import BenchmarkResult
            q = (BenchmarkResult
                 .select(BenchmarkResult.persona_uuid_id, BenchmarkResult.case_id, BenchmarkResult.scale_order)
                 .where(BenchmarkResult.benchmark_run_id == int(skip_completed_run_id)))
            completed_keys = {(str(r.persona_uuid_id), str(r.case_id), str(r.scale_order or 'in')) for r in q}
        except Exception:
            completed_keys = set()

    def _decide_reversed(persona_uuid: str, case_id: str) -> bool:
        # Decide based on run-level setting in _BENCH_PROGRESS via environment
        mode = scale_mode
        if mode == 'rev':
            return True
        if mode == 'in':
            return False
        if mode == 'random50':
            h = hashlib.md5(f"{benchmark_run_id}:{persona_uuid}:{case_id}".encode('utf-8')).digest()
            return (h[0] % 2) == 0
        return False

    def iter_items() -> Iterable[BenchWorkItem]:
        for p in persona_repo.iter_personas(dataset_id):
            for c in cases:
                persona_s = str(p.persona_uuid)
                case_s = str(c.id)
                scale_rev = _decide_reversed(persona_s, case_s)
                # Decide duplication
                def _hash01(a: str) -> float:
                    h = hashlib.md5(a.encode('utf-8')).digest()
                    return int.from_bytes(h, 'big') / (2**128)
                dup = False
                if isinstance(dual_fraction, (int, float)) and dual_fraction and dual_fraction > 0:
                    dup = (_hash01(f"dup:{benchmark_run_id}:{persona_s}:{case_s}") < float(dual_fraction))

                # Primary direction
                if not (completed_keys and (persona_s, case_s, 'rev' if scale_rev else 'in') in completed_keys):
                    yield BenchWorkItem(
                        dataset_id=p.dataset_id,
                        persona_uuid=p.persona_uuid,
                        persona_context=p.persona_context,
                        case_id=c.id,
                        adjective=c.adjective,
                        case_template=c.case_template,
                        scale_reversed=scale_rev,
                    )
                # Opposite direction for duplicated subset
                if dup:
                    opp_rev = not scale_rev
                    if not (completed_keys and (persona_s, case_s, 'rev' if opp_rev else 'in') in completed_keys):
                        yield BenchWorkItem(
                            dataset_id=p.dataset_id,
                            persona_uuid=p.persona_uuid,
                            persona_context=p.persona_context,
                            case_id=c.id,
                            adjective=c.adjective,
                            case_template=c.case_template,
                            scale_reversed=opp_rev,
                        )

    attempt = 1
    base_items: Iterable[BenchWorkItem] = iter_items()
    pending_specs: Iterable[BenchPromptSpec] = prompt_factory.prompts(
        base_items,
        model_name=model_name,
        template_version=template_version,
        attempt=attempt,
        benchmark_run_id=benchmark_run_id,
    )

    # Note: We intentionally do NOT buffer persistence anymore. LLM batching remains.

    debug = os.getenv("BENCH_DEBUG", "").lower() in ("1", "true", "yes")
    while attempt <= max_attempts:
        results: Iterable[LLMResult] = llm.run_stream(pending_specs)
        next_retry_specs: List[BenchPromptSpec] = []
        ok_cnt = retry_cnt = fail_cnt = 0

        for res in results:
            spec = res.spec  # BenchPromptSpec
            decision = post.decide(res)

            if decision.kind == "ok":
                if not decision.answers:
                    _persist_fail(persist, spec, "ok_without_answer", res.raw_text)
                    continue
                # Persist immediately (no buffering in persister phase)
                persist.persist_results(decision.answers)
                if debug:
                    try:
                        a = decision.answers[0]
                        print(f"[BenchmarkPipeline] OK -> persisted persona={a.persona_uuid} case={a.case_id} rating={a.rating}")
                    except Exception:
                        pass
                ok_cnt += 1
                # Mark as finished for progress (first answer defines the (persona,question))
                try:
                    a0 = decision.answers[0]
                    key = (str(a0.persona_uuid), str(a0.case_id))
                    if key not in done_items:
                        done_items.add(key)
                        if progress_log and ((len(done_items) % progress_every == 0) or (total_items and len(done_items) == total_items)):
                            pct = 100.0 * len(done_items) / total_items if total_items else 0.0
                            elapsed = _fmt_dur(time.perf_counter() - t0)
                            print(f"[Benchmark] progress: {len(done_items)}/{total_items or '?'} items ({pct:.1f}%), elapsed={elapsed}")
                except Exception:
                    pass

            elif decision.kind == "retry":
                next_retry_specs.append(decision.retry_spec)
                retry_cnt += 1

            elif decision.kind == "fail":
                _persist_fail(persist, spec, decision.reason, decision.raw_text_snippet)
                fail_cnt += 1

            else:
                _persist_fail(persist, spec, "unknown_decision", res.raw_text)

        if debug:
            try:
                print(f"[BenchmarkPipeline] attempt={attempt} decisions ok={ok_cnt} retry={retry_cnt} fail={fail_cnt}")
            except Exception:
                pass

        if not next_retry_specs:
            break

        attempt += 1
        if attempt > max_attempts:
            for spec in next_retry_specs:
                _persist_fail(persist, spec, "max_attempts_exceeded", raw="")
                # Count permanently failed as finished progress items
                key = (str(spec.work.persona_uuid), str(spec.work.case_id))
                if key not in done_items:
                    done_items.add(key)
            if progress_log and done_items:
                pct = 100.0 * len(done_items) / total_items if total_items else 0.0
                elapsed = _fmt_dur(time.perf_counter() - t0)
                print(f"[Benchmark] progress: {len(done_items)}/{total_items or '?'} items ({pct:.1f}%), elapsed={elapsed}")
            break

        pending_specs = iter(next_retry_specs)
