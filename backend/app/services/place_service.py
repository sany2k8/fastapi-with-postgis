"""Business logic for places: validate filters, run the query, build GeoJSON."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.repositories import place_repo
from app.schemas.place import (
    Feature,
    FeatureCollection,
    PlaceFilters,
    PlaceProperties,
    PointGeometry,
)


class InvalidFilter(Exception):
    """Raised when query parameters don't form a valid search."""


def _validate(f: PlaceFilters) -> None:
    if f.radius_m is not None and not f.has_point:
        raise InvalidFilter("radius_m requires both lat and lng")
    if f.sort == "nearest" and not f.has_point:
        raise InvalidFilter("sort=nearest requires both lat and lng")
    if (f.lat is None) != (f.lng is None):
        raise InvalidFilter("lat and lng must be provided together")
    if f.lat is not None and not (-90 <= f.lat <= 90):
        raise InvalidFilter("lat must be between -90 and 90")
    if f.lng is not None and not (-180 <= f.lng <= 180):
        raise InvalidFilter("lng must be between -180 and 180")
    if f.radius_m is not None and f.radius_m <= 0:
        raise InvalidFilter("radius_m must be positive")


def search_places(db: Session, f: PlaceFilters) -> FeatureCollection:
    _validate(f)
    rows = place_repo.search_places(db, f)
    features: list[Feature] = []
    for r in rows:
        geometry = PointGeometry(coordinates=json.loads(r.geojson)["coordinates"])
        props = PlaceProperties(
            id=r.id,
            name=r.name,
            category=r.category,
            rating=r.rating,
            price_level=r.price_level,
            is_open_24h=r.is_open_24h,
            distance_m=round(r.distance_m, 1) if r.distance_m is not None else None,
        )
        features.append(Feature(geometry=geometry, properties=props))
    return FeatureCollection(features=features)
