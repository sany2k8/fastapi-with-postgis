"""Business logic for neighborhoods: GeoJSON polygons, point-in-polygon, stats."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.repositories import neighborhood_repo
from app.schemas.neighborhood import (
    NeighborhoodCollection,
    NeighborhoodFeature,
    NeighborhoodProperties,
    NeighborhoodStat,
    PolygonGeometry,
)
from app.schemas.place import (
    Feature,
    FeatureCollection,
    PlaceProperties,
    PointGeometry,
)


class NeighborhoodNotFound(Exception):
    pass


def list_neighborhoods(db: Session) -> NeighborhoodCollection:
    rows = neighborhood_repo.list_neighborhoods(db)
    features = [
        NeighborhoodFeature(
            geometry=PolygonGeometry(coordinates=json.loads(r.geojson)["coordinates"]),
            properties=NeighborhoodProperties(id=r.id, name=r.name),
        )
        for r in rows
    ]
    return NeighborhoodCollection(features=features)


def places_in_neighborhood(
    db: Session, nid: int, category: str | None, min_rating: float | None
) -> FeatureCollection:
    if neighborhood_repo.get_neighborhood(db, nid) is None:
        raise NeighborhoodNotFound(f"neighborhood {nid} not found")
    rows = neighborhood_repo.places_in_neighborhood(db, nid, category, min_rating)
    features = [
        Feature(
            geometry=PointGeometry(coordinates=json.loads(r.geojson)["coordinates"]),
            properties=PlaceProperties(
                id=r.id,
                name=r.name,
                category=r.category,
                rating=r.rating,
                price_level=r.price_level,
                is_open_24h=r.is_open_24h,
                distance_m=None,
            ),
        )
        for r in rows
    ]
    return FeatureCollection(features=features)


def stats(db: Session) -> list[NeighborhoodStat]:
    totals = neighborhood_repo.stats_totals(db)
    by_cat = neighborhood_repo.stats_by_category(db)

    # Fold the per-category rows into {neighborhood_id: {category: count}}.
    cat_map: dict[int, dict[str, int]] = {}
    for r in by_cat:
        cat_map.setdefault(r.nid, {})[r.category] = r.cnt

    return [
        NeighborhoodStat(
            id=r.id,
            name=r.name,
            place_count=r.place_count,
            avg_rating=r.avg_rating,
            by_category=cat_map.get(r.id, {}),
        )
        for r in totals
    ]
