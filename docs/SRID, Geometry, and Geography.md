# PostGIS: Understanding SRID, Geometry, and Geography

## 1. The Core Mental Model

The key idea is:

> **SRID and `geometry`/`geography` answer different questions. They don't compete with each other.**

Think of spatial data as having **three layers of meaning**:

```text
POINT(90.4125 23.8103)
        │
        ├── SRID 4326
        │      "What coordinate reference system are these numbers in?"
        │
        └── geometry / geography
               "How should PostGIS model and calculate this spatial object?"
```

---

# 2. `4326` Means the Same Thing in Both

This is important.

These:

```sql
GEOMETRY(Point, 4326)
```

and:

```sql
GEOGRAPHY(Point, 4326)
```

**both use EPSG:4326 = WGS84.**

`4326` does **not** mean something different because the type changed.

The difference is how the coordinates are used.

```text
GEOMETRY(Point, 4326)
        │
        ├── CRS: WGS84
        └── Model: planar geometry

GEOGRAPHY(Point, 4326)
        │
        ├── CRS: WGS84
        └── Model: Earth-based geography
```

So the important distinction is:

> The data type adds another layer of meaning, but it doesn't change the meaning of SRID 4326.

---

# 3. What Does SRID Mean?

**SRID** stands for **Spatial Reference System Identifier**.

It tells PostGIS:

> **"What coordinate reference system are these coordinates using?"**

For example:

```text
POINT(90.4125 23.8103)
```

by itself is just two numbers.

With:

```text
SRID = 4326
```

PostGIS knows that these numbers are interpreted according to **WGS84**.

Conceptually:

```text
POINT(90.4125 23.8103)
        +
    SRID 4326
        ↓
WGS84 longitude / latitude
```

Therefore:

```text
90.4125 → longitude
23.8103 → latitude
```

---

# 4. SRID Is Like a Unit / Coordinate-System Label

A useful analogy is temperature.

Imagine:

```text
100
```

What does it mean?

Could be:

```text
100 °C
100 °F
```

The number alone isn't enough.

Similarly:

```text
90.4125
```

could mean:

```text
90.4125 degrees longitude
```

or:

```text
90.4125 meters
```

depending on the coordinate reference system.

So:

```text
NUMBER
  +
CRS
  =
meaningful coordinate
```

---

# 5. What Happens If We Use Different SRIDs?

Suppose we have:

```text
Point A
SRID 4326
```

and:

```text
Point B
SRID 3857
```

These two points may represent the same physical location, but their numerical coordinates are expressed differently.

For example:

```text
EPSG:4326
POINT(90.4125 23.8103)
```

means approximately:

```text
longitude = 90.4125
latitude  = 23.8103
```

while Web Mercator:

```text
EPSG:3857
POINT(10058500 2720000)
```

uses projected X/Y coordinates whose units are approximately meters.

So:

```text
4326
  ↓
90.4125, 23.8103
  ↓
longitude / latitude
  ↓
degrees
```

while:

```text
3857
  ↓
10058500, 2720000
  ↓
projected X / Y
  ↓
meters
```

---

# 6. What Happens If You Mix SRIDs?

Suppose:

```text
Point A
SRID 4326

Point B
SRID 3857
```

and you try:

```sql
SELECT ST_Distance(point_a, point_b);
```

PostGIS generally won't let you blindly perform the operation.

You'll get an error along the lines of:

```text
Operation on mixed SRID geometries
```

That's good!

Because otherwise PostGIS might calculate something completely meaningless.

You need to transform one into the other's CRS.

For example:

```sql
ST_Transform(point_a, 3857)
```

Then:

```text
Point A
4326
  │
  │ ST_Transform()
  ▼
3857

Point B
3857
```

Now both are using the same CRS and can be compared as geometries.

---

# 7. `ST_SetSRID()` vs `ST_Transform()`

This is one of the most important PostGIS concepts.

Imagine you have:

```text
POINT(90.4125 23.8103)
SRID 4326
```

You want EPSG:3857.

## Wrong: `ST_SetSRID()`

```sql
ST_SetSRID(point, 3857)
```

This does **not** convert the coordinates.

You would end up with:

```text
POINT(90.4125 23.8103)
SRID 3857
```

You're essentially telling PostGIS:

> "These numbers are already Web Mercator."

But they aren't.

---

## Correct: `ST_Transform()`

```sql
ST_Transform(point, 3857)
```

Now PostGIS actually calculates new coordinates:

