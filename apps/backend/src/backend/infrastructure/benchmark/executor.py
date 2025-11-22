"""Benchmark execution logic."""

from __future__ import annotations

import logging
import os
import traceback
from typing import Callable
from urllib.parse import urlparse, urlunparse

import requests

from backend.domain.benchmarking.adapters.postprocess.postprocessor_likert import (
    LikertPostProcessor,
)
from backend.domain.benchmarking.adapters.prompting import LikertPromptFactory
from backend.domain.benchmarking.benchmark import (
    BenchmarkCancelledError,
    run_benchmark_pipeline,
)
from backend.infrastructure.benchmark.persister_bench_sqlite import BenchPersisterPeewee
from backend.infrastructure.benchmark.repository.persona_repository import (
    FullPersonaRepositoryByDataset,
)
from backend.infrastructure.benchmark.repository.trait import TraitRepository
from backend.infrastructure.llm import LlmClientFakeBench, LlmClientVLLMBench
from backend.infrastructure.storage.models import BenchmarkRun

_LOG = logging.getLogger(__name__)


def execute_benchmark_run(
    run_id: int,
    progress_setter: Callable,
    progress_getter: Callable,
    progress_updater: Callable,
    completed_keys_getter: Callable,
) -> None:
    """Execute a benchmark run in the background.

    Args:
        run_id: The benchmark run ID
        progress_setter: Function to set progress state
        progress_getter: Function to get current progress
        progress_updater: Function to update progress from DB
        completed_keys_getter: Function to get already completed keys
    """
    rec = BenchmarkRun.get_by_id(run_id)
    ds_id = int(rec.dataset_id.id)
    model_name = str(rec.model_id.name)
    include_rationale = bool(rec.include_rationale)

    if progress_getter(run_id).get("cancel_requested"):
        progress_setter(
            run_id,
            {
                **progress_getter(run_id),
                "status": "cancelled",
                "error": "Benchmark wurde abgebrochen",
            },
        )
        return

    scale_mode = getattr(rec, "scale_mode", None) or progress_getter(run_id).get(
        "scale_mode"
    )
    dual_fraction = getattr(rec, "dual_fraction", None) or progress_getter(run_id).get(
        "dual_fraction"
    )

    attrgen_run_id = progress_getter(run_id).get("attrgen_run_id")
    persona_repo = FullPersonaRepositoryByDataset(
        dataset_id=ds_id, model_name=model_name, attr_generation_run_id=attrgen_run_id
    )
    trait_repo = TraitRepository()
    max_new_toks = int(progress_getter(run_id).get("max_new_tokens", 256))
    system_prompt = rec.system_prompt
    prompt_factory = LikertPromptFactory(
        include_rationale=include_rationale,
        max_new_tokens=max_new_toks,
        system_preamble=system_prompt,
    )
    post = LikertPostProcessor()
    backend = progress_getter(run_id).get("llm") or "vllm"
    batch_size = int(progress_getter(run_id).get("batch_size") or (rec.batch_size or 2))

    if backend == "fake":
        llm = LlmClientFakeBench(batch_size=batch_size)
    else:
        llm = _create_vllm_client(
            run_id,
            model_name,
            batch_size,
            max_new_toks,
            progress_getter,
            progress_setter,
        )
        if llm is None:
            return

    persist = BenchPersisterPeewee()
    progress_setter(
        run_id,
        {
            **progress_getter(run_id),
            "status": "running",
            "cancel_requested": progress_getter(run_id).get("cancel_requested", False),
        },
    )

    def _cancel_check() -> bool:
        return bool(progress_getter(run_id).get("cancel_requested"))

    try:
        skip_completed = bool(progress_getter(run_id).get("skip_completed", False))
        completed_keys = completed_keys_getter(run_id) if skip_completed else None
        persona_count = persona_repo.count(ds_id)
        run_benchmark_pipeline(
            dataset_id=ds_id,
            trait_repo=trait_repo,
            persona_repo=persona_repo,
            prompt_factory=prompt_factory,
            llm=llm,
            post=post,
            persist=persist,
            model_name=model_name,
            benchmark_run_id=run_id,
            max_attempts=3,
            skip_completed_run_id=run_id if skip_completed else None,
            scale_mode=scale_mode,
            dual_fraction=(
                float(dual_fraction)
                if isinstance(dual_fraction, (int, float))
                else None
            ),
            persona_count_override=persona_count,
            completed_keys=completed_keys,
            cancel_check=_cancel_check,
        )
        progress_updater(run_id, ds_id)
        info = progress_getter(run_id)
        try:
            done = int(info.get("done") or 0)
            total = int(info.get("total") or 0)
        except Exception:
            done = 0
            total = 0
        status = "done" if (total == 0 or done >= total) else "partial"
        progress_setter(run_id, {**info, "status": status})
    except BenchmarkCancelledError:
        progress_setter(
            run_id,
            {
                **progress_getter(run_id),
                "status": "cancelled",
                "error": "Benchmark wurde abgebrochen",
            },
        )
    except Exception as e:
        progress_setter(
            run_id,
            {**progress_getter(run_id), "status": "failed", "error": str(e)},
        )
        try:
            print(f"[bench_run_background] run_id={run_id} failed: {e}")
            traceback.print_exc()
        except Exception:
            pass


def _create_vllm_client(
    run_id: int,
    model_name: str,
    batch_size: int,
    max_new_toks: int,
    progress_getter: Callable,
    progress_setter: Callable,
):
    """Create vLLM client with automatic base URL discovery."""

    def _probe_models(u: str) -> dict:
        r = requests.get(
            u.rstrip("/") + "/v1/models",
            timeout=2.5,
            headers={"accept": "application/json"},
        )
        r.raise_for_status()
        return r.json()

    base_pref = (
        progress_getter(run_id).get("vllm_base_url")
        or os.getenv("VLLM_BASE_URL")
        or "http://localhost:8000"
    )

    # Build candidates
    cands = []

    def _norm(url: str) -> str:
        try:
            p = urlparse(url)
            host = (p.hostname or "").lower()
            if host in {"localhost", "127.0.0.1"}:
                p = p._replace(netloc=f"host.docker.internal:{p.port or 80}")
                return urlunparse(p)
        except Exception:
            pass
        return url

    if base_pref:
        cands += [base_pref, _norm(base_pref)]
    envb = os.getenv("VLLM_BASE_URL")
    if envb:
        cands += [envb, _norm(envb)]
    cands += ["http://host.docker.internal:8000", "http://localhost:8000"]

    tried = []
    base = None
    for u in [x for i, x in enumerate(cands) if x and x not in cands[:i]]:
        try:
            data = _probe_models(u)
            ids = [
                str(m.get("id"))
                for m in (data.get("data") or [])
                if isinstance(m, dict)
            ]
            if not ids or model_name in ids:
                base = u
                break
            tried.append((u, f"Modell '{model_name}' nicht gelistet"))
        except Exception as e:
            tried.append((u, str(e)))

    if base is None:
        progress_setter(
            run_id,
            {
                **progress_getter(run_id),
                "status": "failed",
                "error": f"vLLM nicht erreichbar oder Modell fehlt – versucht: {'; '.join([f'{u}: {err}' for u,err in tried])}",
            },
        )
        return None

    api_key = progress_getter(run_id).get("vllm_api_key") or os.getenv("VLLM_API_KEY")
    return LlmClientVLLMBench(
        base_url=str(base),
        model=model_name,
        api_key=api_key,
        batch_size=batch_size,
        max_new_tokens_cap=max_new_toks,
    )
