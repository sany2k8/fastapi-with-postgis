"""Geocoding helpers: resolve a country + city name to a bounding box.

Uses OpenStreetMap's Nominatim API (the reverse of what routing does — turning a
name into coordinates). Nominatim's usage policy asks for a real User-Agent and
at most ~1 request/second, which a CLI easily respects.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import httpx
import pycountry

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "places-finder-learning/0.1 (routing demo)"}


@dataclass
class CityMatch:
    name: str
    kind: str  # osm 'type', e.g. city / town / administrative
    lat: float
    lon: float
    # bbox in the project convention: (min_lon, min_lat, max_lon, max_lat)
    bbox: tuple[float, float, float, float]

    @property
    def width_km(self) -> float:
        return _bbox_span_km(self.bbox)[0]

    @property
    def height_km(self) -> float:
        return _bbox_span_km(self.bbox)[1]


def country_code(country: str) -> str | None:
    """Resolve a country name or ISO code to a 2-letter code for Nominatim."""
    country = country.strip()
    if len(country) == 2:
        rec = pycountry.countries.get(alpha_2=country.upper())
        return rec.alpha_2.lower() if rec else None
    try:
        matches = pycountry.countries.search_fuzzy(country)
    except LookupError:
        return None
    return matches[0].alpha_2.lower() if matches else None


def list_countries(query: str | None = None) -> list[tuple[str, str]]:
    """Return (name, alpha_2) for all countries, optionally filtered by substring."""
    out = [(c.name, c.alpha_2) for c in pycountry.countries]
    if query:
        q = query.lower()
        out = [c for c in out if q in c[0].lower()]
    return sorted(out)


def search_city(country: str, city: str, limit: int = 5) -> list[CityMatch]:
    """Look up a city within a country; return candidate matches with bboxes."""
    cc = country_code(country)
    params = {
        "city": city,
        "format": "jsonv2",
        "limit": str(limit),
        "featureType": "city",
    }
    if cc:
        params["countrycodes"] = cc
    else:
        params["country"] = country
    resp = httpx.get(NOMINATIM_URL, params=params, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    matches: list[CityMatch] = []
    for r in resp.json():
        # Nominatim boundingbox is [south, north, west, east] as strings.
        s, n, w, e = (float(x) for x in r["boundingbox"])
        matches.append(
            CityMatch(
                name=r["display_name"],
                kind=r.get("type", "?"),
                lat=float(r["lat"]),
                lon=float(r["lon"]),
                bbox=(w, s, e, n),
            )
        )
    return matches


def _bbox_span_km(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    min_lon, min_lat, max_lon, max_lat = bbox
    mid_lat = (min_lat + max_lat) / 2
    width = (max_lon - min_lon) * 111.0 * math.cos(math.radians(mid_lat))
    height = (max_lat - min_lat) * 111.0
    return abs(width), abs(height)


def cap_bbox(
    lat: float, lon: float, bbox: tuple[float, float, float, float], max_km: float
) -> tuple[tuple[float, float, float, float], bool]:
    """Shrink a bbox to at most max_km on a side, centered on (lat, lon).

    Returns (bbox, capped). A whole-city bbox from Nominatim is often tens of km
    across — too large for an in-memory routing graph — so we clamp it.
    """
    width, height = _bbox_span_km(bbox)
    if width <= max_km and height <= max_km:
        return bbox, False
    half = max_km / 2
    dlat = half / 111.0
    dlon = half / (111.0 * math.cos(math.radians(lat)) or 1e-6)
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat), True
