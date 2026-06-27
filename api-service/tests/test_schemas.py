"""Unit-тесты Pydantic-схем (без HTTP и БД)."""

import pytest
from pydantic import ValidationError

from app.routers.predict import PredictRequest


def _base(**kwargs) -> dict:
    return {"total_area": 52.0, "floor": 5, "floors": 9, **kwargs}


def test_valid_request():
    req = PredictRequest(**_base(lat=55.75, lon=37.62, property_kind="flat"))
    assert req.total_area == 52.0
    assert req.property_kind == "flat"


def test_floor_greater_than_floors_raises():
    with pytest.raises(ValidationError, match="floor"):
        PredictRequest(**_base(floor=10, floors=5))


def test_invalid_lat_raises():
    with pytest.raises(ValidationError, match="lat"):
        PredictRequest(**_base(lat=0.0))  # вне Московского региона


def test_invalid_lon_raises():
    with pytest.raises(ValidationError, match="lon"):
        PredictRequest(**_base(lon=0.0))  # вне Московского региона


def test_invalid_property_kind_raises():
    with pytest.raises(ValidationError, match="property_kind"):
        PredictRequest(**_base(property_kind="castle"))


def test_negative_total_area_raises():
    with pytest.raises(ValidationError):
        PredictRequest(**_base(total_area=-1.0))


def test_zero_total_area_raises():
    with pytest.raises(ValidationError):
        PredictRequest(**_base(total_area=0.0))


def test_optional_fields_default_to_none():
    req = PredictRequest(**_base())
    assert req.lat is None
    assert req.lon is None
    assert req.property_kind is None
