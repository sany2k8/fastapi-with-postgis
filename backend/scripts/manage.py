"""Management CLI for Places Finder data.

Lets anyone starting from a blank database add their own data instead of the
predefined SF/Bangladesh fixtures:

  * a single place or neighbourhood
  * a batch of synthetic places inside a bounding box
  * a road network for any area (fetched live from OpenStreetMap)

Run `uv run python -m scripts.manage --help` to see all commands.

Coordinates are passed as comma-separated strings (never as separate numbers),
so a leading minus sign isn't mistaken for a CLI flag. If a value *starts* with
a minus, use the `--opt=value` form (with the equals sign).

Every data command takes EITHER a manual location (--at / --bbox) OR a geocoded
one (--country, using the name as the query) — precise when you have
coordinates, convenient when you don't.

Examples
--------
    # one point of interest  — manual (lat,lng) …
    uv run python -m scripts.manage add-place "Blue Bottle" cafe --at 37.776,-122.423
    # … or geocoded by name
    uv run python -m scripts.manage add-place "Eiffel Tower Cafe" cafe \
        --country France --query "Eiffel Tower"

    # a neighbourhood  — manual bbox (min_lon,min_lat,max_lon,max_lat) …
    uv run python -m scripts.manage add-neighborhood "Downtown" --bbox=-122.42,37.77,-122.40,37.79
    # … or geocoded by name
    uv run python -m scripts.manage add-neighborhood Gulshan --country Bangladesh

    # synthetic places in an area  — manual bbox …
    uv run python -m scripts.manage generate-places --bbox=-122.46,37.74,-122.39,37.81 \
        --count 200 --neighborhood "My Area"
    # … or geocoded by name
    uv run python -m scripts.manage generate-places --country France --place Lyon \
        --count 50 --max-km 6

    # a routable road network for a new city, by explicit bbox …
    uv run python -m scripts.manage add-city-roads sylhet --bbox 91.85,24.87,91.92,24.93

    # … or just pick a country + city and let OSM resolve the bbox for you
    uv run python -m scripts.manage list-countries --search bang
    uv run python -m scripts.manage search-city Bangladesh Sylhet
    uv run python -m scripts.manage add-city Bangladesh Sylhet --max-km 10
"""

from __future__ import annotations

import random

import typer
from faker import Faker
from geoalchemy2.elements import WKTElement
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from app.core.db import SessionLocal
from app.models.neighborhood import Neighborhood
from app.models.place import Place
from scripts import geocode
from scripts.ingest_roads import ingest_city
from scripts.seed import (
    CATEGORIES,
    build_random_place,
    generate_points_in_polygon,
    polygon_wkt,
)

SRID = 4326
app = typer.Typer(add_completion=False, help="Add and inspect Places Finder data.")
console = Console()


def _parse_at(at: str) -> tuple[float, float]:
    try:
        lat, lng = (float(x) for x in at.split(","))
    except ValueError as exc:
        raise typer.BadParameter("--at must be 'lat,lng' (e.g. 37.776,-122.423)") from exc
    if not -90 <= lat <= 90:
        raise typer.BadParameter(f"lat {lat} out of range (-90..90)")
    if not -180 <= lng <= 180:
        raise typer.BadParameter(f"lng {lng} out of range (-180..180)")
    return lat, lng


def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    parts = bbox.split(",")
    if len(parts) != 4:
        raise typer.BadParameter("--bbox must be 'min_lon,min_lat,max_lon,max_lat'")
    try:
        min_lon, min_lat, max_lon, max_lat = (float(x) for x in parts)
    except ValueError as exc:
        raise typer.BadParameter("--bbox values must be numbers") from exc
    if min_lon >= max_lon or min_lat >= max_lat:
        raise typer.BadParameter("bbox min must be less than max")
    return min_lon, min_lat, max_lon, max_lat


def _resolve_point(country: str, query: str) -> tuple[float, float]:
    """Geocode a place name within a country to a single (lat, lng)."""
    matches = geocode.search_place(country, query, limit=1)
    if not matches:
        raise typer.BadParameter(f"no match for '{query}' in '{country}'")
    m = matches[0]
    console.print(f"Resolved [bold]{m.name.split(',')[0]}[/] → {m.lat:.5f}, {m.lon:.5f}")
    return m.lat, m.lon


def _resolve_bbox(country: str, query: str, max_km: float) -> tuple[float, float, float, float]:
    """Geocode a place/area name within a country to a (capped) bounding box."""
    matches = geocode.search_place(country, query, limit=1)
    if not matches:
        raise typer.BadParameter(f"no match for '{query}' in '{country}'")
    m = matches[0]
    bbox, capped = geocode.cap_bbox(m.lat, m.lon, m.bbox, max_km)
    note = f" (capped to ~{max_km:.0f} km)" if capped else ""
    console.print(f"Resolved [bold]{m.name.split(',')[0]}[/] → bbox{note}")
    return bbox


