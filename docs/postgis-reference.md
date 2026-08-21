# PostGIS Functions — A Hands-On Reference

A personal cheat-sheet for the core `ST_*` functions, grouped **A–E** by what
they do. Every query here is runnable and every output shown was produced by
actually running it. It uses a tiny self-contained demo dataset (two throwaway
tables), so you can paste this whole file into `psql` and follow along without
touching the app's data.

- **A. Constructors** — build geometry from numbers or text
- **B. Accessors / Output** — read data back out of a geometry
- **C. Measurement** — distance & the geometry-vs-geography units trap
- **D. Predicates** — true/false spatial relationships (the filters)
- **E. Derivation** — make new geometry from existing geometry

> **Two rules that explain 90% of PostGIS confusion**
> 1. **Every geometry carries an SRID** (a coordinate system). We use **4326** =
>    WGS84 lon/lat, the GPS standard. Coordinates are always **(longitude,
>    latitude)** — X then Y, i.e. lon first.
> 2. **Raw `geometry` measures in the SRID's units.** For 4326 that's *degrees*,
>    which is useless on the ground. Cast to **`::geography`** to measure in
>    **meters**.

---

## Setup — the demo dataset

Run this once. It creates 5 places (points) and 1 zone (polygon). Three places
sit inside the zone, two are outside — chosen so the predicate examples have
clear yes/no answers.

```sql
DROP TABLE IF EXISTS demo_places, demo_zones;

CREATE TABLE demo_places (
  id   serial PRIMARY KEY,
  name text,
  kind text,
  geom geometry(Point, 4326)
);
CREATE TABLE demo_zones (
  id   serial PRIMARY KEY,
  name text,
  geom geometry(Polygon, 4326)
);

INSERT INTO demo_places (name, kind, geom) VALUES
  ('Corner Cafe', 'cafe',       ST_SetSRID(ST_MakePoint(-122.4000, 37.7900), 4326)),
  ('Book Shop',   'shop',       ST_SetSRID(ST_MakePoint(-122.4010, 37.7905), 4326)),
  ('Pizza Place', 'restaurant', ST_SetSRID(ST_MakePoint(-122.3990, 37.7895), 4326)),
  ('Far Bar',     'bar',        ST_SetSRID(ST_MakePoint(-122.4050, 37.7930), 4326)),
  ('City Park',   'park',       ST_SetSRID(ST_MakePoint(-122.3950, 37.7860), 4326));

INSERT INTO demo_zones (name, geom) VALUES
  ('Downtown Zone',
   ST_GeomFromText(
     'POLYGON((-122.4020 37.7885, -122.3980 37.7885, -122.3980 37.7910, -122.4020 37.7910, -122.4020 37.7885))',
     4326));
```

Mental picture (the zone is the box; `Corner Cafe` is the reference point ★):

```
  lat
37.793 |            • Far Bar
       |    ┌────────────────────┐   ← Downtown Zone (polygon)
37.790 |    │   ★Cafe  •Book     │
       |    │       •Pizza       │
37.788 |    └────────────────────┘
37.786 |                              • City Park
       +----------------------------------------- lon
        -122.405   -122.400   -122.395
```

---

## A. Constructors — build geometry

Geometry has to come from somewhere: from coordinate numbers, or parsed from
text.

### `ST_MakePoint(x, y)` + `ST_SetSRID(geom, srid)`
Builds a point from **lon, lat**, then stamps the coordinate system on it.
`ST_MakePoint` alone makes an SRID-less point (SRID 0); you almost always wrap
it in `ST_SetSRID`.

```sql
SELECT ST_AsText(ST_SetSRID(ST_MakePoint(-122.4000, 37.7900), 4326)) AS point;
```
```
        point
---------------------
 POINT(-122.4 37.79)
```
> This exact pattern is how the app builds the "user location" point in every
> radius/nearest query.

### `ST_GeomFromText(wkt, srid)`
Parses **WKT** (Well-Known Text) — the human-readable geometry format — into a
geometry. Works for any type: `POINT`, `LINESTRING`, `POLYGON`, etc.

