"""Unit tests for the A* pathfinder on a tiny hand-built graph (no DB)."""

from app.services.routing_service import _a_star, _totals

# A small graph:  A -- B -- D   (top, longer distance but we control costs)
#                  \       /
#                   \-- C -/     (bottom, C is a shortcut)
# coords are lon/lat-ish; exact values only matter for the A* heuristic.
COORDS = {
    1: (0.0, 0.0),  # A
    2: (0.01, 0.0),  # B
    3: (0.01, -0.01),  # C
    4: (0.02, 0.0),  # D
}
# adjacency: node -> [(neighbor, cost_seconds, length_meters)]
# Top path A-B-D: fast (low seconds) but long. Bottom A-C-D: slow but short.
GRAPH = {
    1: [(2, 10.0, 1000.0), (3, 60.0, 400.0)],
    2: [(1, 10.0, 1000.0), (4, 10.0, 1000.0)],
    3: [(1, 60.0, 400.0), (4, 60.0, 400.0)],
    4: [(2, 10.0, 1000.0), (3, 60.0, 400.0)],
}


def test_time_metric_picks_fast_top_path() -> None:
    path = _a_star(GRAPH, COORDS, 1, 4, "time")
    assert path == [1, 2, 4]  # A-B-D, 20s vs 120s
    dist, secs = _totals(GRAPH, path)
    assert secs == 20.0
    assert dist == 2000.0


def test_distance_metric_picks_short_bottom_path() -> None:
    path = _a_star(GRAPH, COORDS, 1, 3, "distance")
    # Direct A-C is 400 m; A-B-...-C would be far longer.
    assert path == [1, 3]
    dist, _ = _totals(GRAPH, path)
    assert dist == 400.0


def test_full_graph_distance_prefers_shortcut() -> None:
    path = _a_star(GRAPH, COORDS, 1, 4, "distance")
    assert path == [1, 3, 4]  # 800 m total, vs 2000 m for the top
    dist, secs = _totals(GRAPH, path)
    assert dist == 800.0
    assert secs == 120.0


def test_same_start_and_goal() -> None:
    assert _a_star(GRAPH, COORDS, 1, 1, "time") == [1]


def test_unreachable_returns_none() -> None:
    isolated = {**GRAPH, 99: []}
    assert _a_star(isolated, {**COORDS, 99: (5.0, 5.0)}, 1, 99, "time") is None
