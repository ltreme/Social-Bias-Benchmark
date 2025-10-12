from __future__ import annotations

from typing import Any, Dict, List, Optional
import json

from fastapi import APIRouter
from pydantic import BaseModel

from ..utils import ensure_db
from shared.storage.models import Dataset, DatasetPersona, Persona, Country, AttrGenerationRun, AdditionalPersonaAttributes, CounterfactualLink
from shared.datasets.builder import (
    build_balanced_dataset_from_pool,
    build_counterfactuals_from_dataset,
    build_random_subset_from_pool,
)
from persona_generator.main import sample_personas, persist_run_and_personas
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
    additional_attributes_n: Optional[int] = 0
    name_n: Optional[int] = 0
    appearances_n: Optional[int] = 0
    biographies_n: Optional[int] = 0
    enriched_percentage: Optional[float] = 0.0
    


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
    # Use the latest attrgen run for progress stats
    latest_attr_run = (
        AttrGenerationRun
        .select()
        .where(AttrGenerationRun.dataset_id == ds.id)
        .order_by(AttrGenerationRun.id.desc())
        .first()
    )
    # Compute enrichment across any run (robust against older rows)
    def _count_attr(key: str) -> int:
        return (AdditionalPersonaAttributes
                .select()
                .join(DatasetPersona, on=(DatasetPersona.persona_id == AdditionalPersonaAttributes.persona_uuid_id))
                .where((DatasetPersona.dataset_id == ds.id) & (AdditionalPersonaAttributes.attribute_key == key))
                .count())
    name_n = _count_attr('name')
    appearances_n = _count_attr('appearance')
    biographies_n = _count_attr('biography')
    additional_attributes_n = name_n + appearances_n + biographies_n
    enriched_percentage = (additional_attributes_n / (n * 3) * 100) if n > 0 else 0.0

    return DatasetOut(
        id=ds.id, 
        name=ds.name, 
        kind=ds.kind, 
        size=n, 
        created_at=ds.created_at.isoformat() if ds.created_at else None, 
        seed=ds.seed, 
        config_json=json.loads(ds.config_json) if ds.config_json else None,
        additional_attributes_n = additional_attributes_n,
        name_n = name_n,
        appearances_n = appearances_n,
        biographies_n = biographies_n,
        enriched_percentage = enriched_percentage,
    )


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


# --------- Persona browser endpoints ---------

class PersonaOut(BaseModel):
    uuid: str
    created_at: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    education: Optional[str] = None
    occupation: Optional[str] = None
    marriage_status: Optional[str] = None
    migration_status: Optional[str] = None
    religion: Optional[str] = None
    sexuality: Optional[str] = None
    origin_country: Optional[str] = None
    origin_region: Optional[str] = None
    origin_subregion: Optional[str] = None
    additional_attributes: Optional[dict] = None


