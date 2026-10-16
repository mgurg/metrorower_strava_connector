from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from metrorower.errors import (
    InvalidFileError,
    InvalidRentalData,
    NetworkError,
    NextbikeApiError,
    SessionExpired,
)
from metrorower.geo import is_number, parse_coordinates
from metrorower.models import Place, Rental, TrackPoint

API_URL = "https://account.nextbike.pl/api/rental"
COOKIE_NAME = "nextbike-react"
API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://account.nextbike.pl",
    "Referer": "https://account.nextbike.pl/pl-PL/zz/profile",
    "User-Agent": "Mozilla/5.0 Nextbike-GPX-Exporter/1.0",
}
UNAUTHORIZED = 401


def load_cookie(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise InvalidFileError(
            f"Nie znaleziono {path}. Utwórz plik i wklej do niego cookie Nextbike."
        ) from error

    value = value.removeprefix(f"{COOKIE_NAME}=")
    if not value or any(character.isspace() for character in value):
        raise InvalidFileError(f"Plik {path} nie zawiera poprawnej wartości cookie")
    return value


def nextbike_client(cookie: str) -> httpx.Client:
    return httpx.Client(
        headers=API_HEADERS,
        cookies={COOKIE_NAME: cookie},
        timeout=30,
        follow_redirects=True,
    )


class NextbikeApi:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def fetch(self, rental_id: str) -> dict[str, Any]:
        try:
            response = self._client.post(API_URL, json={"id": rental_id})
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status == UNAUTHORIZED:
                raise SessionExpired(status) from error
            raise NextbikeApiError(status) from error
        except httpx.RequestError as error:
            raise NetworkError(f"brak połączenia z API: {error}") from error

        try:
            data = response.json()
        except ValueError as error:
            raise InvalidRentalData("API nie zwróciło poprawnego JSON") from error
        if not isinstance(data, dict):
            raise InvalidRentalData("API nie zwróciło obiektu JSON")
        return data


def utc_from_seconds(seconds: float) -> datetime:
    try:
        return datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError) as error:
        raise InvalidRentalData(f"nieprawidłowy znacznik czasu: {seconds!r}") from error


def parse_route_point(raw: Any, index: int) -> TrackPoint:
    try:
        latitude, longitude = float(raw["lat"]), float(raw["lng"])
        milliseconds = float(raw["ts"])
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidRentalData(f"nieprawidłowy routePoints[{index}]") from error
    if parse_coordinates(latitude, longitude) is None:
        raise InvalidRentalData(f"nieprawidłowy routePoints[{index}]")
    return TrackPoint(latitude, longitude, utc_from_seconds(milliseconds / 1000))


def parse_route_points(raw: Any) -> tuple[TrackPoint, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise InvalidRentalData("pole routePoints nie jest listą")
    points = (
        parse_route_point(point, index) for index, point in enumerate(raw, start=1)
    )
    return tuple(sorted(points, key=lambda point: point.time))


def parse_place(raw: Any) -> Place:
    if not isinstance(raw, dict):
        return Place()
    name = raw.get("name")
    return Place(
        station_number=None if name is None else str(name),
        location=parse_coordinates(raw.get("lat"), raw.get("lng")),
    )


def parse_bike_number(raw: Any) -> str | None:
    if not isinstance(raw, dict) or not raw.get("number"):
        return None
    return str(raw["number"])


def required_number(data: dict[str, Any], field: str) -> float:
    value = data.get(field)
    if not is_number(value):
        raise InvalidRentalData(f"odpowiedź nie zawiera liczbowego pola {field}")
    return float(value)


def parse_rental(data: Any, rental_id: str) -> Rental:
    if not isinstance(data, dict):
        raise InvalidRentalData("odpowiedź nie jest obiektem JSON")
    end_time = data.get("endTime")
    return Rental(
        rental_id=rental_id,
        distance_meters=required_number(data, "distance"),
        start_time=utc_from_seconds(required_number(data, "startTime")),
        end_time=utc_from_seconds(end_time) if is_number(end_time) else None,
        start_place=parse_place(data.get("startPlace")),
        end_place=parse_place(data.get("endPlace")),
        bike_number=parse_bike_number(data.get("bike")),
        route_points=parse_route_points(data.get("routePoints")),
    )
