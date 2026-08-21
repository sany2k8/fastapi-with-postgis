"""Seed the database with synthetic Places Finder data around San Francisco.

Reproducible (fixed seeds). Idempotent: truncates and re-inserts on every run.

Two things worth noticing here for PostGIS learning:

  * Neighborhood polygons are inserted as WKT (``POLYGON((lon lat, ...))``).
  * Places are scattered *inside* those polygons using PostGIS's own
    ``ST_GeneratePoints(geom, n, seed)`` — the database generates the random
    points for us, so every place is guaranteed to fall within a neighborhood
    (which makes the M4 point-in-polygon stats meaningful). A handful of extra
    places are scattered city-wide so some fall *outside* every neighborhood.

Run:  uv run python -m scripts.seed
"""

from __future__ import annotations

import random

from faker import Faker
from geoalchemy2.elements import WKTElement
from sqlalchemy import text

from app.core.db import SessionLocal
from app.models.neighborhood import Neighborhood
from app.models.place import Place

SRID = 4326
RANDOM_SEED = 42

fake = Faker()
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# --- San Francisco neighborhoods as simple rectangular polygons (lon, lat) ----
# Coordinates are approximate but placed over the real areas. Ring is closed
# (first point repeated last), counter-clockwise.
NEIGHBORHOODS: dict[str, tuple[float, float, float, float]] = {
    # name: (min_lon, min_lat, max_lon, max_lat)
    "Mission": (-122.4260, 37.7480, -122.4060, 37.7660),
    "SoMa": (-122.4090, 37.7700, -122.3900, 37.7850),
    "North Beach": (-122.4170, 37.7960, -122.4020, 37.8080),
    "Marina": (-122.4470, 37.7980, -122.4270, 37.8080),
    "Castro": (-122.4400, 37.7550, -122.4270, 37.7680),
    # Top edge kept below North Beach's bottom (37.7960) so areas stay disjoint.
    "Financial District": (-122.4050, 37.7880, -122.3930, 37.7955),
}

# How many places to scatter inside each neighborhood.
PLACES_PER_NEIGHBORHOOD = 75
# Extra places scattered across the whole city (some land outside all polygons).
CITYWIDE_PLACES = 60
CITY_BBOX = (-122.4600, 37.7400, -122.3850, 37.8120)  # min_lon,min_lat,max_lon,max_lat

CATEGORIES = ["cafe", "restaurant", "shop", "park", "bar", "hotel"]
# Relative frequency — cafes/restaurants common, parks/hotels rarer.
CATEGORY_WEIGHTS = [0.24, 0.28, 0.20, 0.08, 0.14, 0.06]

NAME_TEMPLATES: dict[str, list[str]] = {
    "cafe": ["{w} Coffee", "Cafe {w}", "{w} Roasters", "The {w} Bean"],
    "restaurant": ["{w} Kitchen", "{w} Bistro", "Trattoria {w}", "{w} & Sons"],
    "shop": ["{w} Market", "{w} Goods", "{w} Supply Co.", "The {w} Store"],
    "park": ["{w} Park", "{w} Gardens", "{w} Square", "{w} Green"],
    "bar": ["The {w} Tap", "{w} Tavern", "Bar {w}", "{w} & Rye"],
    "hotel": ["Hotel {w}", "The {w} Inn", "{w} Suites", "{w} Lodge"],
}


def polygon_wkt(bbox: tuple[float, float, float, float]) -> str:
    min_lon, min_lat, max_lon, max_lat = bbox
    ring = [
        (min_lon, min_lat),
        (max_lon, min_lat),
        (max_lon, max_lat),
        (min_lon, max_lat),
        (min_lon, min_lat),
    ]
    coords = ", ".join(f"{lon} {lat}" for lon, lat in ring)
    return f"POLYGON(({coords}))"


def _make_name(category: str) -> str:
    word = fake.word().capitalize()
    template = random.choice(NAME_TEMPLATES[category])
    return template.format(w=word)


def _random_attributes(category: str) -> dict[str, object]:
    # Ratings skew high and realistic (3.0–5.0), one decimal.
    rating = round(random.uniform(3.0, 5.0), 1)
    price_level = random.randint(1, 4)
    # Only some categories are ever open 24h, and rarely.
    is_open_24h = category in {"cafe", "shop", "hotel"} and random.random() < 0.1
    return {"rating": rating, "price_level": price_level, "is_open_24h": is_open_24h}


def generate_points_in_polygon(
    session, poly_wkt: str, n: int, seed: int
) -> list[tuple[float, float]]:
    """Ask PostGIS to scatter ``n`` random points inside the polygon."""
    rows = session.execute(
        text(
            """
            SELECT ST_X(g.geom) AS lon, ST_Y(g.geom) AS lat
            FROM (
                SELECT (ST_Dump(
                    ST_GeneratePoints(ST_GeomFromText(:wkt, :srid), :n, :seed)
                )).geom AS geom
            ) AS g
            """
        ),
        {"wkt": poly_wkt, "srid": SRID, "n": n, "seed": seed},
    ).all()
    return [(r.lon, r.lat) for r in rows]


def build_random_place(lon: float, lat: float) -> Place:
    category = random.choices(CATEGORIES, weights=CATEGORY_WEIGHTS, k=1)[0]
    attrs = _random_attributes(category)
    return Place(
        name=_make_name(category),
        category=category,
        geom=WKTElement(f"POINT({lon} {lat})", srid=SRID),
        **attrs,
    )


def seed() -> None:
    session = SessionLocal()
    try:
        # Idempotent reset. RESTART IDENTITY resets the id sequences.
        session.execute(text("TRUNCATE places, neighborhoods RESTART IDENTITY"))

        # 1) Neighborhood polygons.
        for name, bbox in NEIGHBORHOODS.items():
            session.add(Neighborhood(name=name, geom=WKTElement(polygon_wkt(bbox), srid=SRID)))
        session.flush()

        # 2) Places inside each neighborhood (PostGIS generates the points).
        places: list[Place] = []
        for i, bbox in enumerate(NEIGHBORHOODS.values()):
            pts = generate_points_in_polygon(
                session, polygon_wkt(bbox), PLACES_PER_NEIGHBORHOOD, seed=RANDOM_SEED + i
            )
            places.extend(build_random_place(lon, lat) for lon, lat in pts)

        # 3) Extra city-wide places (Python-side random within the city bbox).
        min_lon, min_lat, max_lon, max_lat = CITY_BBOX
        for _ in range(CITYWIDE_PLACES):
            lon = random.uniform(min_lon, max_lon)
            lat = random.uniform(min_lat, max_lat)
            places.append(build_random_place(lon, lat))

        session.add_all(places)
        session.commit()

        print(
            f"Seeded {len(NEIGHBORHOODS)} neighborhoods and {len(places)} places "
            f"({len(NEIGHBORHOODS) * PLACES_PER_NEIGHBORHOOD} inside + "
            f"{CITYWIDE_PLACES} city-wide)."
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