@router.get("/datasets/{dataset_id}/personas")
def list_personas(
    dataset_id: int,
    limit: int = 50,
    offset: int = 0,
    sort: str = "created_at",
    order: str = "desc",
    attrgen_run_id: Optional[int] = None,
    gender: Optional[str] = None,
    religion: Optional[str] = None,
    sexuality: Optional[str] = None,
    education: Optional[str] = None,
    marriage_status: Optional[str] = None,
    migration_status: Optional[str] = None,
    origin_subregion: Optional[str] = None,
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
) -> Dict[str, Any]:
    """Return personas that belong to a dataset with pagination, simple filters and latest additional attributes.

    Query parameters:
      - limit, offset
      - sort: one of ['created_at','age','gender','education','religion','sexuality','marriage_status','migration_status','origin_subregion']
      - order: 'asc' | 'desc'
      - filters: listed optional fields
    """
    ensure_db()
    from peewee import JOIN

    q = (Persona
         .select(Persona, Country)
         .join(DatasetPersona, on=(DatasetPersona.persona_id == Persona.uuid))
         .switch(Persona)
         .join(Country, JOIN.LEFT_OUTER, on=(Persona.origin_id == Country.id))
         .where(DatasetPersona.dataset_id == dataset_id))

    # Apply filters
    if gender:
        q = q.where((Persona.gender == gender))
    if religion:
        q = q.where((Persona.religion == religion))
    if sexuality:
        q = q.where((Persona.sexuality == sexuality))
    if education:
        q = q.where((Persona.education == education))
    if marriage_status:
        q = q.where((Persona.marriage_status == marriage_status))
    if migration_status:
        q = q.where((Persona.migration_status == migration_status))
    if origin_subregion:
        q = q.where((Country.subregion == origin_subregion))
    if min_age is not None:
        q = q.where((Persona.age.is_null(True)) | (Persona.age >= int(min_age)))
    if max_age is not None:
        q = q.where((Persona.age.is_null(True)) | (Persona.age <= int(max_age)))

    total = q.count()

    # Sorting
    sort_map = {
        'created_at': Persona.created_at,
        'age': Persona.age,
        'gender': Persona.gender,
        'education': Persona.education,
        'religion': Persona.religion,
        'sexuality': Persona.sexuality,
        'marriage_status': Persona.marriage_status,
        'migration_status': Persona.migration_status,
        'origin_subregion': Country.subregion,
    }
    col = sort_map.get(sort, Persona.created_at)
    col = col.desc() if str(order).lower() == 'desc' else col.asc()
    q = q.order_by(col).limit(max(1, int(limit))).offset(max(0, int(offset)))

    rows = list(q)
    uuids = [r.uuid for r in rows]
    # Fetch additional attributes per persona+key scoped to a specific AttrGenerationRun when provided
    add_map: Dict[str, Dict[str, Any]] = {}
    if uuids and attrgen_run_id is not None:
        sub = (AdditionalPersonaAttributes
               .select(AdditionalPersonaAttributes)
               .where((AdditionalPersonaAttributes.persona_uuid_id.in_(uuids)) & (AdditionalPersonaAttributes.attr_generation_run_id == int(attrgen_run_id)))
               .order_by(AdditionalPersonaAttributes.persona_uuid_id, AdditionalPersonaAttributes.attribute_key, AdditionalPersonaAttributes.id.desc()))
        for a in sub:
            pid = str(a.persona_uuid_id)
            add_map.setdefault(pid, {})
            if a.attribute_key not in add_map[pid]:
                add_map[pid][a.attribute_key] = a.value

    items: List[PersonaOut] = []
    for r in rows:
        items.append(PersonaOut(
            uuid=str(r.uuid),
            created_at=str(r.created_at) if r.created_at else None,
            age=int(r.age) if r.age is not None else None,
            gender=r.gender,
            education=r.education,
            occupation=r.occupation,
            marriage_status=r.marriage_status,
            migration_status=r.migration_status,
            religion=r.religion,
            sexuality=r.sexuality,
            origin_country=getattr(r.origin_id, 'country_en', None),
            origin_region=getattr(r.origin_id, 'region', None),
            origin_subregion=getattr(r.origin_id, 'subregion', None),
            additional_attributes=add_map.get(str(r.uuid), {}),
        ))
    return {"ok": True, "total": int(total), "items": [i.model_dump() for i in items]}


# --------- Build endpoints ---------

class CreatePoolIn(BaseModel):
    n: int = 20000
    temperature: float = 0.1
    age_from: int = 0
    age_to: int = 100
    name: Optional[str] = None


class CreateDsOut(BaseModel):
    id: int
    name: str


