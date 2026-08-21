"""HTTP layer for routing."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.route import CityInfo, RouteResponse
from app.services import routing_service
from app.services.routing_service import RouteError

router = APIRouter(prefix="/route", tags=["routing"])


@router.get("/cities", response_model=list[CityInfo])
def route_cities(db: Annotated[Session, Depends(get_db)]) -> list[CityInfo]:
    return routing_service.cities(db)


@router.get("", response_model=RouteResponse)
def get_route(
    db: Annotated[Session, Depends(get_db)],
    city: Annotated[str, Query()],
    from_lat: Annotated[float, Query(ge=-90, le=90)],
    from_lng: Annotated[float, Query(ge=-180, le=180)],
    to_lat: Annotated[float, Query(ge=-90, le=90)],
    to_lng: Annotated[float, Query(ge=-180, le=180)],
    cost: Annotated[Literal["time", "distance"], Query()] = "time",
) -> RouteResponse:
    try:
        return routing_service.route(db, city, from_lat, from_lng, to_lat, to_lng, cost)
    except RouteError as exc:
        raise HTTPException(404, str(exc)) from exc
