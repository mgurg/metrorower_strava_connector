from __future__ import annotations

import math
from typing import Any, NamedTuple, TypeGuard

EARTH_RADIUS_METERS = 6_371_000


class Coordinates(NamedTuple):
    latitude: float
    longitude: float


def is_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_coordinates(latitude: Any, longitude: Any) -> Coordinates | None:
    if not (is_number(latitude) and is_number(longitude)):
        return None
    if -90 <= latitude <= 90 and -180 <= longitude <= 180:
        return Coordinates(float(latitude), float(longitude))
    return None


def distance_meters(a: Coordinates, b: Coordinates) -> float:
    cos_latitude = math.cos(math.radians(a.latitude))
    return EARTH_RADIUS_METERS * math.hypot(
        math.radians(b.latitude - a.latitude),
        cos_latitude * math.radians(b.longitude - a.longitude),
    )
