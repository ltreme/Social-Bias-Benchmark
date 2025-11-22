"""Traits API router - simplified to pure routing logic."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.application.services.trait_service import TraitService

from ..deps import db_session
from ..utils import ensure_db

router = APIRouter(tags=["traits"], dependencies=[Depends(db_session)])


class TraitOut(BaseModel):
    id: str
    adjective: str
    case_template: Optional[str] = None
    category: Optional[str] = None
    valence: Optional[Annotated[int, Field(ge=-1, le=1)]] = None
    is_active: bool = True
    linked_results_n: int = 0


class TraitIn(BaseModel):
    adjective: str
    case_template: Optional[str] = None
    category: Optional[str] = None
    valence: Optional[Annotated[int, Field(ge=-1, le=1)]] = None


class TraitActiveIn(BaseModel):
    is_active: bool


class TraitExportIn(BaseModel):
    trait_ids: List[str]


def _get_service() -> TraitService:
    """Get trait service instance."""
    ensure_db()
    return TraitService()


@router.get("/traits", response_model=List[TraitOut])
def list_traits() -> List[TraitOut]:
    """List all traits with metadata."""
    traits = _get_service().list_traits()
    return [TraitOut(**t) for t in traits]


@router.get("/traits/export")
def export_traits() -> StreamingResponse:
    """Export all traits as CSV."""
    content, filename = _get_service().export_all_traits()
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([content]), media_type="text/csv", headers=headers)


@router.post("/traits/export")
def export_filtered_traits(body: TraitExportIn) -> StreamingResponse:
    """Export traits with specific IDs in the given order."""
    content, filename = _get_service().export_filtered_traits(body.trait_ids)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([content]), media_type="text/csv", headers=headers)


@router.post("/traits", response_model=TraitOut)
def create_trait(body: TraitIn) -> TraitOut:
    """Create a new trait."""
    try:
        result = _get_service().create_trait(
            adjective=body.adjective,
            case_template=body.case_template,
            category=body.category,
            valence=body.valence,
        )
        return TraitOut(**result)
    except ValueError as e:
        if "erforderlich" in str(e):
            raise HTTPException(status_code=422, detail=str(e))
        elif "existiert bereits" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        elif "collision" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/traits/{trait_id}", response_model=TraitOut)
def update_trait(trait_id: str, body: TraitIn) -> TraitOut:
    """Update an existing trait."""
    try:
        result = _get_service().update_trait(
            trait_id=trait_id,
            adjective=body.adjective,
            case_template=body.case_template,
            category=body.category,
            valence=body.valence,
        )
        return TraitOut(**result)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        elif "erforderlich" in str(e):
            raise HTTPException(status_code=422, detail=str(e))
        elif "existiert bereits" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/traits/{trait_id}")
def delete_trait(trait_id: str) -> Dict[str, Any]:
    """Delete a trait."""
    try:
        _get_service().delete_trait(trait_id)
        return {"ok": True}
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        elif "verknüpft" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/traits/categories")
def list_trait_categories() -> Dict[str, List[str]]:
    """List all distinct trait categories."""
    categories = _get_service().list_categories()
    return {"categories": categories}


@router.post("/traits/{trait_id}/active", response_model=TraitOut)
def set_trait_active(trait_id: str, body: TraitActiveIn) -> TraitOut:
    """Set trait active status."""
    try:
        result = _get_service().set_trait_active(trait_id, body.is_active)
        return TraitOut(**result)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/traits/import")
async def import_traits(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Import traits from CSV file."""
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    try:
        result = _get_service().import_traits(text)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
