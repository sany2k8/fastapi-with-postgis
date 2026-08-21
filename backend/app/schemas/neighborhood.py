"""Schemas for neighborhoods: polygon GeoJSON out, and per-area stats."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PolygonGeometry(BaseModel):
    type: Literal["Polygon"] = "Polygon"
    # GeoJSON polygon: a list of linear rings, each a list of [lon, lat] pairs.
    coordinates: list[list[list[float]]]


class NeighborhoodProperties(BaseModel):
    id: int
    name: str


class NeighborhoodFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: PolygonGeometry
    properties: NeighborhoodProperties


class NeighborhoodCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[NeighborhoodFeature]


class NeighborhoodStat(BaseModel):
    id: int
    name: str
    place_count: int
    avg_rating: float
    by_category: dict[str, int]
