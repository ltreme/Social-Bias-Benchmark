from __future__ import annotations

from typing import Any, Dict, List, Optional
import json

from fastapi import APIRouter
from pydantic import BaseModel

from ..utils import ensure_db
from shared.storage.models import Dataset, DatasetPersona, Persona, Country
from peewee import JOIN


router = APIRouter(tags=["datasets"])


class DatasetOut(BaseModel):
    id: int
    name: str
    kind: str
    size: int
    created_at: Optional[str] = None
    seed: Optional[int] = None
    config_json: Optional[Dict[str, Any]] = None
    


@router.get("/datasets", response_model=List[DatasetOut])
def list_datasets() -> List[DatasetOut]:
    ensure_db()
    out: List[DatasetOut] = []
    for ds in Dataset.select():
        n = DatasetPersona.select().where(DatasetPersona.dataset_id == ds.id).count()
        out.append(DatasetOut(id=ds.id, name=ds.name, kind=ds.kind, size=n, created_at=ds.created_at.isoformat() if ds.created_at else None, seed=ds.seed, config_json=json.loads(ds.config_json) if ds.config_json else None))
    return out

@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: int) -> DatasetOut:
    ensure_db()
    ds = Dataset.get_or_none(Dataset.id == dataset_id)
    if not ds:
        return DatasetOut(id=0, name="Unknown", kind="unknown", size=0)
    n = DatasetPersona.select().where(DatasetPersona.dataset_id == ds.id).count()
    return DatasetOut(id=ds.id, name=ds.name, kind=ds.kind, size=n, created_at=ds.created_at.isoformat() if ds.created_at else None, seed=ds.seed, config_json=json.loads(ds.config_json) if ds.config_json else None)


@router.get("/datasets/{dataset_id}/runs")
def dataset_runs(dataset_id: int) -> List[Dict[str, Any]]:
    """Return runs associated with a dataset."""
    ensure_db()
    from shared.storage.models import BenchmarkRun, Model

    out: List[Dict[str, Any]] = []
    for r in BenchmarkRun.select().join(Model).where(BenchmarkRun.dataset_id == dataset_id).order_by(BenchmarkRun.id.desc()):
        out.append(
            {
                "id": int(r.id),
                "model_name": str(r.model_id.name),
                "include_rationale": bool(r.include_rationale),
                "created_at": str(r.created_at),
            }
        )
    return out

@router.get("/datasets/{dataset_id}/composition")
def dataset_composition(dataset_id: int) -> Dict[str, Any]:
    """Return composition stats for a dataset and an age pyramid."""
    ensure_db()
    member_personas = list(
        Persona.select(Persona, Country)
        .join(DatasetPersona, on=(DatasetPersona.persona_id == Persona.uuid))
        .switch(Persona)
        .join(Country, on=(Persona.origin_id == Country.id), join_type=JOIN.LEFT_OUTER)
        .where(DatasetPersona.dataset_id == dataset_id)
    )
    n = len(member_personas)
    if n == 0:
        return {
            "ok": True,
            "n": 0,
            "attributes": {},
            "age": {"bins": [], "male": [], "female": [], "other": []},
        }

    def norm(v: Optional[str]) -> str:
        s = (v or "").strip()
        return s if s else "Unknown"

    from collections import Counter

    buckets: Dict[str, Counter] = {
        "gender": Counter(),
        "religion": Counter(),
        "sexuality": Counter(),
        "education": Counter(),
        "marriage_status": Counter(),
        "migration_status": Counter(),
        "origin_country": Counter(),
        "origin_region": Counter(),
        "origin_subregion": Counter(),
    }

    def age_bin(a: Optional[int]) -> str:
        if a is None or a < 0:
            return "Unknown"
        if a >= 90:
            return "90+"
        lo = (a // 5) * 5
        return f"{lo}-{lo+4}"

    from collections import Counter as C

    age_by_gender: Dict[str, C] = {"male": C(), "female": C(), "other": C()}
    for p in member_personas:
        buckets["gender"][norm(p.gender)] += 1
        buckets["religion"][norm(p.religion)] += 1
        buckets["sexuality"][norm(p.sexuality)] += 1
        buckets["education"][norm(p.education)] += 1
        buckets["marriage_status"][norm(p.marriage_status)] += 1
        buckets["migration_status"][norm(p.migration_status)] += 1
        country = getattr(p, "origin_id", None)
        buckets["origin_country"][norm(getattr(country, "country_en", None))] += 1
        buckets["origin_region"][norm(getattr(country, "region", None))] += 1
        buckets["origin_subregion"][norm(getattr(country, "subregion", None))] += 1

        gb = (p.gender or "").strip().lower()
        gkey = "other"
        if gb in ("male", "m", "man"):
            gkey = "male"
        elif gb in ("female", "f", "woman"):
            gkey = "female"
        abin = age_bin(getattr(p, "age", None))
        age_by_gender[gkey][abin] += 1

    def pack(counter, limit: Optional[int] = None):
        items = counter.most_common()
        if limit is not None:
            items = items[:limit]
        total = sum(counter.values()) or 1
        return [
            {"value": k, "count": int(v), "share": float(v) / float(total)} for k, v in items
        ]

    bin_labels = [*(f"{b}-{b+4}" for b in range(0, 90, 5)), "90+", "Unknown"]
    age = {
        "bins": bin_labels,
        "male": [int(age_by_gender["male"].get(b, 0)) for b in bin_labels],
        "female": [int(age_by_gender["female"].get(b, 0)) for b in bin_labels],
        "other": [int(age_by_gender["other"].get(b, 0)) for b in bin_labels],
    }

    attributes: Dict[str, Any] = {
        key: pack(cnt, 30 if key in ("origin_country",) else None)
        for key, cnt in buckets.items()
    }

    return {"ok": True, "n": n, "attributes": attributes, "age": age}

