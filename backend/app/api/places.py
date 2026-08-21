"""HTTP layer for places — parse query params, call the service, serialize."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.place import FeatureCollection, PlaceFilters
from app.services import place_service
from app.services.place_service import InvalidFilter

router = APIRouter(prefix="/places", tags=["places"])


def _parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    if bbox is None:
        return None
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(422, "bbox must be 'min_lon,min_lat,max_lon,max_lat'")
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError as exc:
        raise HTTPException(422, "bbox values must be numbers") from exc
    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(422, "bbox min must be less than max")
    return (min_lon, min_lat, max_lon, max_lat)


@router.get("", response_model=FeatureCollection)
def list_places(
    db: Annotated[Session, Depends(get_db)],
    bbox: Annotated[
        str | None,
        Query(description="Viewport 'min_lon,min_lat,max_lon,max_lat'"),
    ] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_m: Annotated[
        float | None, Query(gt=0, description="Radius in meters (needs lat+lng)")
    ] = None,
    category: Annotated[str | None, Query()] = None,
    min_rating: Annotated[float | None, Query(ge=0, le=5)] = None,
    max_price: Annotated[int | None, Query(ge=1, le=4)] = None,
    open_24h: Annotated[bool | None, Query()] = None,
    sort: Annotated[Literal["id", "nearest"], Query()] = "id",
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> FeatureCollection:
    filters = PlaceFilters(
        bbox=_parse_bbox(bbox),
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        category=category,
        min_rating=min_rating,
        max_price=max_price,
        open_24h=open_24h,
        sort=sort,
        limit=limit,
    )
    try:
        return place_service.search_places(db, filters)
    except InvalidFilter as exc:
        raise HTTPException(422, str(exc)) from exc
