from __future__ import annotations

from typing import List, Optional, Dict, Any
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..utils import ensure_db
from shared.storage.models import Case, BenchmarkResult


router = APIRouter(tags=["cases"])


class CaseOut(BaseModel):
    id: str
    adjective: str
    case_template: Optional[str] = None
    linked_results_n: int = 0


class CaseIn(BaseModel):
    adjective: str
    case_template: Optional[str] = None


@router.get("/cases", response_model=List[CaseOut])
def list_cases() -> List[CaseOut]:
    ensure_db()
    out: List[CaseOut] = []
    # Pre-compute counts to show whether deletion is allowed
    counts: Dict[str, int] = {}
    for row in (
        BenchmarkResult
        .select(BenchmarkResult.case_id, BenchmarkResult.id)
        .tuples()
    ):
        cid = str(row[0])
        counts[cid] = counts.get(cid, 0) + 1

    for c in Case.select().order_by(Case.id.asc()):
        out.append(CaseOut(
            id=str(c.id),
            adjective=str(c.adjective),
            case_template=str(c.case_template) if c.case_template is not None else None,
            linked_results_n=int(counts.get(str(c.id), 0)),
        ))
    return out


def _next_generated_id() -> str:
    """Generate the next case ID in the form g%d where %d increments the max present number."""
    pat = re.compile(r"^g(\d+)$")
    max_n = 0
    for c in Case.select(Case.id):
        m = pat.match(str(c.id))
        if m:
            try:
                n = int(m.group(1))
            except ValueError:
                continue
            if n > max_n:
                max_n = n
    return f"g{max_n + 1}"


@router.post("/cases", response_model=CaseOut)
def create_case(body: CaseIn) -> CaseOut:
    ensure_db()
    # Generate a unique ID using the g%d scheme
    new_id = _next_generated_id()
    # Double-check uniqueness just in case
    if Case.get_or_none(Case.id == new_id) is not None:
        raise HTTPException(status_code=409, detail=f"Case ID collision for {new_id}")
    c = Case.create(id=new_id, adjective=body.adjective, case_template=body.case_template)
    return CaseOut(id=str(c.id), adjective=str(c.adjective), case_template=c.case_template, linked_results_n=0)


@router.put("/cases/{case_id}", response_model=CaseOut)
def update_case(case_id: str, body: CaseIn) -> CaseOut:
    ensure_db()
    c = Case.get_or_none(Case.id == case_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Case not found")
    c.adjective = body.adjective
    c.case_template = body.case_template
    c.save()
    linked = BenchmarkResult.select().where(BenchmarkResult.case_id == case_id).count()
    return CaseOut(id=str(c.id), adjective=str(c.adjective), case_template=c.case_template, linked_results_n=int(linked))


@router.delete("/cases/{case_id}")
def delete_case(case_id: str) -> Dict[str, Any]:
    ensure_db()
    c = Case.get_or_none(Case.id == case_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Case not found")
    linked = BenchmarkResult.select().where(BenchmarkResult.case_id == case_id).count()
    if linked > 0:
        raise HTTPException(status_code=400, detail="Case ist mit Benchmark-Resultaten verknüpft und kann nicht gelöscht werden")
    c.delete_instance()  # RESTRICT also protects at DB level
    return {"ok": True}

