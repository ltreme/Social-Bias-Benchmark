from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional
import os
from urllib.parse import urlparse, urlunparse
import requests

from fastapi import APIRouter, HTTPException

from ..utils import ensure_db
from shared.storage.models import AttrGenerationRun, Model, DatasetPersona, AdditionalPersonaAttributes, BenchmarkRun
import peewee as pw

from benchmark.pipeline.attr_gen import run_attr_gen_pipeline
from benchmark.repository.persona_repository import PersonaRepositoryByDataset
from benchmark.pipeline.adapters.prompting import AttributePromptFactory
from benchmark.pipeline.adapters.postprocess.postprocessor_attr import AttributePostProcessor
from benchmark.pipeline.adapters.persister_sqlite import PersisterPeewee
from benchmark.pipeline.adapters.llm import LlmClientFake, LlmClientVLLM

router = APIRouter(tags=["attrgen"])

# In-memory job progress (single-process dev). For multi-process, replace with Redis.
PROGRESS: Dict[int, Dict[str, Any]] = {}

def _progress_poller(run_id: int, dataset_id: int) -> None:
    try:
        while PROGRESS.get(run_id, {}).get("status") in {"queued", "running"}:
            _update_progress_done(run_id, dataset_id)
            time.sleep(2.0)
    except Exception:
        pass


REQUIRED_KEYS = ("name", "appearance", "biography")

def _normalize_base_url(url: Optional[str]) -> str:
    base = (url or os.getenv('VLLM_BASE_URL') or 'http://localhost:8000').strip()
    try:
        p = urlparse(base)
        host = (p.hostname or '').lower()
        if host in {"localhost", "127.0.0.1"}:
            # Inside a container, talk to the host via host.docker.internal
            # Keep port/protocol as provided
            p = p._replace(netloc=f"host.docker.internal:{p.port or 80}")
            return urlunparse(p)
    except Exception:
        pass
    return base

def _probe_vllm_models(base_url: str, timeout: float = 2.5) -> Dict[str, Any]:
    """Call vLLM /v1/models to verify availability. Returns JSON on success.
    Raises a requests.RequestException (or ValueError) on failure.
    """
    u = base_url.rstrip('/') + '/v1/models'
    r = requests.get(u, timeout=timeout, headers={'accept': 'application/json'})
    r.raise_for_status()
    try:
        return r.json()
    except Exception as e:
        raise ValueError(f"Ungültige vLLM-Antwort von {u}: {e}")

def _select_vllm_base_for(model_name: str, preferred: Optional[str]) -> str:
    """Try several base URLs and return the first that answers and (if possible) contains the model.

    Candidates order: preferred, normalized(preferred), env VLLM_BASE_URL, normalized(env),
    http://host.docker.internal:8000, http://localhost:8000
    """
    tried: list[tuple[str, str]] = []
    cands = []
    if preferred:
        cands.append(preferred)
        cands.append(_normalize_base_url(preferred))
    env_base = os.getenv('VLLM_BASE_URL')
    if env_base:
        cands.append(env_base)
        cands.append(_normalize_base_url(env_base))
    cands.append('http://host.docker.internal:8000')
    cands.append('http://localhost:8000')
    seen = set()
    for c in cands:
        if not c or c in seen:
            continue
        seen.add(c)
        try:
            data = _probe_vllm_models(c)
            # If models are listed, try to ensure the model exists; otherwise accept the base.
            ids = [str(m.get('id')) for m in (data.get('data') or []) if isinstance(m, dict)]
            if not ids or model_name in ids:
                return c
            tried.append((c, f"Modell '{model_name}' nicht gelistet"))
        except Exception as e:
            tried.append((c, str(e)))
    # Nothing worked
    detail = "; ".join([f"{u}: {err}" for u, err in tried]) or "keine Kandidaten"
    raise RuntimeError(f"vLLM nicht erreichbar oder Modell fehlt – versucht: {detail}")