@app.command()
def add_place(
    name: str = typer.Argument(..., help="Place name"),
    category: str = typer.Argument(..., help=f"One of: {', '.join(CATEGORIES)}"),
    at: str | None = typer.Option(None, "--at", help="Location as 'lat,lng'"),
    country: str | None = typer.Option(
        None, "--country", help="Geocode by name instead of --at (uses NAME as the query)"
    ),
    query: str | None = typer.Option(None, "--query", help="Override the geocode query"),
    rating: float = typer.Option(4.0, min=0, max=5),
    price: int = typer.Option(2, "--price", min=1, max=4, help="Price level 1-4"),
    open24h: bool = typer.Option(False, "--open24h"),
) -> None:
    """Add a single point of interest, by explicit --at or by geocoding a name."""
    if category not in CATEGORIES:
        raise typer.BadParameter(f"category must be one of: {', '.join(CATEGORIES)}")
    if at:
        lat, lng = _parse_at(at)
    elif country:
        lat, lng = _resolve_point(country, query or name)
    else:
        raise typer.BadParameter("provide --at, or --country to geocode by name")
    with SessionLocal() as s:
        s.add(
            Place(
                name=name,
                category=category,
                rating=rating,
                price_level=price,
                is_open_24h=open24h,
                geom=WKTElement(f"POINT({lng} {lat})", srid=SRID),
            )
        )
        s.commit()
    console.print(f"[green]✓[/] added place '{name}' ({category}) at {lat}, {lng}")


@app.command()
def add_neighborhood(
    name: str = typer.Argument(..., help="Neighbourhood name (must be unique)"),
    bbox: str | None = typer.Option(None, "--bbox", help="'min_lon,min_lat,max_lon,max_lat'"),
    country: str | None = typer.Option(
        None, "--country", help="Geocode by name instead of --bbox (uses NAME as the query)"
    ),
    query: str | None = typer.Option(None, "--query", help="Override the geocode query"),
    max_km: float = typer.Option(5.0, "--max-km", help="Cap the geocoded area to this size"),
) -> None:
    """Add a neighbourhood rectangle, by explicit --bbox or by geocoding a name."""
    if bbox:
        box = _parse_bbox(bbox)
    elif country:
        box = _resolve_bbox(country, query or name, max_km)
    else:
        raise typer.BadParameter("provide --bbox, or --country to geocode by name")
    wkt = polygon_wkt(box)
    with SessionLocal() as s:
        s.add(Neighborhood(name=name, geom=WKTElement(wkt, srid=SRID)))
        s.commit()
    console.print(f"[green]✓[/] added neighbourhood '{name}'")


@app.command()
def generate_places(
    bbox: str | None = typer.Option(None, "--bbox", help="'min_lon,min_lat,max_lon,max_lat'"),
    country: str | None = typer.Option(None, "--country", help="Geocode area instead of --bbox"),
    place: str | None = typer.Option(None, "--place", help="Area/city to geocode (with --country)"),
    max_km: float = typer.Option(10.0, "--max-km", help="Cap the geocoded area to this size"),
    count: int = typer.Option(100, min=1, help="How many places to generate"),
    seed: int = typer.Option(42, help="Random seed for reproducibility"),
    neighborhood: str | None = typer.Option(
        None, "--neighborhood", help="Also create a neighbourhood covering this bbox"
    ),
) -> None:
    """Scatter N synthetic places in a bbox (explicit --bbox, or geocoded area)."""
    if bbox:
        box = _parse_bbox(bbox)
    elif country and place:
        box = _resolve_bbox(country, place, max_km)
    else:
        raise typer.BadParameter("provide --bbox, or --country and --place to geocode")
    random.seed(seed)
    Faker.seed(seed)
    with SessionLocal() as s:
        if neighborhood:
            s.add(Neighborhood(name=neighborhood, geom=WKTElement(polygon_wkt(box), srid=SRID)))
            s.flush()
        pts = generate_points_in_polygon(s, polygon_wkt(box), count, seed=seed)
        s.add_all(build_random_place(lon, lat) for lon, lat in pts)
        s.commit()
    extra = f" + neighbourhood '{neighborhood}'" if neighborhood else ""
    console.print(f"[green]✓[/] generated {len(pts)} places in bbox{extra}")


