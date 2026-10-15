from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from metrorower.files import load_json
from metrorower.models import (
    Coordinates,
    StationsByNumber,
    TrackPoint,
    as_coordinates,
    is_integer,
    valid_coordinate,
)

DEFAULT_STATIONS_PATH = (
    Path(__file__).resolve().parent.parent / "resources" / "stations.json"
)
EARTH_RADIUS_METRES = 6_371_000
MAX_PLACE_TO_STATION_METRES = 300


def valid_station(station: Any) -> bool:
    return (
        isinstance(station, dict)
        and is_integer(station.get("number"))
        and valid_coordinate(station.get("lat"), station.get("lng"))
    )


def load_stations(path: Path) -> StationsByNumber:
    data = load_json(path)
    if not isinstance(data, list) or not data:
        raise ValueError(f"Plik {path} nie zawiera listy stacji")
    for index, station in enumerate(data, start=1):
        if not valid_station(station):
            raise ValueError(f"Nieprawidłowa stacja #{index} w {path}")
    return {str(station["number"]): station for station in data}


def equirectangular_distance_metres(a: Coordinates, b: Coordinates) -> float:
    cos_latitude = math.cos(math.radians(a[0]))
    return EARTH_RADIUS_METRES * math.hypot(
        math.radians(b[0] - a[0]), cos_latitude * math.radians(b[1] - a[1])
    )


def station_location(
    place: Any, route_point: TrackPoint, stations: StationsByNumber
) -> Coordinates | None:
    place = place if isinstance(place, dict) else {}
    named_station = stations.get(str(place.get("name")))
    if named_station is not None:
        return float(named_station["lat"]), float(named_station["lng"])

    location = as_coordinates(place.get("lat"), place.get("lng")) or (
        route_point.latitude,
        route_point.longitude,
    )

    distance, nearest = min(
        (
            (
                equirectangular_distance_metres(
                    location, (station["lat"], station["lng"])
                ),
                station,
            )
            for station in stations.values()
        ),
        key=lambda pair: pair[0],
    )
    if distance > MAX_PLACE_TO_STATION_METRES:
        return None
    return float(nearest["lat"]), float(nearest["lng"])
