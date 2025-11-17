from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from peewee import fn
from pydantic import BaseModel, conint

from backend.infrastructure.storage.models import BenchmarkResult, Trait

from ..utils import ensure_db

router = APIRouter(tags=["traits"])


class TraitOut(BaseModel):
    id: str
    adjective: str
    case_template: Optional[str] = None
    category: Optional[str] = None
    valence: Optional[conint(ge=-1, le=1)] = None
    is_active: bool = True
    linked_results_n: int = 0


class TraitIn(BaseModel):
    adjective: str
    case_template: Optional[str] = None
    category: Optional[str] = None
    valence: Optional[conint(ge=-1, le=1)] = None


class TraitActiveIn(BaseModel):
    is_active: bool


@router.get("/traits", response_model=List[TraitOut])
def list_traits() -> List[TraitOut]:
    ensure_db()
    out: List[TraitOut] = []
    # Pre-compute counts to show whether deletion is allowed
    counts: Dict[str, int] = {}
    for row in BenchmarkResult.select(
        BenchmarkResult.case_id, BenchmarkResult.id
    ).tuples():
        cid = str(row[0])
        counts[cid] = counts.get(cid, 0) + 1

    for c in Trait.select().order_by(Trait.id.asc()):
        out.append(
            TraitOut(
                id=str(c.id),
                adjective=str(c.adjective),
                case_template=(
                    str(c.case_template) if c.case_template is not None else None
                ),
                category=str(c.category) if c.category is not None else None,
                valence=int(c.valence) if c.valence is not None else None,
                is_active=bool(c.is_active),
                linked_results_n=int(counts.get(str(c.id), 0)),
            )
        )
    return out


def _next_generated_id() -> str:
    """Generate the next trait ID in the form g%d where %d increments the max present number."""
    pat = re.compile(r"^g(\d+)$")
    max_n = 0
    for c in Trait.select(Trait.id):
        m = pat.match(str(c.id))
        if m:
            try:
                n = int(m.group(1))
            except ValueError:
                continue
            if n > max_n:
                max_n = n
    return f"g{max_n + 1}"


def _normalize_adjective(value: str | None) -> str:
    return (value or "").strip()


def _adjective_exists(adjective: str, *, exclude_id: str | None = None) -> bool:
    norm = _normalize_adjective(adjective)
    if not norm:
        return False
    query = Trait.select().where(fn.LOWER(Trait.adjective) == norm.lower())
    if exclude_id is not None:
        query = query.where(Trait.id != exclude_id)
    return query.exists()


@router.post("/traits", response_model=TraitOut)
def create_trait(body: TraitIn) -> TraitOut:
    ensure_db()
    adjective = _normalize_adjective(body.adjective)
    if not adjective:
        raise HTTPException(status_code=422, detail="Adjektiv ist erforderlich")
    if _adjective_exists(adjective):
        raise HTTPException(status_code=400, detail="Adjektiv existiert bereits")
    # Generate a unique ID using the g%d scheme
    new_id = _next_generated_id()
    # Double-check uniqueness just in case
    if Trait.get_or_none(Trait.id == new_id) is not None:
        raise HTTPException(status_code=409, detail=f"Trait ID collision for {new_id}")
    c = Trait.create(
        id=new_id,
        adjective=adjective,
        case_template=body.case_template,
        category=body.category,
        valence=body.valence,
        is_active=True,
    )
    return TraitOut(
        id=str(c.id),
        adjective=str(c.adjective),
        case_template=c.case_template,
        category=c.category,
        valence=c.valence,
        is_active=bool(c.is_active),
        linked_results_n=0,
    )


@router.put("/traits/{trait_id}", response_model=TraitOut)
def update_trait(trait_id: str, body: TraitIn) -> TraitOut:
    ensure_db()
    c = Trait.get_or_none(Trait.id == trait_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Trait not found")
    adjective = _normalize_adjective(body.adjective)
    if not adjective:
        raise HTTPException(status_code=422, detail="Adjektiv ist erforderlich")
    if _adjective_exists(adjective, exclude_id=trait_id):
        raise HTTPException(status_code=400, detail="Adjektiv existiert bereits")
    c.adjective = adjective
    c.case_template = body.case_template
    c.category = body.category
    c.valence = body.valence
    c.save()
    linked = BenchmarkResult.select().where(BenchmarkResult.case_id == trait_id).count()
    return TraitOut(
        id=str(c.id),
        adjective=str(c.adjective),
        case_template=c.case_template,
        category=c.category,
        valence=c.valence,
        is_active=bool(c.is_active),
        linked_results_n=int(linked),
    )


@router.delete("/traits/{trait_id}")
def delete_trait(trait_id: str) -> Dict[str, Any]:
    ensure_db()
    c = Trait.get_or_none(Trait.id == trait_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Trait not found")
    linked = BenchmarkResult.select().where(BenchmarkResult.case_id == trait_id).count()
    if linked > 0:
        raise HTTPException(
            status_code=400,
            detail="Trait ist mit Benchmark-Resultaten verknüpft und kann nicht gelöscht werden",
        )
    c.delete_instance()  # RESTRICT also protects at DB level
    return {"ok": True}


@router.get("/traits/categories")
def list_trait_categories() -> Dict[str, List[str]]:
    ensure_db()
    categories: List[str] = []
    query = (
        Trait.select(Trait.category)
        .where((Trait.category.is_null(False)) & (Trait.category != ""))
        .distinct()
        .order_by(Trait.category.asc())
    )
    categories = [str(row.category) for row in query if row.category]
    return {"categories": categories}


@router.post("/traits/{trait_id}/active", response_model=TraitOut)
def set_trait_active(trait_id: str, body: TraitActiveIn) -> TraitOut:
    ensure_db()
    trait = Trait.get_or_none(Trait.id == trait_id)
    if trait is None:
        raise HTTPException(status_code=404, detail="Trait not found")
    trait.is_active = bool(body.is_active)
    trait.save()
    linked = BenchmarkResult.select().where(BenchmarkResult.case_id == trait_id).count()
    return TraitOut(
        id=str(trait.id),
        adjective=str(trait.adjective),
        case_template=trait.case_template,
        category=trait.category,
        valence=trait.valence,
        is_active=bool(trait.is_active),
        linked_results_n=int(linked),
    )
