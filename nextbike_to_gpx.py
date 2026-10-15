#!/usr/bin/env python3
"""Pobierz przejazdy Nextbike i wyeksportuj ich punkty trasy do GPX."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import Any, NamedTuple
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import httpx


API_URL = "https://account.nextbike.pl/api/rental"
COOKIE_NAME = "nextbike-react"
GPX_NAMESPACE = "http://www.topografix.com/GPX/1/1"
ET.register_namespace("", GPX_NAMESPACE)
LOCAL_TIMEZONE = ZoneInfo("Europe/Warsaw")
DEFAULT_STATIONS_PATH = Path(__file__).resolve().parent / "resources" / "stations.json"
EARTH_RADIUS_METRES = 6_371_000
MAX_PLACE_TO_STATION_METRES = 300
STATION_SEARCH_WINDOW_SECONDS = 120

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
    rental: dict[str, Any]
    source: str
    distance: float
    track_if_long_enough: Track | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pobiera przejazdy Nextbike i zapisuje trasy jako GPX."
    )
    parser.add_argument(
        "--ids",
        type=Path,
        default=Path("ids.txt"),
        help="plik z ID przejazdów (domyślnie: ids.txt)",
    )
    parser.add_argument(
        "--cookie",
        type=Path,
        default=Path("cookie.txt"),
        help="plik z cookie Nextbike (domyślnie: cookie.txt)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="katalog pełnych odpowiedzi JSON (domyślnie: data)",
    )
    parser.add_argument(
        "--gpx-dir",
        type=Path,
        default=Path("gpx"),
        help="katalog wynikowych plików GPX (domyślnie: gpx)",
    )
    parser.add_argument(
        "--stations",
        type=Path,
        default=DEFAULT_STATIONS_PATH,
        help="plik ze stacjami (domyślnie: resources/stations.json)",
    )
    parser.add_argument(
        "--min-distance-km",
        type=float,
        default=1.0,
        help="minimalny dystans eksportowany do GPX (domyślnie: 1.0)",
    )
    return parser.parse_args()


def load_ids(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError as error:
        raise ValueError(f"Nie znaleziono pliku z ID: {path}") from error

    ids: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        value = line.strip()
        if not value or value.casefold() == "id":
            continue
        if not value.isdecimal():
            raise ValueError(
                f"Nieprawidłowe ID w {path}, wiersz {line_number}: {value!r}"
            )
        ids.append(value)

    if not ids:
        raise ValueError(f"Plik {path} nie zawiera żadnych ID przejazdów")
    return list(dict.fromkeys(ids))


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


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"nie można odczytać {path}: {error}") from error


def valid_coordinate(latitude: Any, longitude: Any) -> bool:
    return (
        isinstance(latitude, (int, float))
        and isinstance(longitude, (int, float))
        and not isinstance(latitude, bool)
        and not isinstance(longitude, bool)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def load_stations(path: Path) -> StationsByNumber:
    data = load_json(path)
    if not isinstance(data, list) or not data:
        raise ValueError(f"Plik {path} nie zawiera listy stacji")
    for index, station in enumerate(data, start=1):
        if (
            not isinstance(station, dict)
            or not isinstance(station.get("number"), int)
            or isinstance(station["number"], bool)
            or not valid_coordinate(station.get("lat"), station.get("lng"))
        ):
            raise ValueError(f"Nieprawidłowa stacja #{index} w {path}")
    return {str(station["number"]): station for station in data}


def write_atomically(path: Path, write: Callable[[Path], None]) -> None:
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        write(temporary_path)
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def save_json(path: Path, data: dict[str, Any]) -> None:
    write_atomically(
        path,
        lambda temporary_path: temporary_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        ),
    )


def fetch_rental(client: httpx.Client, rental_id: str) -> dict[str, Any]:
    response = client.post(API_URL, json={"id": rental_id})
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("API nie zwróciło obiektu JSON")
    return data


def datetime_from_seconds(seconds: float, tz: tzinfo) -> datetime:
    try:
        return datetime.fromtimestamp(seconds, tz=tz)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(f"nieprawidłowy znacznik czasu: {seconds!r}") from error


def iso_time_from_milliseconds(timestamp: float) -> str:
    moment = datetime_from_seconds(timestamp / 1000, timezone.utc)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def rental_time(rental: dict[str, Any], field: str, fallback: str) -> str:
    seconds = rental.get(field)
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        return fallback
    return iso_time_from_milliseconds(seconds * 1000)


def rental_date(rental: dict[str, Any]) -> str:
    start_time = rental.get("startTime")
    if not isinstance(start_time, (int, float)):
        raise ValueError("odpowiedź nie zawiera liczbowego pola startTime")
    return datetime_from_seconds(start_time, LOCAL_TIMEZONE).strftime("%Y%m%d")


def gpx_filename(date: str, rental_id: str) -> str:
    return f"{date}_metrorower_{rental_id}.gpx"


def rental_id_from_gpx_filename(name: str) -> str | None:
    match = re.fullmatch(r"\d{8}_metrorower_(\d+)\.gpx", name)
    return match[1] if match else None


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
    distance = rental.get("distance")
    if not isinstance(distance, (int, float)):
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
                raise ValueError("cache nie zawiera obiektu JSON")
            return Ride(rental, "cache", *validate_rental(rental, minimum_metres))
        except ValueError as error:
            print(
                f"[{rental_id}] nieprawidłowy cache ({error}), pobieram ponownie",
                file=sys.stderr,
            )

    rental = fetch_rental(client, rental_id)
    ride = Ride(rental, "API", *validate_rental(rental, minimum_metres))
    save_json(json_path, rental)
    return ride


def station_location(
    place: Any, route_point: TrackPoint, stations: StationsByNumber
) -> Coordinates | None:
    place = place if isinstance(place, dict) else {}
    named_station = stations.get(str(place.get("name")))
    if named_station is not None:
        return float(named_station["lat"]), float(named_station["lng"])

    latitude, longitude = place.get("lat"), place.get("lng")
    if not valid_coordinate(latitude, longitude):
        latitude, longitude = route_point[:2]

    distance, nearest = min(
        (
            (
                equirectangular_distance_metres(
                    (latitude, longitude), (station["lat"], station["lng"])
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


def equirectangular_distance_metres(a: Coordinates, b: Coordinates) -> float:
    cos_latitude = math.cos(math.radians(a[0]))
    return EARTH_RADIUS_METRES * math.hypot(
        math.radians(b[0] - a[0]), cos_latitude * math.radians(b[1] - a[1])
    )


def seconds_between(a: TrackPoint, b: TrackPoint) -> float:
    return abs(
        (
            datetime.fromisoformat(b.iso_time) - datetime.fromisoformat(a.iso_time)
        ).total_seconds()
    )


def index_closest_to_station_near_edge(
    route_points: list[TrackPoint],
    indices_from_edge: range,
    station: Coordinates | None,
) -> int:
    edge_index = indices_from_edge[0]
    if station is None:
        return edge_index
    indices_within_window = [
        index
        for index in indices_from_edge
        if seconds_between(route_points[edge_index], route_points[index])
        <= STATION_SEARCH_WINDOW_SECONDS
    ]
    return min(
        indices_within_window,
        key=lambda index: equirectangular_distance_metres(
            route_points[index][:2], station
        ),
    )


def build_track_points(
    rental: dict[str, Any],
    route_points: list[TrackPoint],
    stations: StationsByNumber,
) -> list[TrackPoint]:
    start_station = station_location(
        rental.get("startPlace"), route_points[0], stations
    )
    end_station = station_location(rental.get("endPlace"), route_points[-1], stations)

    indices = range(len(route_points))
    first = index_closest_to_station_near_edge(route_points, indices, start_station)
    last = index_closest_to_station_near_edge(route_points, indices[::-1], end_station)
    windows_overlap = first > last
    if windows_overlap:
        first, last = 0, len(route_points) - 1
    track_points = route_points[first : last + 1]

    if start_station is not None:
        first_time = track_points[0].iso_time
        start_time = min(rental_time(rental, "startTime", first_time), first_time)
        track_points.insert(0, TrackPoint(*start_station, start_time))
    if end_station is not None:
        last_time = track_points[-1].iso_time
        end_time = max(rental_time(rental, "endTime", last_time), last_time)
        track_points.append(TrackPoint(*end_station, end_time))
    return track_points


def write_gpx(
    path: Path,
    rental: dict[str, Any],
    rental_id: str,
    distance: float,
    track_points: list[TrackPoint],
) -> int:
    name = f"Nextbike {rental_id}"
    gpx = ET.Element(
        f"{{{GPX_NAMESPACE}}}gpx",
        {"version": "1.1", "creator": "metrorower"},
    )
    metadata = ET.SubElement(gpx, f"{{{GPX_NAMESPACE}}}metadata")
    ET.SubElement(metadata, f"{{{GPX_NAMESPACE}}}name").text = name

    track = ET.SubElement(gpx, f"{{{GPX_NAMESPACE}}}trk")
    ET.SubElement(track, f"{{{GPX_NAMESPACE}}}name").text = name
    bike = rental.get("bike")
    description = f"Dystans: {distance} m"
    if isinstance(bike, dict) and bike.get("number"):
        description += f"; rower: {bike['number']}"
    ET.SubElement(track, f"{{{GPX_NAMESPACE}}}desc").text = description
    segment = ET.SubElement(track, f"{{{GPX_NAMESPACE}}}trkseg")

    for latitude, longitude, time in track_points:
        track_point = ET.SubElement(
            segment,
            f"{{{GPX_NAMESPACE}}}trkpt",
            {"lat": str(latitude), "lon": str(longitude)},
        )
        ET.SubElement(track_point, f"{{{GPX_NAMESPACE}}}time").text = time

    ET.indent(gpx, space="  ")
    tree = ET.ElementTree(gpx)
    write_atomically(
        path,
        lambda temporary_path: tree.write(
            temporary_path, encoding="utf-8", xml_declaration=True
        ),
    )
    return len(track_points)


def main() -> int:
    args = parse_args()
    if args.min_distance_km < 0:
        print("Błąd: minimalny dystans nie może być ujemny", file=sys.stderr)
        return 2

    try:
        rental_ids = load_ids(args.ids)
        cookie = load_cookie(args.cookie)
        stations = load_stations(args.stations)
    except ValueError as error:
        print(f"Błąd: {error}", file=sys.stderr)
        return 2

    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.gpx_dir.mkdir(parents=True, exist_ok=True)

    sources: Counter[str] = Counter()
    created = 0
    already_exported = 0
    too_short = 0
    errors = 0
    minimum_metres = args.min_distance_km * 1000
    exported_ids = {
        rental_id
        for path in args.gpx_dir.iterdir()
        if (rental_id := rental_id_from_gpx_filename(path.name)) is not None
    }

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://account.nextbike.pl",
        "Referer": "https://account.nextbike.pl/pl-PL/zz/profile",
        "User-Agent": "Mozilla/5.0 Nextbike-GPX-Exporter/1.0",
    }

    with httpx.Client(
        headers=headers,
        cookies={COOKIE_NAME: cookie},
        timeout=30,
        follow_redirects=True,
    ) as client:
        for rental_id in rental_ids:
            if rental_id in exported_ids:
                already_exported += 1
                print(f"[{rental_id}] pomijam: GPX już istnieje")
                continue

            try:
                ride = load_ride(
                    client,
                    args.data_dir / f"{rental_id}.json",
                    rental_id,
                    minimum_metres,
                )
                sources[ride.source] += 1

                if ride.track_if_long_enough is None:
                    too_short += 1
                    print(
                        f"[{rental_id}] odrzucony: {ride.distance / 1000:.2f} km "
                        f"(< {args.min_distance_km:g} km; dane z {ride.source})"
                    )
                    continue

                gpx_path = args.gpx_dir / gpx_filename(
                    ride.track_if_long_enough.date, rental_id
                )
                point_count = write_gpx(
                    gpx_path,
                    ride.rental,
                    rental_id,
                    ride.distance,
                    build_track_points(
                        ride.rental, ride.track_if_long_enough.route_points, stations
                    ),
                )
                created += 1
                print(
                    f"[{rental_id}] zapisano {gpx_path} "
                    f"({ride.distance / 1000:.2f} km, {point_count} punktów; "
                    f"dane z {ride.source})"
                )
            except httpx.HTTPStatusError as error:
                errors += 1
                status = error.response.status_code
                hint = " — cookie wygasło lub jest niepoprawne" if status == 401 else ""
                print(f"[{rental_id}] błąd HTTP {status}{hint}", file=sys.stderr)
            except (httpx.RequestError, ValueError, OSError) as error:
                errors += 1
                print(f"[{rental_id}] błąd: {error}", file=sys.stderr)

    print(
        "\nPodsumowanie: "
        f"pobrano={sources['API']}, cache={sources['cache']}, "
        f"utworzono_GPX={created}, już_istniało={already_exported}, "
        f"poniżej_limitu={too_short}, błędy={errors}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
