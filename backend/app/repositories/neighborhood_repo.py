"""Data access for neighborhoods — point-in-polygon and spatial aggregation.

Key PostGIS here:
  * polygon -> map   : `ST_AsGeoJSON(geom)`
  * point-in-polygon : `ST_Contains(neighborhood.geom, place.geom)`
  * choropleth stats : `ST_Contains` join + `GROUP BY` aggregation
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.orm import Session


def list_neighborhoods(db: Session) -> list[Row[Any]]:
    sql = text(
        """
        SELECT id, name, ST_AsGeoJSON(geom) AS geojson
        FROM neighborhoods
        ORDER BY name
        """
    )
    return list(db.execute(sql).all())


def get_neighborhood(db: Session, nid: int) -> Row[Any] | None:
    sql = text("SELECT id, name FROM neighborhoods WHERE id = :nid")
    return db.execute(sql, {"nid": nid}).first()


def places_in_neighborhood(
    db: Session,
    nid: int,
    category: str | None,
    min_rating: float | None,
) -> list[Row[Any]]:
    params: dict[str, Any] = {"nid": nid}
    extra: list[str] = []
    if category is not None:
        params["category"] = category
        extra.append("AND p.category = :category")
    if min_rating is not None:
        params["min_rating"] = min_rating
        extra.append("AND p.rating >= :min_rating")

    sql = text(
        f"""
        SELECT
            p.id, p.name, p.category, p.rating::float8 AS rating,
            p.price_level, p.is_open_24h,
            ST_AsGeoJSON(p.geom) AS geojson,
            NULL::float8 AS distance_m
        FROM places p
        JOIN neighborhoods n ON n.id = :nid
        WHERE ST_Contains(n.geom, p.geom)
        {" ".join(extra)}
        ORDER BY p.id
        """
    )
    return list(db.execute(sql, params).all())


def stats_totals(db: Session) -> list[Row[Any]]:
    # LEFT JOIN so a neighborhood with zero places still appears.
    sql = text(
        """
        SELECT
            n.id, n.name,
            count(p.id) AS place_count,
            COALESCE(round(avg(p.rating), 2), 0)::float8 AS avg_rating
        FROM neighborhoods n
        LEFT JOIN places p ON ST_Contains(n.geom, p.geom)
        GROUP BY n.id, n.name
        ORDER BY n.name
        """
    )
    return list(db.execute(sql).all())


def stats_by_category(db: Session) -> list[Row[Any]]:
    sql = text(
        """
        SELECT n.id AS nid, p.category, count(*) AS cnt
        FROM neighborhoods n
        JOIN places p ON ST_Contains(n.geom, p.geom)
        GROUP BY n.id, p.category
        """
    )
    return list(db.execute(sql).all())
