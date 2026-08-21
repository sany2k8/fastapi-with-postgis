"""Build a routable road graph from OpenStreetMap for three Bangladesh cities.

Pipeline (for each city bbox):
  1. Ask the Overpass API for all drivable `highway` ways + their nodes.
  2. Turn each way into edges: one straight segment per consecutive node pair.
     Intersections need no special handling — two ways that cross share the same
     OSM node id, so they automatically share a graph vertex.
  3. Cost each edge by *travel time* = length / typical speed for its road class.
  4. Bulk-insert nodes (vertices) and roads (edges) into PostGIS.

Idempotent per city (deletes that city's rows first). Run:
    uv run python -m scripts.ingest_roads
"""

from __future__ import annotations

import math
import sys
import time
from typing import Any

import httpx
from sqlalchemy import text

from app.core.db import engine

# City name -> bounding box (min_lon, min_lat, max_lon, max_lat), the same order
# the /api/places bbox uses. Central-area boxes keep the graphs fast to route.
CITIES: dict[str, tuple[float, float, float, float]] = {
    "khulna": (89.510, 22.790, 89.590, 22.875),
    "dhaka": (90.370, 23.720, 90.430, 23.800),
    "chattogram": (91.750, 22.310, 91.840, 22.390),
}

# Drivable road classes we keep, and a typical speed (km/h) for each.
SPEED_KMH: dict[str, float] = {
    "motorway": 80,
    "motorway_link": 45,
    "trunk": 60,
    "trunk_link": 40,
    "primary": 50,
    "primary_link": 35,
    "secondary": 40,
    "secondary_link": 30,
    "tertiary": 35,
    "tertiary_link": 25,
    "unclassified": 30,
    "residential": 25,
    "living_street": 12,
}
HIGHWAY_FILTER = "|".join(SPEED_KMH.keys())

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _overpass_query(bbox: tuple[float, float, float, float]) -> str:
    # bbox is (min_lon, min_lat, max_lon, max_lat); Overpass wants
    # (south, west, north, east) = (min_lat, min_lon, max_lat, max_lon).
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        "[out:json][timeout:180];"
        f'way["highway"~"^({HIGHWAY_FILTER})$"]({min_lat},{min_lon},{max_lat},{max_lon});'
        "(._;>;);"
        "out;"
    )


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def _is_oneway(tags: dict[str, str], highway: str) -> tuple[bool, bool]:
    """Return (oneway, reversed) — reversed means the digitized direction is
    backwards (oneway=-1), so we swap the segment's endpoints."""
    val = tags.get("oneway", "")
    if val == "-1":
        return True, True
    oneway = (
        val in {"yes", "true", "1"}
        or tags.get("junction") == "roundabout"
        or highway in {"motorway", "motorway_link"}
    )
    return oneway, False


def _fetch(city: str, bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    # Overpass rate-limits; retry 429/504 with exponential backoff.
    for attempt in range(5):
        print(f"[{city}] querying Overpass… (attempt {attempt + 1})")
        resp = httpx.post(
            OVERPASS_URL,
            data={"data": _overpass_query(bbox)},
            headers={"User-Agent": "places-finder-learning/0.1 (routing demo)"},
            timeout=200,
        )
        if resp.status_code in (429, 503, 504):
            wait = 20 * (attempt + 1)
            print(f"[{city}] rate-limited ({resp.status_code}); waiting {wait}s…")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"[{city}] Overpass kept rate-limiting; try again later")


def _already_loaded(city: str) -> bool:
    with engine.connect() as conn:
        n = conn.execute(
            text("SELECT count(*) FROM roads WHERE city = :c"), {"c": city}
        ).scalar_one()
    return bool(n)


def _build(city: str, data: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    coords: dict[int, tuple[float, float]] = {}
    ways: list[dict[str, Any]] = []
    for el in data["elements"]:
        if el["type"] == "node":
            coords[el["id"]] = (el["lon"], el["lat"])
        elif el["type"] == "way" and el.get("tags", {}).get("highway") in SPEED_KMH:
            ways.append(el)

    edges: list[dict] = []
    used_nodes: set[int] = set()
    for w in ways:
        tags = w.get("tags", {})
        highway = tags["highway"]
        name = tags.get("name")
        oneway, reverse = _is_oneway(tags, highway)
        speed_mps = SPEED_KMH[highway] * 1000 / 3600
        nodes = w["nodes"]
        if reverse:
            nodes = list(reversed(nodes))
        for a, b in zip(nodes, nodes[1:], strict=False):
            if a not in coords or b not in coords or a == b:
                continue
            (x1, y1), (x2, y2) = coords[a], coords[b]
            length = _haversine_m(x1, y1, x2, y2)
            if length == 0:
                continue
            used_nodes.update((a, b))
            edges.append(
                {
                    "city": city,
                    "osm_way_id": w["id"],
                    "name": name,
                    "highway": highway,
                    "source": a,
                    "target": b,
                    "length_m": length,
                    "cost_s": length / speed_mps,
                    "oneway": oneway,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                }
            )

    node_rows = [
        {"id": nid, "city": city, "lon": coords[nid][0], "lat": coords[nid][1]}
        for nid in used_nodes
    ]
    return node_rows, edges


def _load(city: str, node_rows: list[dict], edges: list[dict]) -> None:
    node_sql = text(
        "INSERT INTO road_nodes (id, city, geom) "
        "VALUES (:id, :city, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) "
        "ON CONFLICT (id) DO NOTHING"
    )
    edge_sql = text(
        "INSERT INTO roads "
        "(city, osm_way_id, name, highway, source, target, length_m, cost_s, oneway, geom) "
        "VALUES (:city, :osm_way_id, :name, :highway, :source, :target, "
        ":length_m, :cost_s, :oneway, "
        "ST_SetSRID(ST_MakeLine(ST_MakePoint(:x1,:y1), ST_MakePoint(:x2,:y2)), 4326))"
    )
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM roads WHERE city = :c"), {"c": city})
        conn.execute(text("DELETE FROM road_nodes WHERE city = :c"), {"c": city})
        for i in range(0, len(node_rows), 5000):
            conn.execute(node_sql, node_rows[i : i + 5000])
        for i in range(0, len(edges), 5000):
            conn.execute(edge_sql, edges[i : i + 5000])
    print(f"[{city}] loaded {len(node_rows)} nodes, {len(edges)} edges")


def ingest_city(city: str, bbox: tuple[float, float, float, float]) -> tuple[int, int]:
    """Fetch, build, and load one city's road graph. Returns (nodes, edges).

    bbox is (min_lon, min_lat, max_lon, max_lat). Replaces any existing rows for
    that city. Reusable by the management CLI to add an arbitrary area.
    """
    data = _fetch(city, bbox)
    node_rows, edges = _build(city, data)
    _load(city, node_rows, edges)
    return len(node_rows), len(edges)


def main() -> None:
    force = "--force" in sys.argv
    for i, (city, bbox) in enumerate(CITIES.items()):
        if not force and _already_loaded(city):
            print(f"[{city}] already loaded — skipping (use --force to reload)")
            continue
        if i > 0:
            time.sleep(15)  # be polite between Overpass queries
        ingest_city(city, bbox)
    print("done.")


if __name__ == "__main__":
    main()
