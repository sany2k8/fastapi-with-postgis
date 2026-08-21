"""Integration tests against the live PostGIS database.

These assume the database has been seeded (`uv run python -m scripts.seed`).
They assert structural invariants and relative behavior rather than exact
counts, so they stay valid if the seed size changes.
"""

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import engine


def test_radius_query_uses_geography_index() -> None:
    """The metre-based radius query must ride ix_places_geog, not seq-scan.

    This guards the optimization added in migration 0002: without the
    functional geography index the planner falls back to a Seq Scan.
    """
    sql = text(
        """
        EXPLAIN
        SELECT id FROM places
        WHERE ST_DWithin(
            geom::geography,
            ST_SetSRID(ST_MakePoint(-122.416, 37.757), 4326)::geography,
            500
        )
        """
    )
    with engine.connect() as conn:
        plan = "\n".join(row[0] for row in conn.execute(sql))
    assert "ix_places_geog" in plan
    assert "Seq Scan" not in plan


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_places_returns_geojson(client: TestClient) -> None:
    fc = client.get("/api/places", params={"limit": 2000}).json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) > 0
    feat = fc["features"][0]
    assert feat["geometry"]["type"] == "Point"
    assert len(feat["geometry"]["coordinates"]) == 2


def test_bbox_is_a_subset_of_all(client: TestClient) -> None:
    all_count = len(client.get("/api/places", params={"limit": 2000}).json()["features"])
    bbox_count = len(
        client.get(
            "/api/places",
            params={"bbox": "-122.426,37.748,-122.406,37.766", "limit": 2000},
        ).json()["features"]
    )
    assert 0 < bbox_count < all_count


def test_radius_requires_point(client: TestClient) -> None:
    assert client.get("/api/places", params={"radius_m": 500}).status_code == 422


def test_nearest_is_distance_sorted(client: TestClient) -> None:
    fc = client.get(
        "/api/places",
        params={"lat": 37.757, "lng": -122.416, "sort": "nearest", "limit": 10},
    ).json()
    dists = [f["properties"]["distance_m"] for f in fc["features"]]
    assert dists == sorted(dists)


def test_bad_bbox_is_422(client: TestClient) -> None:
    assert client.get("/api/places", params={"bbox": "1,2,3"}).status_code == 422


def test_neighborhoods_are_polygons(client: TestClient) -> None:
    fc = client.get("/api/neighborhoods").json()
    assert len(fc["features"]) == 6
    assert all(f["geometry"]["type"] == "Polygon" for f in fc["features"])


def test_stats_categories_sum_to_place_count(client: TestClient) -> None:
    stats = client.get("/api/neighborhoods/stats").json()
    assert len(stats) == 6
    for s in stats:
        assert s["place_count"] > 0
        assert sum(s["by_category"].values()) == s["place_count"]


def test_missing_neighborhood_is_404(client: TestClient) -> None:
    assert client.get("/api/neighborhoods/9999/places").status_code == 404
