"""Data access for places — where the PostGIS lives.

Every spatial filter is an explicit SQL fragment so the query is readable and
you can see exactly which PostGIS function does what:

  * bbox (map viewport)  -> `geom && ST_MakeEnvelope(...)`   [GiST bbox operator]
  * radius search        -> `ST_DWithin(geom::geography, pt, m)`  [meters]
  * distance column      -> `ST_Distance(geom::geography, pt)`    [meters]
  * nearest ordering     -> `ORDER BY geom <-> pt`               [KNN operator]
  * geometry -> map      -> `ST_AsGeoJSON(geom)`

Only static SQL fragments are concatenated; all user values are bound params.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.orm import Session

from app.schemas.place import PlaceFilters

# A WGS84 point built from bound :lng/:lat params — reused across clauses.
_POINT = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)"


def search_places(db: Session, f: PlaceFilters) -> list[Row[Any]]:
    params: dict[str, Any] = {"limit": f.limit}
    where: list[str] = []

    # Distance column (meters) only makes sense when we have a reference point.
    if f.has_point:
        params["lat"] = f.lat
        params["lng"] = f.lng
        distance_select = f", ST_Distance(geom::geography, {_POINT}::geography) AS distance_m"
    else:
        distance_select = ", NULL::float8 AS distance_m"

    # Map viewport: `&&` is the bounding-box overlap operator and is served
    # directly by the GiST index. For point geometries, overlapping the
    # envelope is equivalent to being inside it.
    if f.bbox is not None:
        params.update(min_lon=f.bbox[0], min_lat=f.bbox[1], max_lon=f.bbox[2], max_lat=f.bbox[3])
        where.append("geom && ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)")

    # Radius in meters. Casting to geography makes ST_DWithin measure true
    # spherical meters (vs planar degrees on the raw geometry).
    if f.has_point and f.radius_m is not None:
        params["radius_m"] = f.radius_m
        where.append(f"ST_DWithin(geom::geography, {_POINT}::geography, :radius_m)")

    # Attribute filters.
    if f.category is not None:
        params["category"] = f.category
        where.append("category = :category")
    if f.min_rating is not None:
        params["min_rating"] = f.min_rating
        where.append("rating >= :min_rating")
    if f.max_price is not None:
        params["max_price"] = f.max_price
        where.append("price_level <= :max_price")
    if f.open_24h is not None:
        params["open_24h"] = f.open_24h
        where.append("is_open_24h = :open_24h")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    # Nearest ordering. Gotcha: the plain geometry KNN operator `geom <-> pt`
    # is index-backed but measures *planar degrees*, which diverges from true
    # distance for lon/lat data (a degree of longitude is much shorter than a
    # degree of latitude away from the equator). We order by the geography
    # `<->` instead so the sort agrees with the `distance_m` (meters) we return.
    if f.sort == "nearest" and f.has_point:
        order_sql = f"ORDER BY geom::geography <-> {_POINT}::geography"
    else:
        order_sql = "ORDER BY id"

    sql = text(
        f"""
        SELECT
            id, name, category, rating::float8 AS rating,
            price_level, is_open_24h,
            ST_AsGeoJSON(geom) AS geojson
            {distance_select}
        FROM places
        {where_sql}
        {order_sql}
        LIMIT :limit
        """
    )
    return list(db.execute(sql, params).all())
