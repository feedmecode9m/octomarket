"""Chart drawing models — horizontal lines, trendlines, zones."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


DRAWING_TYPES = ("horizontal", "trendline", "zone")

DEFAULT_COLORS = {
    "horizontal": "#ff4757",
    "trendline": "#00d4ff",
    "zone": "rgba(0,212,255,0.12)",
}


@dataclass
class ChartPoint:
    time: str
    price: float

    def to_dict(self) -> Dict[str, Any]:
        return {"time": self.time, "price": self.price}


@dataclass
class HorizontalDrawing:
    type: str = "horizontal"
    price: float = 0.0
    label: str = ""
    color: str = DEFAULT_COLORS["horizontal"]
    id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "type": self.type,
            "price": self.price,
            "label": self.label,
            "color": self.color,
        }
        return {k: v for k, v in payload.items() if v is not None}


@dataclass
class TrendLineDrawing:
    start: ChartPoint
    end: ChartPoint
    type: str = "trendline"
    label: str = ""
    color: str = DEFAULT_COLORS["trendline"]
    id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "type": self.type,
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "label": self.label,
            "color": self.color,
        }
        return {k: v for k, v in payload.items() if v is not None}


@dataclass
class ZoneDrawing:
    top: float
    bottom: float
    type: str = "zone"
    label: str = ""
    color: str = DEFAULT_COLORS["zone"]
    id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "type": self.type,
            "top": self.top,
            "bottom": self.bottom,
            "label": self.label,
            "color": self.color,
        }
        return {k: v for k, v in payload.items() if v is not None}


def drawing_from_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return normalized drawing dict from raw input."""
    dtype = (data.get("type") or "").strip().lower()
    if dtype == "horizontal":
        return HorizontalDrawing(
            id=data.get("id"),
            price=float(data["price"]),
            label=data.get("label") or "",
            color=data.get("color") or DEFAULT_COLORS["horizontal"],
        ).to_dict()
    if dtype == "trendline":
        start = data.get("start") or {}
        end = data.get("end") or {}
        return TrendLineDrawing(
            id=data.get("id"),
            start=ChartPoint(str(start["time"]), float(start["price"])),
            end=ChartPoint(str(end["time"]), float(end["price"])),
            label=data.get("label") or "",
            color=data.get("color") or DEFAULT_COLORS["trendline"],
        ).to_dict()
    if dtype == "zone":
        return ZoneDrawing(
            id=data.get("id"),
            top=float(data["top"]),
            bottom=float(data["bottom"]),
            label=data.get("label") or "",
            color=data.get("color") or DEFAULT_COLORS["zone"],
        ).to_dict()
    raise ValueError(f"Unknown drawing type '{dtype}'")