```text
POINT(90.4125 23.8103)
SRID 4326

          │
          │ ST_Transform()
          ▼

POINT(10058xxx 2720xxx)
SRID 3857
```

Therefore:

```text
ST_SetSRID()
    =
"Tell PostGIS what CRS these existing numbers are already in."

ST_Transform()
    =
"Convert these coordinates into another CRS."
```

---

# 8. Geometry: The Flat / Planar Model

Imagine putting your coordinates onto a flat piece of paper:

```text
             Y
             ↑
             |
             |
             |       ● Dhaka
             |
             |
             +----------------------→ X
```

That's essentially the mental model for `geometry`.

Coordinates exist in a **Cartesian/planar coordinate system**.

For example:

```text
POINT(90.4125 23.8103)
```

means:

```text
X = 90.4125
Y = 23.8103
```

PostGIS performs geometric calculations on that coordinate plane.

The important idea is:

> **Geometry treats the spatial world as a coordinate plane.**

It doesn't inherently mean "bad" or "inaccurate."

---

# 9. Geography: The Earth-Based Model

`geography` says:

> "These coordinates represent positions on Earth."

Instead of imagining:

```text
        flat paper

      ● -------- ●
```

think:

```text
             Earth
          .-----------.
       .-'             '-.
      /                   \
     |       ●        ●    |
      \                   /
       '-._____________.-'
```

The Earth is curved.

So when you calculate distances, geography can account for the Earth's shape.

The important idea is:

> **Geography treats coordinates as locations on Earth rather than simply points on a flat Cartesian plane.**

---

# 10. The Biggest Practical Difference: Distance

Suppose:

```text
Dhaka
POINT(90.4125 23.8103)

Chittagong
POINT(91.7832 22.3569)
```

You want:

> How far is Dhaka from Chittagong?

With `geometry`:

```sql
ST_Distance(...)
```

you're doing a planar calculation using the coordinate system.

With `geography`:

```sql
ST_Distance(...)
```

you're asking:

> "What's the distance between these two positions on Earth?"

And the result is in **meters**.

That's why `geography` is very convenient for GPS/location applications.

---

# 11. Geometry Does Not Always Mean Degrees

This is an important correction to a common misunderstanding.

People sometimes learn:

> "Geometry uses degrees and geography uses meters."

That's **not correct**.

Geometry uses whatever units its CRS defines.

For example:

```text
Geometry + EPSG:4326
        ↓
coordinates are degrees
```

while:

```text
Geometry + a suitable projected CRS
        ↓
coordinates might be meters
```

For example, you could transform your WGS84 coordinates into a projected CRS where coordinates are expressed in meters:

```text
WGS84
90.4125, 23.8103
       │
       │ ST_Transform()
       ▼
Projected CRS
~10,000,000, ~2,700,000 meters
```

Then geometry can perform planar calculations in meters.

Therefore:

> **Geometry is not inherently a degree-based data type. Its coordinate units depend on the CRS.**

---

# 12. Why Use Geography?

Because you don't always want to worry about choosing a suitable projected CRS.

Suppose your application receives:

```json
{
    "latitude": 23.8103,
    "longitude": 90.4125
}
```

This is normal GPS data.

You can store:

```sql
location GEOGRAPHY(Point, 4326)
```

Then:

```sql
ST_Distance(location, another_location)
```

gives you a distance in **meters**.

That's extremely convenient.

---

# 13. Restaurant API Example

Imagine you're building a **restaurant finder API** with FastAPI + PostgreSQL/PostGIS.

Your table might be:

```sql
CREATE TABLE restaurants (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    location GEOGRAPHY(Point, 4326) NOT NULL
);
```

Insert:

```sql
INSERT INTO restaurants (name, location)
VALUES (
    'Restaurant A',
    ST_SetSRID(
        ST_MakePoint(90.4125, 23.8103),
        4326
    )::geography
);
```

Notice the order:

```text
longitude, latitude
```

not:

```text
latitude, longitude
```

Then you can ask:

> Find restaurants within 5 km of this location.

Conceptually:

```sql
SELECT
    name,
    ST_Distance(
        location,
        ST_SetSRID(
            ST_MakePoint(90.40, 23.80),
            4326
        )::geography
    ) AS distance_meters
FROM restaurants
WHERE ST_DWithin(
    location,
    ST_SetSRID(
        ST_MakePoint(90.40, 23.80),
        4326
    )::geography,
    5000
)
ORDER BY distance_meters;
```

