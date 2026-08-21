"""Integration tests for the routing API (assume road data is ingested)."""

from fastapi.testclient import TestClient

# A short trip within Khulna's network.
KHULNA = {
    "city": "khulna",
    "from_lat": 22.845,
    "from_lng": 89.540,
    "to_lat": 22.815,
    "to_lng": 89.560,
}


def test_route_cities_lists_three(client: TestClient) -> None:
    cities = client.get("/api/route/cities").json()
    names = {c["city"] for c in cities}
    assert {"khulna", "dhaka", "chattogram"} <= names
    for c in cities:
        assert c["nodes"] > 0 and c["edges"] > 0


def test_route_returns_linestring(client: TestClient) -> None:
    r = client.get("/api/route", params={**KHULNA, "cost": "time"}).json()
    assert r["geometry"]["type"] == "LineString"
    assert r["node_count"] >= 2
    assert len(r["geometry"]["coordinates"]) == r["node_count"]
    assert r["distance_m"] > 0 and r["duration_s"] > 0


def test_time_route_is_not_slower_than_distance_route(client: TestClient) -> None:
    t = client.get("/api/route", params={**KHULNA, "cost": "time"}).json()
    d = client.get("/api/route", params={**KHULNA, "cost": "distance"}).json()
    # The time-optimized route must not take longer than the distance-optimized
    # one, and the distance route must not be longer than the time route.
    assert t["duration_s"] <= d["duration_s"] + 1e-6
    assert d["distance_m"] <= t["distance_m"] + 1e-6


def test_unknown_city_is_404(client: TestClient) -> None:
    r = client.get(
        "/api/route",
        params={
            "city": "nowhere",
            "from_lat": 22.8,
            "from_lng": 89.5,
            "to_lat": 22.81,
            "to_lng": 89.51,
        },
    )
    assert r.status_code == 404