```sql
SELECT ST_AsText(ST_GeomFromText('LINESTRING(-122.402 37.789, -122.398 37.791)', 4326)) AS line;
```
```
                    line
---------------------------------------------
 LINESTRING(-122.402 37.789,-122.398 37.791)
```
> The app's seed uses the `POLYGON((...))` form to insert neighborhood shapes.

### `ST_MakeEnvelope(minLon, minLat, maxLon, maxLat, srid)`
Builds a **rectangle** from its corners. This is the map viewport / bounding box.

```sql
SELECT ST_AsText(ST_MakeEnvelope(-122.402, 37.7885, -122.398, 37.791, 4326)) AS box;
```
```
                                     box
-----------------------------------------------------------------------------------------------
 POLYGON((-122.402 37.7885,-122.402 37.791,-122.398 37.791,-122.398 37.7885,-122.402 37.7885))
```
> Paired with the `&&` operator (`geom && ST_MakeEnvelope(...)`), this is the
> fast, GiST-index-backed "what's in the current map view" query.

---

## B. Accessors / Output — read geometry back

### `ST_X`, `ST_Y`, `ST_SRID`, `ST_GeometryType`
Pull the pieces out of a geometry.

```sql
SELECT name,
       ST_X(geom) AS lon, ST_Y(geom) AS lat,
       ST_SRID(geom) AS srid, ST_GeometryType(geom) AS gtype
FROM demo_places ORDER BY id;
```
```
    name     |   lon    |   lat   | srid |  gtype
-------------+----------+---------+------+----------
 Corner Cafe |   -122.4 |   37.79 | 4326 | ST_Point
 Book Shop   | -122.401 | 37.7905 | 4326 | ST_Point
 Pizza Place | -122.399 | 37.7895 | 4326 | ST_Point
 Far Bar     | -122.405 |  37.793 | 4326 | ST_Point
 City Park   | -122.395 |  37.786 | 4326 | ST_Point
```
- **`ST_X` / `ST_Y`** — longitude / latitude of a point (only valid on points).
- **`ST_SRID`** — the coordinate-system id. Handy in tests to assert everything
  is 4326.
- **`ST_GeometryType`** — `ST_Point`, `ST_Polygon`, `ST_LineString`, …

### `ST_AsText` vs `ST_AsGeoJSON`
Two ways to serialize a geometry: WKT for humans, GeoJSON for web maps.

```sql
SELECT name, ST_AsText(geom) AS wkt, ST_AsGeoJSON(geom) AS geojson
FROM demo_places WHERE name = 'Corner Cafe';
```
```
    name     |         wkt         |                    geojson
-------------+---------------------+-----------------------------------------------
 Corner Cafe | POINT(-122.4 37.79) | {"type":"Point","coordinates":[-122.4,37.79]}
```
> `ST_AsGeoJSON` is what the API returns for the frontend — Leaflet reads GeoJSON
> directly. Note GeoJSON coordinates are `[lon, lat]`; Leaflet wants `[lat, lng]`,
> so the frontend flips them at the boundary.

---

## C. Measurement — distance, and the units trap

### `ST_Distance` — geometry (degrees) vs geography (meters)
The single most important lesson in PostGIS. The **same function** returns
different units depending on the type.

```sql
WITH ref AS (SELECT ST_SetSRID(ST_MakePoint(-122.4000, 37.7900), 4326) AS g)
SELECT p.name,
       round(ST_Distance(p.geom, ref.g)::numeric, 6)                      AS dist_degrees,
       round(ST_Distance(p.geom::geography, ref.g::geography)::numeric,1) AS dist_meters
FROM demo_places p, ref
ORDER BY p.geom::geography <-> ref.g::geography;   -- <-> = nearest-first (KNN)
```
```
    name     | dist_degrees | dist_meters
-------------+--------------+-------------
 Corner Cafe |     0.000000 |         0.0
 Book Shop   |     0.001118 |       104.1
 Pizza Place |     0.001118 |       104.1
 Far Bar     |     0.005831 |       552.1
 City Park   |     0.006403 |       625.4
```
- **`ST_Distance(a, b)`** on raw `geometry` → distance in the SRID's units. For
  4326 that's **degrees** — almost never what you want.