@router.post("/datasets/build-balanced", response_model=CreateDsOut)
def api_build_balanced(body: Dict[str, Any]) -> CreateDsOut:
    """Build a balanced dataset from an existing dataset.
    body: { dataset_id: int, n: int, seed?: int, name?: str }
    """
    ensure_db()
    ds = build_balanced_dataset_from_pool(dataset_id=int(body["dataset_id"]), axes=["gender", "age", "origin"], n_target=int(body.get("n", 2000)), seed=int(body.get("seed", 42)), name=body.get("name"))
    return CreateDsOut(id=int(ds.id), name=str(ds.name))


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: int) -> Dict[str, Any]:
    """Delete a dataset and all associated artifacts.

    Behavior:
    - Deletes AdditionalPersonaAttributes for AttrGenerationRuns of this dataset
    - Deletes AttrGenerationRuns of this dataset
    - Deletes CounterfactualLink rows of this dataset
    - Deletes the Dataset (cascades to DatasetPersona, BenchmarkRun, BenchmarkResult)
    - Deletes Personas that no longer belong to any dataset (cascades their AdditionalPersonaAttributes)
    """
    ensure_db()
    from shared.storage.db import transaction
    from peewee import fn

    stats: Dict[str, int] = {
        'deleted_attr_rows': 0,
        'deleted_attr_runs': 0,
        'deleted_cf_links': 0,
        'deleted_dataset': 0,
        'deleted_orphan_personas': 0,
    }

    with transaction():
        # 1) Remove AdditionalPersonaAttributes generated by runs of this dataset
        run_ids = [int(r.id) for r in AttrGenerationRun.select(AttrGenerationRun.id).where(AttrGenerationRun.dataset_id == dataset_id)]
        if run_ids:
            stats['deleted_attr_rows'] = int(AdditionalPersonaAttributes.delete().where(AdditionalPersonaAttributes.attr_generation_run_id.in_(run_ids)).execute() or 0)
        stats['deleted_attr_runs'] = int(AttrGenerationRun.delete().where(AttrGenerationRun.dataset_id == dataset_id).execute() or 0)

        # 2) Remove counterfactual links for this dataset (also cascades if dataset deleted later)
        stats['deleted_cf_links'] = int(CounterfactualLink.delete().where(CounterfactualLink.dataset_id == dataset_id).execute() or 0)

        # 3) Delete dataset (CASCADE to DatasetPersona, BenchmarkRun, BenchmarkResult)
        stats['deleted_dataset'] = int(Dataset.delete().where(Dataset.id == dataset_id).execute() or 0)

        # 4) Remove personas that are no longer members of any dataset
        #    Find personas with zero memberships
        member_subq = DatasetPersona.select(DatasetPersona.persona_id).distinct()
        orphan_personas = Persona.select(Persona.uuid).where(~(Persona.uuid.in_(member_subq)))
        orphan_ids = [p.uuid for p in orphan_personas]
        if orphan_ids:
            stats['deleted_orphan_personas'] = int(Persona.delete().where(Persona.uuid.in_(orphan_ids)).execute() or 0)

    return {"ok": True, **stats}


@router.post("/datasets/sample-reality", response_model=CreateDsOut)
def api_sample_reality(body: Dict[str, Any]) -> CreateDsOut:
    """Sample random subset from an existing dataset.
    body: { dataset_id: int, n: int, seed?: int, name?: str }
    """
    ensure_db()
    ds = build_random_subset_from_pool(dataset_id=int(body["dataset_id"]), n=int(body.get("n", 500)), seed=int(body.get("seed", 42)), name=body.get("name"))
    return CreateDsOut(id=int(ds.id), name=str(ds.name))


@router.post("/datasets/build-counterfactuals", response_model=CreateDsOut)
def api_build_counterfactuals(body: Dict[str, Any]) -> CreateDsOut:
    """Build counterfactual dataset from an existing dataset.
    body: { dataset_id: int, seed?: int, name?: str }
    """
    ensure_db()
    ds = build_counterfactuals_from_dataset(dataset_id=int(body["dataset_id"]), seed=int(body.get("seed", 42)), name=body.get("name"))
    return CreateDsOut(id=int(ds.id), name=str(ds.name))


@router.post("/datasets/generate-pool", response_model=CreateDsOut)
def api_generate_pool(body: CreatePoolIn) -> CreateDsOut:
    ensure_db()
    params = dict(
        age_min=body.age_from,
        age_max=body.age_to,
        age_temperature=body.temperature,
        education_temperature=body.temperature,
        education_exclude=None,
        gender_temperature=body.temperature,
        gender_exclude=None,
        occupation_exclude=None,
        marriage_status_temperature=body.temperature,
        marriage_status_exclude=None,
        migration_status_temperature=body.temperature,
        migration_status_exclude=None,
        origin_temperature=body.temperature,
        origin_exclude=None,
        religion_temperature=body.temperature,
        religion_exclude=None,
        sexuality_temperature=body.temperature,
        sexuality_exclude=None,
    )
    sampled = sample_personas(n=body.n, **params)
    ds_id = persist_run_and_personas(n=body.n, params=params, sampled=sampled, export_csv_path=None)
    ds = Dataset.get_by_id(ds_id)
    if body.name:
        ds.name = str(body.name)
        ds.save()
    return CreateDsOut(id=int(ds.id), name=str(ds.name))
