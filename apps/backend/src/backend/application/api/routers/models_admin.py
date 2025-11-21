from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.infrastructure.storage.models import Model

from ..deps import db_session
from ..utils import ensure_db

router = APIRouter(tags=["models-admin"], dependencies=[Depends(db_session)])


class ModelOut(BaseModel):
    id: int
    name: str
    min_vram: Optional[int] = None
    vllm_serve_cmd: Optional[str] = None
    created_at: Optional[str] = None


@router.get("/admin/models", response_model=List[ModelOut])
def list_models_admin() -> List[ModelOut]:
    ensure_db()
    out: List[ModelOut] = []
    for m in Model.select().order_by(Model.id.desc()):
        out.append(
            ModelOut(
                id=int(m.id),
                name=str(m.name),
                min_vram=m.min_vram,
                vllm_serve_cmd=m.vllm_serve_cmd,
                created_at=str(m.created_at) if m.created_at else None,
            )
        )
    return out


class ModelIn(BaseModel):
    name: str
    min_vram: Optional[int] = None
    vllm_serve_cmd: Optional[str] = None


@router.post("/admin/models", response_model=ModelOut)
def create_model(body: ModelIn) -> ModelOut:
    ensure_db()
    m, _ = Model.get_or_create(name=body.name)
    if body.min_vram is not None:
        m.min_vram = int(body.min_vram)
    if body.vllm_serve_cmd is not None:
        m.vllm_serve_cmd = str(body.vllm_serve_cmd)
    m.save()
    return ModelOut(
        id=int(m.id),
        name=str(m.name),
        min_vram=m.min_vram,
        vllm_serve_cmd=m.vllm_serve_cmd,
        created_at=str(m.created_at) if m.created_at else None,
    )


class ModelUpdate(BaseModel):
    name: Optional[str] = None
    min_vram: Optional[int] = None
    vllm_serve_cmd: Optional[str] = None


@router.put("/admin/models/{model_id}", response_model=ModelOut)
def update_model(model_id: int, body: ModelUpdate) -> ModelOut:
    ensure_db()
    m = Model.get_or_none(Model.id == int(model_id))
    if not m:
        # create if not exists
        m = Model.create(id=int(model_id), name=body.name or f"model-{model_id}")
    if body.name is not None:
        m.name = str(body.name)
    if body.min_vram is not None:
        m.min_vram = int(body.min_vram)
    if body.vllm_serve_cmd is not None:
        m.vllm_serve_cmd = str(body.vllm_serve_cmd)
    m.save()
    return ModelOut(
        id=int(m.id),
        name=str(m.name),
        min_vram=m.min_vram,
        vllm_serve_cmd=m.vllm_serve_cmd,
        created_at=str(m.created_at) if m.created_at else None,
    )


@router.delete("/admin/models/{model_id}")
def delete_model(model_id: int) -> Dict[str, Any]:
    ensure_db()
    try:
        deleted = Model.delete().where(Model.id == int(model_id)).execute()
        return {"ok": True, "deleted": int(deleted)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
