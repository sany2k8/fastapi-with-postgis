"""Routing: snap to the graph, run A*, return the route as GeoJSON.

This is the shortest-path half of a maps app. PostGIS stores the graph and does
the nearest-node snapping (KNN); the graph search itself is a hand-written A*
— the same algorithm a real routing engine uses, minus the heavy preprocessing.
"""

from __future__ import annotations

import heapq
import math

from sqlalchemy.orm import Session

from app.repositories import road_repo
from app.schemas.route import (
    CityInfo,
    LineGeometry,
    RouteResponse,
    SnappedPoint,
)

# Fastest road ~80 km/h. Used as the optimistic speed in the A* time heuristic
# so the heuristic never overestimates remaining time (keeps A* correct).
MAX_SPEED_MPS = 80_000 / 3600

Graph = dict[int, list[tuple[int, float, float]]]
Coords = dict[int, tuple[float, float]]

# In-memory cache: a city's graph is loaded from PostGIS once, then reused.
_cache: dict[str, tuple[Graph, Coords]] = {}


class RouteError(Exception):
    """No route could be produced (unknown city or disconnected endpoints)."""


def _graph(city: str) -> tuple[Graph, Coords]:
    if city not in _cache:
        adj, coords = road_repo.load_graph(city)
        if not coords:
            raise RouteError(f"unknown city '{city}'")
        _cache[city] = (adj, coords)
    return _cache[city]


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    (lon1, lat1), (lon2, lat2) = a, b
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(h))


def _a_star(adj: Graph, coords: Coords, start: int, goal: int, metric: str) -> list[int] | None:
    """A* over the graph. metric='time' minimizes seconds, 'distance' meters."""
    goal_xy = coords[goal]

    def heuristic(n: int) -> float:
        straight = _haversine_m(coords[n], goal_xy)
        # Admissible lower bound on the remaining cost in the chosen unit.
        return straight / MAX_SPEED_MPS if metric == "time" else straight

    g: dict[int, float] = {start: 0.0}
    came: dict[int, int] = {}
    open_q: list[tuple[float, float, int]] = [(heuristic(start), 0.0, start)]
    while open_q:
        _, gc, u = heapq.heappop(open_q)
        if u == goal:
            break
        if gc > g.get(u, math.inf):
            continue
        for nbr, cost_s, length_m in adj.get(u, ()):
            step = cost_s if metric == "time" else length_m
            ng = gc + step
            if ng < g.get(nbr, math.inf):
                g[nbr] = ng
                came[nbr] = u
                heapq.heappush(open_q, (ng + heuristic(nbr), ng, nbr))

    if goal != start and goal not in came:
        return None
    path = [goal]
    while path[-1] != start:
        path.append(came[path[-1]])
    path.reverse()
    return path


def _totals(adj: Graph, path: list[int]) -> tuple[float, float]:
    """Sum meters and seconds along a node path (min-cost edge per hop)."""
    dist = time = 0.0
    for u, v in zip(path, path[1:], strict=False):
        best = min(
            (e for e in adj.get(u, ()) if e[0] == v),
            key=lambda e: e[1],
            default=None,
        )
        if best is not None:
            time += best[1]
            dist += best[2]
    return dist, time


def route(
    db: Session,
    city: str,
    from_lat: float,
    from_lng: float,
    to_lat: float,
    to_lng: float,
    metric: str,
) -> RouteResponse:
    adj, coords = _graph(city)

    start_row = road_repo.nearest_node(db, city, from_lat, from_lng)
    end_row = road_repo.nearest_node(db, city, to_lat, to_lng)
    if start_row is None or end_row is None:
        raise RouteError(f"no road nodes for city '{city}'")

    path = _a_star(adj, coords, start_row.id, end_row.id, metric)
    if path is None:
        raise RouteError("no route between those points (disconnected on this network)")

    dist_m, dur_s = _totals(adj, path)
    return RouteResponse(
        city=city,
        cost="time" if metric == "time" else "distance",
        distance_m=round(dist_m, 1),
        duration_s=round(dur_s, 1),
        geometry=LineGeometry(coordinates=[[coords[n][0], coords[n][1]] for n in path]),
        node_count=len(path),
        start=SnappedPoint(
            lat=start_row.lat, lng=start_row.lon, snap_distance_m=round(start_row.snap_m, 1)
        ),
        end=SnappedPoint(
            lat=end_row.lat, lng=end_row.lon, snap_distance_m=round(end_row.snap_m, 1)
        ),
    )


def cities(db: Session) -> list[CityInfo]:
    return [
        CityInfo(
            city=r.city,
            nodes=r.nodes,
            edges=r.edges,
            center_lat=r.center_lat,
            center_lng=r.center_lng,
        )
        for r in road_repo.list_cities(db)
    ]