Here:

```text
4326
 │
 └── tells PostGIS the coordinates are WGS84

geography
 │
 └── tells PostGIS to perform Earth-based calculations

5000
 │
 └── means 5,000 meters
```

---

# 14. What Happens With Geometry + 4326?

Suppose instead you have:

```sql
location GEOMETRY(Point, 4326)
```

Then:

```sql
ST_DWithin(
    location,
    user_location,
    5000
)
```

does **not** mean 5 km.

Because EPSG:4326 uses:

```text
degrees
```

So `5000` means:

```text
5000 degrees
```

which is obviously useless.

You'd have to either:

### Option A — Transform to a projected CRS

```text
WGS84 geometry
      ↓
ST_Transform()
      ↓
meter-based geometry
      ↓
ST_DWithin(..., 5000)
```

or:

### Option B — Cast to geography

```sql
location::geography
```

and perform the distance operation using meters.

---

# 15. Why Would Anyone Use Geometry?

Because `geometry` is extremely powerful for **planar spatial operations**.

For example:

### Buildings

```text
POLYGON(...)
```

### Roads

```text
LINESTRING(...)
```

### Land boundaries

```text
POLYGON(...)
```

### City boundaries

```text
POLYGON(...)
```

### Spatial intersections

```sql
ST_Intersects(a, b)
```

### Polygon containment

```sql
ST_Contains(city, restaurant)
```

### Geometry operations

```sql
ST_Buffer(...)
ST_Intersection(...)
ST_Union(...)
ST_Difference(...)
```

For many GIS workloads, `geometry` is the normal choice.

---

# 16. Geometry vs Geography: Simple Analogy

Think about a **map**.

## Geometry

Imagine printing a map onto a huge sheet of paper.

```text
      ┌───────────────────────┐
      │                       │
      │  Dhaka ●              │
      │             ● Chittagong
      │                       │
      └───────────────────────┘
```

You perform calculations on this flat map.

## Geography

Imagine putting the locations onto a **globe**.

```text
             _______
          .-'       '-.
        .'             '.
       /   ●       ●     \
       \                 /
        '.             .'
          '-._______.-'
```

You're treating them as locations on Earth.

---

# 17. Geography Is Not "More Accurate Geometry"

Another common misunderstanding is:

```text
geometry = bad
geography = good
```

That's not correct.

Instead:

```text
geometry
   ↓
planar/cartesian spatial model
   ↓
excellent for GIS and projected spatial calculations


geography
   ↓
Earth-based spatial model
   ↓
excellent for global/GPS distance and location calculations
```

Both are useful.

---

# 18. Geography Is Not the Same as SRID 4326

This is another important distinction.

Don't think:

```text
4326 = geography
```

That's false.

You can have:

```sql
GEOMETRY(Point, 4326)
```

and:

```sql
GEOGRAPHY(Point, 4326)
```

Both use:

```text
EPSG:4326 = WGS84
```

But:

```text
GEOMETRY
    ↓
planar spatial model
```

while:

```text
GEOGRAPHY
    ↓
Earth-based spatial model
```

---

# 19. Geography and SRID 4326

`geography` is specifically designed around **geodetic/Earth-based coordinates**, and PostGIS supports a more limited set of CRS choices for geography than it does for geometry.

In normal applications, you'll commonly see:

```sql
GEOGRAPHY(Point, 4326)
```

because GPS data naturally arrives as:

```text
longitude
latitude
```

So for a backend application, this is very intuitive:

```text
GPS
 │
 ▼
longitude + latitude
 │
 ▼
WGS84 / EPSG:4326
 │
 ▼
GEOGRAPHY(Point, 4326)
 │
 ▼
Earth-aware distance
 │
 ▼
meters
```

---

# 20. Important Correction: Geography Units

A previous simplification might make it sound like:

> Geography → units are meters.

The more precise statement is:

> **Geography performs its supported spatial calculations using Earth-based/geodetic semantics, and distance/area results are commonly returned in meters.**

It's not that **SRID 4326 itself means meters**.

In fact:

```text
4326
```

is still a latitude/longitude CRS whose coordinate values are in **degrees**.

The geography type is what allows PostGIS to interpret those coordinates as positions on Earth for geodetic calculations.

---

# 21. The Complete Mental Model

Think of spatial data as:

```text
                       Spatial Object
                            │
                 POINT(90.4125 23.8103)
                            │
                 ┌──────────┴──────────┐
                 │                     │
             GEOMETRY              GEOGRAPHY
                 │                     │
           planar model           Earth model
                 │                     │
                 └──────────┬──────────┘
                            │
                       SRID = 4326
                            │
                            ▼
                    WGS84 coordinate
                    reference system
```

So:

### SRID answers:

> **"Where does this coordinate system come from and what do its numbers represent?"**

### Geometry/geography answers:

> **"What spatial model should PostGIS use for this object?"**

---

# 22. Complete Picture

Here's the complete relationship:

```text
                 Spatial Data
                      │
                      ▼
             POINT(90.4125 23.8103)
                      │
                      │
             ┌────────┴────────┐
             │                 │
         GEOMETRY          GEOGRAPHY
             │                 │
          "flat"             "Earth"
             │                 │
             └────────┬────────┘
                      │
                     SRID
                      │
            "Which coordinate
             reference system?"
                      │
             ┌────────┴────────┐
             │                 │
           4326              3857
             │                 │
          WGS84             Web Mercator
             │                 │
       lon/lat degrees    projected X/Y
```

Therefore:

```text
GEOMETRY / GEOGRAPHY
        +
      SRID
        +
    coordinates
        ↓
complete spatial meaning
```

---

# 23. The Three Things to Remember

If you remember only three things, remember these:

### 1. SRID

```text
SRID = 4326
```

means:

> **"These coordinates use the WGS84 coordinate reference system."**

It gives the coordinate numbers their CRS context.

---

### 2. Geometry

```sql
GEOMETRY(Point, 4326)
```

means:

> **"This is a planar geometry whose coordinates use WGS84."**

The coordinate units are determined by the CRS.

If the CRS is 4326, the coordinates are degrees.

If you transform it to an appropriate projected CRS, the coordinates may be meters.

---

### 3. Geography

```sql
GEOGRAPHY(Point, 4326)
```

means:

> **"This is an Earth-based geographic object using WGS84 coordinates."**

It's particularly convenient for:

```text
GPS
location services
nearby searches
distance calculations
radius searches
```

where distances are naturally expressed in meters.

---

# 24. Final Mental Model

Don't memorize dozens of rules. Remember this:

```text
                 POINT
                   │
                   │
          ┌────────┴────────┐
          │                 │
      GEOMETRY          GEOGRAPHY
          │                 │
       "flat"             "Earth"
          │                 │
          └────────┬────────┘
                   │
                  SRID
                   │
          "Which coordinate
           reference system?"
                   │
          ┌────────┴────────┐
          │                 │
        4326              3857
          │                 │
       WGS84             Web Mercator
          │                 │
     lon/lat degrees    projected X/Y
```

So **SRID doesn't tell PostGIS whether the object is geometry or geography.**

Instead:

```text
GEOMETRY / GEOGRAPHY
        +
      SRID
        +
    coordinates
        ↓
complete spatial meaning
```

And this is why you can legitimately have:

```sql
GEOMETRY(Point, 4326)
```

and:

```sql
GEOGRAPHY(Point, 4326)
```

They share the **same CRS**, but use **different spatial calculation models**.

---

# 25. Backend Engineer's Practical Rule

For a backend application, especially something like:

```text
Restaurant finder
Uber / ride sharing
Delivery application
Nearby stores
Doctors within 10 km
GPS tracking
Location search
```

a common starting point is:

```sql
location GEOGRAPHY(Point, 4326)
```

because the input naturally arrives as:

```text
latitude
longitude
```

and your queries are naturally:

```text
within 1 km
within 5 km
distance = 2.3 km
```

For traditional GIS:

```text
City boundaries
Land parcels
Road networks
Buildings
Complex polygons
Regional GIS analysis
CAD-like spatial calculations
```

`geometry` is often the better choice, usually with an appropriate projected CRS.

---

# 26. One-Sentence Summary

> **SRID tells PostGIS what coordinate reference system the numbers belong to; `geometry` tells PostGIS to treat those coordinates as planar spatial data; `geography` tells PostGIS to treat them as Earth-based geographic data.**

The relationship is:

```text
                    Spatial Object
                         │
                         ▼
                Coordinates
                         │
                         +
                        SRID
                         │
                         ▼
              Coordinate Reference
                    System
                         │
                         +
                Geometry / Geography
                         │
                         ▼
             Spatial calculation model
```

That distinction is the foundation for understanding PostGIS.