def _update_progress_done(run_id: int, dataset_id: int) -> None:
    # Derive done personas = have all required attributes for this run
    sub = (AdditionalPersonaAttributes
        .select(AdditionalPersonaAttributes.persona_uuid_id,
                pw.fn.COUNT(AdditionalPersonaAttributes.id).alias('c'))
        .where(
            (AdditionalPersonaAttributes.attr_generation_run_id == run_id) &
            (AdditionalPersonaAttributes.attribute_key.in_(REQUIRED_KEYS))
        )
        .group_by(AdditionalPersonaAttributes.persona_uuid_id)
        .having(pw.fn.COUNT(AdditionalPersonaAttributes.id) >= len(REQUIRED_KEYS)))
    done = sub.count()
    total = DatasetPersona.select().where(DatasetPersona.dataset_id == dataset_id).count()
    PROGRESS.setdefault(run_id, {})
    PROGRESS[run_id].update({"total": total, "done": done, "pct": (100.0*done/total) if total else 0.0})


def _incomplete_uuid_set(run_id: int, dataset_id: int) -> set[str]:
    # Personas in dataset that are missing at least one required attribute for this run
    q = (DatasetPersona
        .select(DatasetPersona.persona_id.alias('pid'), pw.fn.COUNT(AdditionalPersonaAttributes.id).alias('c'))
        .join(AdditionalPersonaAttributes, pw.JOIN.LEFT_OUTER, on=((AdditionalPersonaAttributes.persona_uuid_id == DatasetPersona.persona_id) &
            (AdditionalPersonaAttributes.attr_generation_run_id == run_id) &
            (AdditionalPersonaAttributes.attribute_key.in_(REQUIRED_KEYS))))
        .where(DatasetPersona.dataset_id == dataset_id)
        .group_by(DatasetPersona.persona_id)
        .having(pw.fn.COUNT(AdditionalPersonaAttributes.id) < len(REQUIRED_KEYS)))
    return {str(r.pid) for r in q}


def _run_attrgen_background(run_id: int) -> None:
    rec = AttrGenerationRun.get_by_id(run_id)
    dataset_id = int(rec.dataset_id.id) if rec.dataset_id else None
    model_name = str(rec.model_id.name)

    # Instantiate components
    persona_repo = PersonaRepositoryByDataset(dataset_id=dataset_id)
    prompt_factory = AttributePromptFactory(max_new_tokens=int(rec.max_new_tokens or 160), system_preamble=rec.system_prompt)
    post = AttributePostProcessor()

    # Choose LLM backend: prefer vLLM if model looks like served; fallback HF; allow 'fake' via model name prefix
    llm_backend = PROGRESS.get(run_id, {}).get("llm")
    batch_size = int(rec.batch_size or 2)
    if llm_backend == "fake":
        llm = LlmClientFake(batch_size=batch_size)
    else:
        try:
            sel = _select_vllm_base_for(model_name, PROGRESS.get(run_id, {}).get("vllm_base_url"))
        except Exception as e:
            PROGRESS[run_id] = {**PROGRESS.get(run_id, {}), "status": "failed", "error": str(e)}
            return
        llm = LlmClientVLLM(base_url=str(sel), model=model_name, api_key=None, batch_size=batch_size, max_new_tokens_cap=int(rec.max_new_tokens or 192))

    persist = PersisterPeewee()

    PROGRESS[run_id] = {**PROGRESS.get(run_id, {}), "status": "running", "done": 0, "total": 0, "pct": 0.0}
    try:
        # Optional: skip personas that are already complete for this run
        skip_completed = bool(PROGRESS.get(run_id, {}).get("skip_completed", False))
        if skip_completed and dataset_id is not None:
            allow = _incomplete_uuid_set(run_id, dataset_id)
            class _FilterRepo:
                def __init__(self, base, allowed: set[str]):
                    self.base = base
                    self.allowed = allowed
                def iter_personas(self, ds_id: int):
                    for w in self.base.iter_personas(ds_id):
                        if str(w.persona_uuid) in self.allowed:
                            yield w
            persona_repo = _FilterRepo(persona_repo, allow)

        run_attr_gen_pipeline(
            dataset_id=dataset_id,
            persona_repo=persona_repo,
            prompt_factory=prompt_factory,
            llm=llm,
            post=post,
            persist=persist,
            model_name=model_name,
            max_attempts=int(rec.max_attempts or 3),
            persist_buffer_size=256,
            total_personas_override=None,
            attr_generation_run_id=run_id,
        )
        _update_progress_done(run_id, dataset_id)
        PROGRESS[run_id]["status"] = "done"
    except Exception as e:
        PROGRESS[run_id]["status"] = "failed"
        PROGRESS[run_id]["error"] = str(e)


