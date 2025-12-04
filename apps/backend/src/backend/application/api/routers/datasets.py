"""Router for dataset endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.application.services.dataset_service import DatasetService
from backend.domain.persona.dataset_validator import DatasetValidationError

from ..deps import db_session
from ..utils import ensure_db

router = APIRouter(tags=["datasets"], dependencies=[Depends(db_session)])

# Service singleton (for single-process dev)
_service: DatasetService | None = None


def get_service() -> DatasetService:
    """Get or create the DatasetService instance."""
    global _service
    if _service is None:
        _service = DatasetService()
    return _service


# ========== Request/Response Models ==========


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
    runs_count: Optional[int] = 0
    models_count: Optional[int] = 0
    source_dataset_id: Optional[int] = None
    source_dataset_name: Optional[str] = None


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


class CreatePoolIn(BaseModel):
    n: int = 20000
    temperature: float = 0.1
    age_from: int = 0
    age_to: int = 100
    name: Optional[str] = None


class CreateDsOut(BaseModel):
    id: int
    name: str


class PoolStartIn(BaseModel):
    n: int
    temperature: float
    age_from: int
    age_to: int
    name: Optional[str] = None


class BalancedStartIn(BaseModel):
    dataset_id: int
    n: int
    seed: int = 42
    name: Optional[str] = None


# ========== Dataset CRUD Endpoints ==========


@router.get("/datasets", response_model=List[DatasetOut])
def list_datasets() -> List[DatasetOut]:
    """List all datasets."""
    ensure_db()
    service = get_service()
    datasets = service.list_datasets()
    return [DatasetOut(**ds.to_dict()) for ds in datasets]


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: int) -> DatasetOut:
    """Get detailed dataset information including enrichment stats."""
    ensure_db()
    service = get_service()
    dataset = service.get_dataset(dataset_id)
    return DatasetOut(**dataset.to_dict())


@router.get("/datasets/{dataset_id}/runs")
def dataset_runs(dataset_id: int) -> List[Dict[str, Any]]:
    """Return benchmark runs associated with a dataset."""
    ensure_db()
    service = get_service()
    return service.get_dataset_runs(dataset_id)


@router.get("/datasets/{dataset_id}/composition")
def dataset_composition(dataset_id: int) -> Dict[str, Any]:
    """Return composition stats for a dataset with age pyramid."""
    ensure_db()
    service = get_service()
    return service.get_dataset_composition(dataset_id)


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: int) -> Dict[str, Any]:
    """Delete a dataset and all associated artifacts synchronously."""
    ensure_db()
    service = get_service()
    return service.delete_dataset_sync(dataset_id)


# ========== Persona Browser Endpoints ==========


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
    """List personas with pagination, filters, and optional additional attributes."""
    ensure_db()
    service = get_service()

    filters = {
        "gender": gender,
        "religion": religion,
        "sexuality": sexuality,
        "education": education,
        "marriage_status": marriage_status,
        "migration_status": migration_status,
        "origin_subregion": origin_subregion,
        "min_age": min_age,
        "max_age": max_age,
    }

    try:
        return service.list_personas(
            dataset_id, limit, offset, sort, order, attrgen_run_id, filters
        )
    except DatasetValidationError as e:
        return {"ok": False, "error": str(e)}


@router.get("/datasets/{dataset_id}/personas/export")
def export_personas_csv(
    dataset_id: int, attrgen_run_id: Optional[int] = None
) -> StreamingResponse:
    """Stream personas as CSV with optional additional attributes."""
    ensure_db()
    service = get_service()

    stream, filename = service.export_personas_csv(dataset_id, attrgen_run_id)

    return StreamingResponse(
        stream,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ========== Dataset Building Endpoints (Synchronous) ==========


@router.post("/datasets/build-balanced", response_model=CreateDsOut)
def api_build_balanced(body: Dict[str, Any]) -> CreateDsOut:
    """Build a balanced dataset from an existing dataset."""
    ensure_db()
    service = get_service()

    try:
        result = service.build_balanced_dataset(body)
        return CreateDsOut(**result)
    except DatasetValidationError as e:
        return CreateDsOut(id=0, name=f"Error: {str(e)}")


@router.post("/datasets/sample-reality", response_model=CreateDsOut)
def api_sample_reality(body: Dict[str, Any]) -> CreateDsOut:
    """Sample random subset from an existing dataset."""
    ensure_db()
    service = get_service()

    result = service.build_random_subset(body)
    return CreateDsOut(**result)


@router.post("/datasets/build-counterfactuals", response_model=CreateDsOut)
def api_build_counterfactuals(body: Dict[str, Any]) -> CreateDsOut:
    """Build counterfactual dataset from an existing dataset."""
    ensure_db()
    service = get_service()

    result = service.build_counterfactuals(body)
    return CreateDsOut(**result)


@router.post("/datasets/generate-pool", response_model=CreateDsOut)
def api_generate_pool(body: CreatePoolIn) -> CreateDsOut:
    """Generate a pool dataset synchronously."""
    ensure_db()
    service = get_service()

    try:
        result = service.generate_pool_sync(body.model_dump())
        return CreateDsOut(**result)
    except DatasetValidationError as e:
        return CreateDsOut(id=0, name=f"Error: {str(e)}")


# ========== Background Job Endpoints ==========


@router.post("/datasets/pool/start")
def start_pool_generation(body: PoolStartIn) -> Dict[str, Any]:
    """Start pool generation in background."""
    ensure_db()
    service = get_service()

    try:
        result = service.start_pool_generation(body.model_dump())
        return {"ok": True, **result}
    except DatasetValidationError as e:
        return {"ok": False, "error": str(e)}


@router.get("/datasets/pool/{job_id}/status")
def pool_status(job_id: int) -> Dict[str, Any]:
    """Get status of a pool generation job."""
    ensure_db()
    service = get_service()
    status = service.get_pool_status(job_id)
    return {"ok": True, **status}


@router.post("/datasets/balanced/start")
def start_balanced_generation(body: BalancedStartIn) -> Dict[str, Any]:
    """Start balanced dataset generation in background."""
    ensure_db()
    service = get_service()

    try:
        result = service.start_balanced_generation(body.model_dump())
        return {"ok": True, **result}
    except DatasetValidationError as e:
        return {"ok": False, "error": str(e)}


@router.get("/datasets/balanced/{job_id}/status")
def balanced_status(job_id: int) -> Dict[str, Any]:
    """Get status of a balanced generation job."""
    ensure_db()
    service = get_service()
    status = service.get_balanced_status(job_id)
    return {"ok": True, **status}


@router.post("/datasets/{dataset_id}/delete/start")
def start_dataset_delete(dataset_id: int) -> Dict[str, Any]:
    """Start dataset deletion in background."""
    ensure_db()
    service = get_service()

    result = service.start_dataset_deletion(dataset_id)
    return {"ok": True, **result}


@router.get("/datasets/delete/{job_id}/status")
def delete_status(job_id: int) -> Dict[str, Any]:
    """Get status of a dataset deletion job."""
    ensure_db()
    service = get_service()
    status = service.get_delete_status(job_id)
    return {"ok": True, **status}
