"""Schemas for the routing API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CityInfo(BaseModel):
    city: str
    nodes: int
    edges: int
    center_lat: float
    center_lng: float


class LineGeometry(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[list[float]]  # [[lon, lat], ...]


class SnappedPoint(BaseModel):
    lat: float
    lng: float
    snap_distance_m: float  # how far the click was from the road


class RouteResponse(BaseModel):
    city: str
    cost: Literal["time", "distance"]
    distance_m: float
    duration_s: float
    geometry: LineGeometry
    node_count: int
    start: SnappedPoint
    end: SnappedPoint