@router.post("/attrgen/start")
def start_attr_generation(body: Dict[str, Any]) -> Dict[str, Any]:
    """Start attribute generation for a dataset in background.

    body: { dataset_id:int, model_name:str, llm?: 'hf'|'vllm'|'fake', batch_size?:int, max_new_tokens?:int, max_attempts?:int, system_prompt?:str, vllm_base_url?:str }
    """
    ensure_db()
    dataset_id = int(body["dataset_id"])
    model_name = str(body["model_name"])  # HF or vLLM served name
    batch_size = int(body.get("batch_size", 2))
    max_new_tokens = int(body.get("max_new_tokens", 192))
    max_attempts = int(body.get("max_attempts", 3))
    system_prompt = body.get("system_prompt")
    llm = body.get("llm", "hf")
    vllm_base_url = body.get("vllm_base_url")

    resume_run_id = body.get("resume_run_id")
    skip_completed = bool(body.get("skip_completed", bool(resume_run_id)))
    if resume_run_id is not None:
        rec = AttrGenerationRun.get_by_id(int(resume_run_id))
        if int(rec.dataset_id.id) != dataset_id:
            raise ValueError("resume_run_id gehört zu einem anderen Dataset")
        # Update runtime params if provided
        rec.batch_size = batch_size
        rec.max_new_tokens = max_new_tokens
        rec.max_attempts = max_attempts
        rec.system_prompt = system_prompt
        rec.save()
    else:
        model_entry, _ = Model.get_or_create(name=model_name)
        rec = AttrGenerationRun.create(
            dataset_id=dataset_id,
            model_id=model_entry.id,
            batch_size=batch_size,
            max_new_tokens=max_new_tokens,
            max_attempts=max_attempts,
            system_prompt=system_prompt,
        )
    PROGRESS[rec.id] = {"status": "queued", "llm": llm, "vllm_base_url": vllm_base_url, "skip_completed": skip_completed}

    # Start pipeline thread
    t_pipe = threading.Thread(target=_run_attrgen_background, args=(int(rec.id),), daemon=True)
    t_pipe.start()
    # Start progress polling thread (does not block DB writes)
    t_poll = threading.Thread(target=_progress_poller, args=(int(rec.id), int(dataset_id)), daemon=True)
    t_poll.start()
    return {"ok": True, "run_id": int(rec.id)}


@router.get("/attrgen/{run_id}/status")
def attrgen_status(run_id: int) -> Dict[str, Any]:
    ensure_db()
    info = PROGRESS.get(run_id)
    if not info:
        # maybe process restarted; compute from DB
        try:
            rec = AttrGenerationRun.get_by_id(run_id)
            ds_id = int(rec.dataset_id.id) if rec.dataset_id else None
            if ds_id is not None:
                _update_progress_done(run_id, ds_id)
                info = PROGRESS.get(run_id)
        except Exception:
            info = {"status": "unknown"}
    return {"ok": True, **(info or {})}


