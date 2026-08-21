"""Unit tests for the pure filter-validation logic (no DB, no I/O)."""

import pytest

from app.schemas.place import PlaceFilters
from app.services.place_service import InvalidFilter, _validate


def test_valid_bbox_only() -> None:
    _validate(PlaceFilters(bbox=(-122.5, 37.7, -122.3, 37.8)))  # no raise


def test_radius_without_point_is_rejected() -> None:
    with pytest.raises(InvalidFilter):
        _validate(PlaceFilters(radius_m=500))


def test_nearest_without_point_is_rejected() -> None:
    with pytest.raises(InvalidFilter):
        _validate(PlaceFilters(sort="nearest"))


def test_lat_without_lng_is_rejected() -> None:
    with pytest.raises(InvalidFilter):
        _validate(PlaceFilters(lat=37.7))


def test_out_of_range_lat_is_rejected() -> None:
    with pytest.raises(InvalidFilter):
        _validate(PlaceFilters(lat=200, lng=-122.4))


def test_negative_radius_is_rejected() -> None:
    with pytest.raises(InvalidFilter):
        _validate(PlaceFilters(lat=37.7, lng=-122.4, radius_m=-5))


def test_valid_point_and_radius() -> None:
    _validate(PlaceFilters(lat=37.7, lng=-122.4, radius_m=500, sort="nearest"))


def test_has_point_property() -> None:
    assert PlaceFilters(lat=37.7, lng=-122.4).has_point is True
    assert PlaceFilters().has_point is False