- Cast both sides to **`::geography`** → **true meters** on the Earth's surface.
- **`<->`** in `ORDER BY` is the **K-Nearest-Neighbour operator**: "sort rows by
  closeness to this point." On a GiST index it can return nearest rows without
  scanning the whole table.

> **The gotcha that bit this project:** `geom <-> pt` (planar, degrees) can sort
> *differently* from `geom::geography <-> pt::geography` (meters), because a
> degree of longitude is shorter than a degree of latitude away from the equator.
> Always compare distances in the **same** unit you present them in.

---

## D. Predicates — true/false relationships (your filters)

These return booleans and are what `WHERE` clauses are built from. They are all
**GiST-index accelerated**.

### `ST_DWithin(a, b, distance)` — radius search
"Are these within `distance` of each other?" On geography, `distance` is meters.
This is the right way to do radius search — never `ST_Distance(...) < 400`,
which uses the index far less effectively.

```sql
WITH ref AS (SELECT ST_SetSRID(ST_MakePoint(-122.4000, 37.7900), 4326)::geography AS g)
SELECT p.name,
       round(ST_Distance(p.geom::geography, ref.g)::numeric,1) AS meters,
       ST_DWithin(p.geom::geography, ref.g, 400)               AS within_400m
FROM demo_places p, ref ORDER BY meters;
```
```
    name     | meters | within_400m
-------------+--------+-------------
 Corner Cafe |    0.0 | t
 Book Shop   |  104.1 | t
 Pizza Place |  104.1 | t
 Far Bar     |  552.1 | f
 City Park   |  625.4 | f
```

### `ST_Contains(A, B)` vs `ST_Within(B, A)` — point-in-polygon
The **same test with the arguments swapped**. "Does polygon A contain geometry
B?" is identical to "Is B within A?" — which is why the two columns below match.

```sql
SELECT p.name,
       ST_Contains(z.geom, p.geom) AS zone_contains_place,
       ST_Within(p.geom, z.geom)   AS place_within_zone
FROM demo_places p, demo_zones z ORDER BY p.id;
```
```
    name     | zone_contains_place | place_within_zone
-------------+---------------------+-------------------
 Corner Cafe | t                   | t
 Book Shop   | t                   | t
 Pizza Place | t                   | t
 Far Bar     | f                   | f
 City Park   | f                   | f
```
> This is exactly how the app answers "show me the places in this neighborhood":
> `ST_Contains(neighborhood.geom, place.geom)`.

### `ST_Intersects(a, b)` — do they touch/overlap at all?
Looser than Contains: true if they share *any* point. Works between any types —
here, does a line cross the zone?

```sql
SELECT ST_Intersects(z.geom,
         ST_GeomFromText('LINESTRING(-122.401 37.780, -122.399 37.795)', 4326)) AS line_crosses_zone
FROM demo_zones z;
```
```
 line_crosses_zone
-------------------
 t
```
> **Predicate family to remember:** `ST_Contains` (fully inside), `ST_Within`
> (inside, args flipped), `ST_Covers` (inside *including* the boundary),
> `ST_Intersects` (touch at all), `ST_Overlaps`, `ST_Crosses`, `ST_Disjoint`
> (share nothing), `ST_Equals`.

---

## E. Derivation — make new geometry from old

These return **new geometry** (or a measurement of it) rather than a boolean.

### `ST_Centroid`, `ST_Area`, `ST_Perimeter`
The center point, area, and boundary length of a polygon. Cast to `::geography`
for real-world m² / m.