@router.get("/datasets/{dataset_id}/attrgen/latest")
def latest_attrgen_for_dataset(dataset_id: int) -> Dict[str, Any]:
    ensure_db()
    try:
        rec = (AttrGenerationRun
            .select()
            .where(AttrGenerationRun.dataset_id == dataset_id)
            .order_by(AttrGenerationRun.id.desc())
            .first())
        if not rec:
            return {"ok": True, "found": False}
        rid = int(rec.id)
        ds_id = int(dataset_id)
        _update_progress_done(rid, ds_id)
        info = PROGRESS.get(rid, {})
        status = info.get("status") or "unknown"
        return {"ok": True, "found": True, "run_id": rid, "status": status, "done": info.get("done", 0), "total": info.get("total", 0), "pct": info.get("pct", 0.0), "error": info.get("error")}
    except Exception:
        return {"ok": True, "found": False}


@router.get("/datasets/{dataset_id}/attrgen/runs")
def list_attrgen_runs(dataset_id: int) -> Dict[str, Any]:
    ensure_db()
    rows = (AttrGenerationRun
            .select()
            .where(AttrGenerationRun.dataset_id == dataset_id)
            .order_by(AttrGenerationRun.id.desc())
            .limit(25))
    out = []
    for r in rows:
        rid = int(r.id)
        _update_progress_done(rid, dataset_id)
        info = PROGRESS.get(rid, {})
        out.append({
            "id": rid,
            "created_at": str(r.created_at),
            "batch_size": int(r.batch_size or 0),
            "max_new_tokens": int(r.max_new_tokens or 0),
            "max_attempts": int(r.max_attempts or 0),
            "system_prompt": r.system_prompt,
            "model_name": r.model_id.name if r.model_id else None,
            "status": info.get("status", "unknown"),
            "done": info.get("done", 0),
            "total": info.get("total", 0),
            "pct": info.get("pct", 0.0),
            "error": info.get("error"),
        })
    return {"ok": True, "runs": out}


@router.delete("/attrgen/{run_id}")
def delete_attrgen_run(run_id: int) -> Dict[str, Any]:
    """Delete an attribute-generation run if safe.

    Safety rules:
    - If the run is currently queued/running, block deletion.
    - If there exists a benchmark run for the same dataset and model that was
      created at or after this attrgen run, block deletion (likely dependent).
    Otherwise, delete all AdditionalPersonaAttributes for this run and the run itself.
    """
    ensure_db()
    try:
        rec = AttrGenerationRun.get_by_id(int(run_id))
    except Exception:
        raise HTTPException(status_code=404, detail="AttrGen-Run nicht gefunden")

    # In-memory job protection
    state = PROGRESS.get(int(run_id), {}).get("status")
    if state in {"queued", "running"}:
        raise HTTPException(status_code=400, detail="Run läuft noch oder ist in der Warteschlange – Löschen nicht möglich")

    # Heuristik: block if a benchmark for same dataset+model exists at/after run time
    try:
        ds_id = int(rec.dataset_id.id) if rec.dataset_id else None
        model_id = int(rec.model_id.id) if rec.model_id else None
        if ds_id is not None and model_id is not None:
            conflict = (BenchmarkRun
                        .select()
                        .where(
                            (BenchmarkRun.dataset_id == ds_id) &
                            (BenchmarkRun.model_id == model_id) &
                            (BenchmarkRun.created_at >= rec.created_at)
                        )
                        .limit(1)
                        .exists())
            if conflict:
                raise HTTPException(status_code=400, detail="Es existieren Benchmarks für dieses Dataset/Modell nach diesem Attr-Run – Löschen gesperrt")
    except HTTPException:
        raise
    except Exception:
        # On any unexpected error during the check, fail safe and do not delete
        raise HTTPException(status_code=400, detail="Konnte Abhängigkeiten nicht prüfen – Löschen abgebrochen")

    # Delete attributes for this run, then the run itself
    deleted_attrs = (AdditionalPersonaAttributes
                     .delete()
                     .where(AdditionalPersonaAttributes.attr_generation_run_id == int(run_id))
                     .execute())
    rec.delete_instance()
    # Best-effort: cleanup any progress entry
    PROGRESS.pop(int(run_id), None)
    return {"ok": True, "deleted_attributes": int(deleted_attrs)}
