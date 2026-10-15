from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from typing import Any, NamedTuple, TypeGuard
from zoneinfo import ZoneInfo

LOCAL_TIMEZONE = ZoneInfo("Europe/Warsaw")


Coordinates = tuple[float, float]


StationsByNumber = dict[str, dict[str, int | float]]


class TrackPoint(NamedTuple):
    latitude: float
    longitude: float
    iso_time: str


class Track(NamedTuple):
    date: str
    route_points: list[TrackPoint]


class Ride(NamedTuple):
    rental_id: str
    rental: dict[str, Any]
    source: str
    distance: float
    track_if_long_enough: Track | None


class InvalidDataError(ValueError):
    pass


def is_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_integer(value: Any) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def as_coordinates(latitude: Any, longitude: Any) -> Coordinates | None:
    if not (is_number(latitude) and is_number(longitude)):
        return None
    if -90 <= latitude <= 90 and -180 <= longitude <= 180:
        return float(latitude), float(longitude)
    return None


def number_field(data: dict[str, Any], field: str) -> float | None:
    value = data.get(field)
    return value if is_number(value) else None


def valid_coordinate(latitude: Any, longitude: Any) -> bool:
    return as_coordinates(latitude, longitude) is not None


def datetime_from_seconds(seconds: float, tz: tzinfo) -> datetime:
    try:
        return datetime.fromtimestamp(seconds, tz=tz)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f"nieprawidłowy znacznik czasu: {seconds!r}") from error


def iso_time_from_milliseconds(timestamp: float) -> str:
    moment = datetime_from_seconds(timestamp / 1000, UTC)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def rental_time(rental: dict[str, Any], field: str, fallback: str) -> str:
    seconds = number_field(rental, field)
    if seconds is None:
        return fallback
    return iso_time_from_milliseconds(seconds * 1000)


def rental_date(rental: dict[str, Any]) -> str:
    start_time = number_field(rental, "startTime")
    if start_time is None:
        raise ValueError("odpowiedź nie zawiera liczbowego pola startTime")
    return datetime_from_seconds(start_time, LOCAL_TIMEZONE).strftime("%Y%m%d")
