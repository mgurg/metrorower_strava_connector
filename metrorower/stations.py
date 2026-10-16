from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from metrorower.errors import InvalidFileError
from metrorower.files import load_json
from metrorower.geo import (
    Coordinates,
    distance_meters,
    parse_coordinates,
)
from metrorower.models import Place

STATIONS_PATH = Path(__file__).resolve().parent / "resources" / "stations.json"
MAX_PLACE_TO_STATION_METERS = 300


@dataclass(frozen=True)
class Station:
    number: int
    location: Coordinates


class Stations:
    def __init__(self, stations: Iterable[Station]) -> None:
        self._by_number = {str(station.number): station for station in stations}

    def __len__(self) -> int:
        return len(self._by_number)

    def __getitem__(self, number: str) -> Station:
        return self._by_number[number]

    def locate(self, place: Place, fallback: Coordinates) -> Coordinates | None:
        named_station = self._by_number.get(place.station_number or "")
        if named_station is not None:
            return named_station.location
        return self.nearest_within(
            place.location or fallback, MAX_PLACE_TO_STATION_METERS
        )

    def nearest_within(
        self, location: Coordinates, max_meters: float
    ) -> Coordinates | None:
        distance, nearest = min(
            (
                (distance_meters(location, station.location), station)
                for station in self._by_number.values()
            ),
            key=lambda pair: pair[0],
        )
        return nearest.location if distance <= max_meters else None


def parse_station(raw: Any) -> Station | None:
    if not isinstance(raw, dict):
        return None
    number = raw.get("number")
    location = parse_coordinates(raw.get("lat"), raw.get("lng"))
    if not isinstance(number, int) or isinstance(number, bool) or location is None:
        return None
    return Station(number, location)


def load_stations(path: Path) -> Stations:
    data = load_json(path)
    if not isinstance(data, list) or not data:
        raise InvalidFileError(f"Plik {path} nie zawiera listy stacji")
    stations: list[Station] = []
    for index, raw in enumerate(data, start=1):
        station = parse_station(raw)
        if station is None:
            raise InvalidFileError(f"Nieprawidłowa stacja #{index} w {path}")
        stations.append(station)
    return Stations(stations)
