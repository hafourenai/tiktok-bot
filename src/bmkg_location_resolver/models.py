"""Structured public result types."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Forecast:
    code: str
    location: dict[str, Any]
    data: dict[str, Any]
    html: str
