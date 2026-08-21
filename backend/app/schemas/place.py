"""Pydantic schemas: filter params in, GeoJSON FeatureCollection out.

The API speaks GeoJSON (https://geojson.org) so the frontend can hand responses
straight to Leaflet's L.geoJSON(). Coordinates are always [longitude, latitude].
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


@dataclass
class PlaceFilters:
    """Parsed, validated query parameters for a places search."""

    bbox: tuple[float, float, float, float] | None = None  # min_lon,min_lat,max_lon,max_lat
    lat: float | None = None
    lng: float | None = None
    radius_m: float | None = None
    category: str | None = None
    min_rating: float | None = None
    max_price: int | None = None
    open_24h: bool | None = None
    sort: Literal["id", "nearest"] = "id"
    limit: int = 500

    @property
    def has_point(self) -> bool:
        return self.lat is not None and self.lng is not None


class PlaceProperties(BaseModel):
    id: int
    name: str
    category: str
    rating: float
    price_level: int
    is_open_24h: bool
    # Present only for radius or nearest queries; straight-line meters.
    distance_m: float | None = None


class PointGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float]  # [lon, lat]


class Feature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: PointGeometry
    properties: PlaceProperties


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature]
