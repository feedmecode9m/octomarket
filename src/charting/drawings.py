"""Drawing validation and normalization."""

from copy import deepcopy
from typing import Any, Dict

from .drawing_models import DRAWING_TYPES, drawing_from_dict


def _require_number(value: Any, field_name: str) -> float:
    if value is None:
        raise ValueError(f"{field_name} is required")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number") from exc


def _validate_point(point: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(point, dict):
        raise ValueError(f"{field_name} must be an object with time and price")
    if not point.get("time"):
        raise ValueError(f"{field_name}.time is required")
    price = _require_number(point.get("price"), f"{field_name}.price")
    return {"time": str(point["time"]), "price": price}


def validate_horizontal(data: Dict[str, Any]) -> None:
    _require_number(data.get("price"), "price")


def validate_trendline(data: Dict[str, Any]) -> None:
    start = _validate_point(data.get("start"), "start")
    end = _validate_point(data.get("end"), "end")
    if start["time"] == end["time"] and start["price"] == end["price"]:
        raise ValueError("Trendline start and end must differ")


def validate_zone(data: Dict[str, Any]) -> None:
    top = _require_number(data.get("top"), "top")
    bottom = _require_number(data.get("bottom"), "bottom")
    if top <= bottom:
        raise ValueError("Zone top must be greater than bottom")


def validate_drawing(data: Dict[str, Any]) -> None:
    dtype = (data.get("type") or "").strip().lower()
    if dtype not in DRAWING_TYPES:
        raise ValueError(f"Drawing type must be one of: {DRAWING_TYPES}")
    if dtype == "horizontal":
        validate_horizontal(data)
    elif dtype == "trendline":
        validate_trendline(data)
    elif dtype == "zone":
        validate_zone(data)


def normalize_drawing(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data:
        raise ValueError("Drawing payload is required")
    validate_drawing(data)
    return drawing_from_dict(data)


def validate_drawing_update(existing: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(existing)
    merged.update({k: v for k, v in patch.items() if k != "id" and v is not None})
    if "type" in patch and patch["type"]:
        merged["type"] = str(patch["type"]).lower()
    validate_drawing(merged)
    return drawing_from_dict({**merged, "id": existing.get("id")})