```sql
SELECT name,
       ST_AsText(ST_Centroid(geom))                       AS centroid,
       round(ST_Area(geom::geography)::numeric)           AS area_m2,
       round((ST_Area(geom::geography)/1e6)::numeric, 4)  AS area_km2,
       round(ST_Perimeter(geom::geography)::numeric)      AS perimeter_m
FROM demo_zones;
```
```
     name      |             centroid             | area_m2 | area_km2 | perimeter_m
---------------+----------------------------------+---------+----------+-------------
 Downtown Zone | POINT(-122.4 37.789750000000005) |   97765 |   0.0978 |        1260
```
- **`ST_Centroid`** — the polygon's center of mass; great for placing a label.
- **`ST_Area`** — area (m² on geography). Our little zone is ~0.098 km².
- **`ST_Perimeter`** — boundary length (m). (For lines, use **`ST_Length`**.)

### `ST_Buffer(geom, distance)` — grow a shape outward
Turns a point into a **circle** of the given radius (meters on geography). Below
we build a 250 m circle around the cafe and count places inside it.

```sql
WITH circle AS (
  SELECT ST_Buffer(ST_SetSRID(ST_MakePoint(-122.4000, 37.7900), 4326)::geography, 250)::geometry AS g
)
SELECT count(*) AS places_in_250m_buffer
FROM demo_places p, circle c
WHERE ST_Contains(c.g, p.geom);
```
```
 places_in_250m_buffer
-----------------------
                     3
```
> For a simple radius *filter*, prefer `ST_DWithin` (no geometry built).
> Reach for `ST_Buffer` when you actually need the circle/zone **as a shape** —
> to draw it, store it, or intersect other things with it.

### `ST_Transform(geom, srid)` — reproject to another coordinate system
Converts coordinates between reference systems (looked up in `spatial_ref_sys`).
Here: 4326 lon/lat degrees → **3857 Web Mercator meters**, the system slippy-map
tiles use.

```sql
SELECT name, ST_AsText(ST_SnapToGrid(ST_Transform(geom, 3857), 1)) AS web_mercator
FROM demo_places WHERE name = 'Corner Cafe';
```
```
    name     |       web_mercator
-------------+--------------------------
 Corner Cafe | POINT(-13625506 4549802)
```
> `(-122.4, 37.79)` degrees becomes `(-13.6M, 4.5M)` meters. `ST_SnapToGrid` just
> rounds the output here so it prints cleanly.

---

## Cleanup

```sql
DROP TABLE IF EXISTS demo_places, demo_zones;
```

---

## One-page recap

| Group | Function | What it does | Units gotcha |
|---|---|---|---|
| **A** Build | `ST_MakePoint(x,y)` | point from lon, lat | wrap in `ST_SetSRID` |
| | `ST_SetSRID(g, 4326)` | stamp coordinate system | — |
| | `ST_GeomFromText(wkt, srid)` | parse WKT text | — |
| | `ST_MakeEnvelope(…, srid)` | rectangle / bbox | — |
| **B** Read | `ST_X` / `ST_Y` | lon / lat of a point | points only |
| | `ST_SRID`, `ST_GeometryType` | coordinate system, type | — |
| | `ST_AsText` / `ST_AsGeoJSON` | WKT / GeoJSON output | GeoJSON is `[lon,lat]` |
| **C** Measure | `ST_Distance(a,b)` | distance between | cast `::geography` for meters |
| | `<->` | nearest-neighbour sort | planar ≠ metric ordering |
| **D** Relate | `ST_DWithin(a,b,d)` | within distance? (radius) | meters on geography |
| | `ST_Contains` / `ST_Within` | fully inside? (flipped args) | GiST-indexed |
| | `ST_Intersects` | touch/overlap at all? | GiST-indexed |
| **E** Derive | `ST_Centroid` | center point | — |
| | `ST_Area` / `ST_Perimeter` / `ST_Length` | size measures | `::geography` for m²/m |
| | `ST_Buffer(g, d)` | grow into a circle/zone | meters on geography |
| | `ST_Transform(g, srid)` | reproject | needs both SRIDs in `spatial_ref_sys` |