@app.command()
def add_city_roads(
    city: str = typer.Argument(..., help="City/area label (lowercase, no spaces)"),
    bbox: str = typer.Option(..., "--bbox", help="'min_lon,min_lat,max_lon,max_lat'"),
) -> None:
    """Fetch a road network from OpenStreetMap and load it as a routable graph."""
    box = _parse_bbox(bbox)
    console.print(f"Fetching roads for '{city}' from Overpass… (this can take a moment)")
    nodes, edges = ingest_city(city, box)
    console.print(f"[green]✓[/] loaded '{city}': {nodes} nodes, {edges} edges")


@app.command()
def list_countries(
    search: str | None = typer.Option(None, "--search", help="Filter by name substring"),
) -> None:
    """List countries (name + ISO code) to use with add-city / search-city."""
    rows = geocode.list_countries(search)
    if not rows:
        console.print("[yellow]no countries matched[/]")
        return
    table = Table(title=f"countries ({len(rows)})")
    table.add_column("name")
    table.add_column("code")
    for name, code in rows:
        table.add_row(name, code)
    console.print(table)


@app.command()
def search_city(
    country: str = typer.Argument(..., help="Country name or ISO code"),
    city: str = typer.Argument(..., help="City name to look up"),
    limit: int = typer.Option(5, min=1, max=20),
) -> None:
    """Look up a city via OpenStreetMap and show candidate matches + bbox size."""
    matches = geocode.search_city(country, city, limit)
    if not matches:
        console.print(f"[yellow]no match for '{city}' in '{country}'[/]")
        return
    table = Table(title=f"'{city}' in {country}")
    table.add_column("#")
    table.add_column("match")
    table.add_column("type")
    table.add_column("size (km)")
    for i, m in enumerate(matches, 1):
        short = m.name.split(",")[0] + (f", …{m.name.split(',')[-1]}" if "," in m.name else "")
        table.add_row(str(i), short, m.kind, f"{m.width_km:.0f}×{m.height_km:.0f}")
    console.print(table)
    console.print("[dim]Add one with:  add-city <country> <city> --max-km 12[/]")


@app.command()
def add_city(
    country: str = typer.Argument(..., help="Country name or ISO code"),
    city: str = typer.Argument(..., help="City name (geocoded via OpenStreetMap)"),
    label: str | None = typer.Option(None, "--label", help="DB label (default: slug of city)"),
    max_km: float = typer.Option(12.0, "--max-km", help="Cap the fetched area to this size"),
) -> None:
    """Pick a country + city, auto-resolve its bounding box, and load its roads."""
    matches = geocode.search_city(country, city, limit=1)
    if not matches:
        raise typer.BadParameter(f"no match for '{city}' in '{country}' — try `search-city`")
    m = matches[0]
    bbox, capped = geocode.cap_bbox(m.lat, m.lon, m.bbox, max_km)
    slug = (label or city).strip().lower().replace(" ", "-")
    console.print(f"Resolved [bold]{m.name.split(',')[0]}[/] → center {m.lat:.4f}, {m.lon:.4f}")
    if capped:
        console.print(f"[dim]bbox capped to ~{max_km:.0f} km (full area was larger)[/]")
    console.print(f"Fetching roads for '{slug}' from Overpass… (this can take a moment)")
    nodes, edges = ingest_city(slug, bbox)
    console.print(f"[green]✓[/] loaded '{slug}': {nodes} nodes, {edges} edges — now routable")


@app.command()
def clear_roads(city: str = typer.Argument(..., help="City label to remove")) -> None:
    """Delete a city's road network (roads + nodes)."""
    with SessionLocal() as s:
        s.execute(text("DELETE FROM roads WHERE city = :c"), {"c": city})
        s.execute(text("DELETE FROM road_nodes WHERE city = :c"), {"c": city})
        s.commit()
    console.print(f"[green]✓[/] cleared road network for '{city}'")


@app.command()
def stats() -> None:
    """Show current data counts."""
    with SessionLocal() as s:
        places = s.execute(text("SELECT count(*) FROM places")).scalar_one()
        hoods = s.execute(text("SELECT count(*) FROM neighborhoods")).scalar_one()
        road_rows = s.execute(
            text(
                "SELECT city, count(*) AS edges, "
                "(SELECT count(*) FROM road_nodes n WHERE n.city = r.city) AS nodes "
                "FROM roads r GROUP BY city ORDER BY city"
            )
        ).all()

    console.print(f"places: [bold]{places}[/]    neighbourhoods: [bold]{hoods}[/]")
    table = Table(title="road networks")
    table.add_column("city")
    table.add_column("nodes", justify="right")
    table.add_column("edges", justify="right")
    for row in road_rows:
        table.add_row(row.city, str(row.nodes), str(row.edges))
    if road_rows:
        console.print(table)
    else:
        console.print("[dim]no road networks loaded[/]")


if __name__ == "__main__":
    app()
