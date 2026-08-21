"""Data access for the road graph: load edges/nodes, snap a point to a vertex."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.core.db import engine


def load_graph(
    city: str,
) -> tuple[dict[int, list[tuple[int, float, float]]], dict[int, tuple[float, float]]]:
    """Return (adjacency, coords) for a city.

    adjacency: node_id -> list of (neighbor_id, cost_seconds, length_meters).
    Reverse direction is added unless the edge is one-way.
    coords:    node_id -> (lon, lat), for the A* heuristic and route geometry.
    """
    adj: dict[int, list[tuple[int, float, float]]] = {}
    coords: dict[int, tuple[float, float]] = {}
    with engine.connect() as conn:
        for r in conn.execute(
            text("SELECT id, ST_X(geom) AS lon, ST_Y(geom) AS lat FROM road_nodes WHERE city = :c"),
            {"c": city},
        ):
            coords[r.id] = (r.lon, r.lat)
        for r in conn.execute(
            text("SELECT source, target, cost_s, length_m, oneway FROM roads WHERE city = :c"),
            {"c": city},
        ):
            adj.setdefault(r.source, []).append((r.target, r.cost_s, r.length_m))
            if not r.oneway:
                adj.setdefault(r.target, []).append((r.source, r.cost_s, r.length_m))
    return adj, coords


def nearest_node(db: Session, city: str, lat: float, lng: float) -> Row[Any] | None:
    """Snap a lat/lng to the closest graph vertex using the GiST KNN operator."""
    sql = text(
        """
        SELECT id, ST_X(geom) AS lon, ST_Y(geom) AS lat,
               ST_Distance(geom::geography,
                           ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS snap_m
        FROM road_nodes
        WHERE city = :city
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)
        LIMIT 1
        """
    )
    return db.execute(sql, {"city": city, "lat": lat, "lng": lng}).first()


def list_cities(db: Session) -> list[Row[Any]]:
    """City summaries: node/edge counts and the network's center point."""
    sql = text(
        """
        SELECT n.city,
               n.nodes,
               e.edges,
               ST_X(ST_Centroid(n.extent)) AS center_lng,
               ST_Y(ST_Centroid(n.extent)) AS center_lat
        FROM (
            SELECT city, count(*) AS nodes, ST_Extent(geom) AS extent
            FROM road_nodes GROUP BY city
        ) n
        JOIN (SELECT city, count(*) AS edges FROM roads GROUP BY city) e
          ON e.city = n.city
        ORDER BY n.city
        """
    )
    return list(db.execute(sql).all())
