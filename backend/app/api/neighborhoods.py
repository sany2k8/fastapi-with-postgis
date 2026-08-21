"""HTTP layer for neighborhoods."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.neighborhood import NeighborhoodCollection, NeighborhoodStat
from app.schemas.place import FeatureCollection
from app.services import neighborhood_service
from app.services.neighborhood_service import NeighborhoodNotFound

router = APIRouter(prefix="/neighborhoods", tags=["neighborhoods"])


@router.get("", response_model=NeighborhoodCollection)
def list_neighborhoods(
    db: Annotated[Session, Depends(get_db)],
) -> NeighborhoodCollection:
    return neighborhood_service.list_neighborhoods(db)


@router.get("/stats", response_model=list[NeighborhoodStat])
def neighborhood_stats(
    db: Annotated[Session, Depends(get_db)],
) -> list[NeighborhoodStat]:
    return neighborhood_service.stats(db)


@router.get("/{nid}/places", response_model=FeatureCollection)
def places_in_neighborhood(
    nid: int,
    db: Annotated[Session, Depends(get_db)],
    category: Annotated[str | None, Query()] = None,
    min_rating: Annotated[float | None, Query(ge=0, le=5)] = None,
) -> FeatureCollection:
    try:
        return neighborhood_service.places_in_neighborhood(db, nid, category, min_rating)
    except NeighborhoodNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
