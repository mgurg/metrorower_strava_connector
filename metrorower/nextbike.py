from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import httpx

from metrorower.files import load_json, save_json
from metrorower.models import (
    InvalidDataError,
    Ride,
    Track,
    TrackPoint,
    iso_time_from_milliseconds,
    number_field,
    rental_date,
    valid_coordinate,
)

API_URL = "https://account.nextbike.pl/api/rental"
COOKIE_NAME = "nextbike-react"
API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://account.nextbike.pl",
    "Referer": "https://account.nextbike.pl/pl-PL/zz/profile",
    "User-Agent": "Mozilla/5.0 Nextbike-GPX-Exporter/1.0",
}


def load_cookie(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise ValueError(
            f"Nie znaleziono {path}. Utwórz plik i wklej do niego cookie Nextbike."
        ) from error

    value = value.removeprefix(f"{COOKIE_NAME}=")
    if not value or any(character.isspace() for character in value):
        raise ValueError(f"Plik {path} nie zawiera poprawnej wartości cookie")
    return value


def nextbike_client(cookie: str) -> httpx.Client:
    return httpx.Client(
        headers=API_HEADERS,
        cookies={COOKIE_NAME: cookie},
        timeout=30,
        follow_redirects=True,
    )


def fetch_rental(client: httpx.Client, rental_id: str) -> dict[str, Any]:
    response = client.post(API_URL, json={"id": rental_id})
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise InvalidDataError("API nie zwróciło obiektu JSON")
    return data


def parse_route_points(rental: dict[str, Any]) -> list[TrackPoint]:
    route_points = rental.get("routePoints")
    if not isinstance(route_points, list) or not route_points:
        raise ValueError("brak punktów routePoints")

    parsed_points: list[tuple[float, float, float]] = []
    for index, point in enumerate(route_points, start=1):
        try:
            latitude, longitude = float(point["lat"]), float(point["lng"])
            parsed_points.append((latitude, longitude, float(point["ts"])))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"nieprawidłowy routePoints[{index}]") from error
        if not valid_coordinate(latitude, longitude):
            raise ValueError(f"nieprawidłowy routePoints[{index}]")

    parsed_points.sort(key=lambda point: point[2])
    return [
        TrackPoint(latitude, longitude, iso_time_from_milliseconds(timestamp))
        for latitude, longitude, timestamp in parsed_points
    ]


def validate_rental(
    rental: dict[str, Any], minimum_metres: float
) -> tuple[float, Track | None]:
    distance = number_field(rental, "distance")
    if distance is None:
        raise ValueError("odpowiedź nie zawiera liczbowego pola distance")
    if distance < minimum_metres:
        return distance, None
    return distance, Track(rental_date(rental), parse_route_points(rental))


def load_ride(
    client: httpx.Client, json_path: Path, rental_id: str, minimum_metres: float
) -> Ride:
    if json_path.exists():
        try:
            rental = load_json(json_path)
            if not isinstance(rental, dict):
                raise InvalidDataError("cache nie zawiera obiektu JSON")
            return Ride(
                rental_id, rental, "cache", *validate_rental(rental, minimum_metres)
            )
        except ValueError as error:
            print(
                f"[{rental_id}] nieprawidłowy cache ({error}), pobieram ponownie",
                file=sys.stderr,
            )

    rental = fetch_rental(client, rental_id)
    ride = Ride(rental_id, rental, "API", *validate_rental(rental, minimum_metres))
    save_json(json_path, rental)
    return ride
