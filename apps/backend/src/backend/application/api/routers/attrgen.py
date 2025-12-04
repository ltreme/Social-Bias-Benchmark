"""Router for attribute generation endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from backend.application.services.attrgen_service import AttrGenService
from backend.domain.benchmarking.attr_gen_validator import AttrGenValidationError

from ..deps import db_session
from ..utils import ensure_db

router = APIRouter(tags=["attrgen"], dependencies=[Depends(db_session)])

# Service singleton (for single-process dev)
_service: AttrGenService | None = None


def get_service() -> AttrGenService:
    """Get or create the AttrGenService instance."""
    global _service
    if _service is None:
        _service = AttrGenService()
    return _service


@router.post("/attrgen/start")
def start_attr_generation(body: Dict[str, Any]) -> Dict[str, Any]:
    """Start attribute generation for a dataset in background.

    body: {
        dataset_id: int,
        model_name: str,
        llm?: 'hf'|'vllm'|'fake',
        batch_size?: int,
        max_new_tokens?: int,
        max_attempts?: int,
        system_prompt?: str,
        vllm_base_url?: str,
        resume_run_id?: int,
        skip_completed?: bool
    }
    """
    ensure_db()
    service = get_service()

    try:
        result = service.start_attr_generation(body)
        return {"ok": True, **result}
    except AttrGenValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Starten: {str(e)}")


@router.get("/attrgen/{run_id}/status")
def attrgen_status(run_id: int) -> Dict[str, Any]:
    """Get status of an attribute generation run."""
    ensure_db()
    service = get_service()

    try:
        status = service.get_run_status(run_id)
        return {"ok": True, **status}
    except Exception as e:
        return {"ok": True, "status": "unknown", "error": str(e)}


@router.get("/datasets/{dataset_id}/attrgen/latest")
def latest_attrgen_for_dataset(dataset_id: int) -> Dict[str, Any]:
    """Get the latest attribute generation run for a dataset."""
    ensure_db()
    service = get_service()

    try:
        result = service.get_latest_run(dataset_id)
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": True, "found": False, "error": str(e)}


@router.get("/datasets/{dataset_id}/attrgen/runs")
def list_attrgen_runs(dataset_id: int) -> Dict[str, Any]:
    """List all attribute generation runs for a dataset."""
    ensure_db()
    service = get_service()

    try:
        runs = service.list_runs(dataset_id)
        return {"ok": True, "runs": runs}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/attrgen/{run_id}")
def delete_attrgen_run(run_id: int) -> Dict[str, Any]:
    """Delete an attribute generation run if safe.

    Safety rules:
    - Run must not be currently queued or running
    - No benchmark runs that depend on this attrgen run may exist
    """
    ensure_db()
    service = get_service()

    try:
        result = service.delete_run(run_id)
        return {"ok": True, **result}
    except AttrGenValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Löschen: {str(e)}")
