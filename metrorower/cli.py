from __future__ import annotations

import argparse
import sys
from collections import Counter
from enum import StrEnum
from pathlib import Path
from typing import NamedTuple

import httpx

from metrorower.files import load_ids
from metrorower.gpx import exported_rental_ids, gpx_filename, write_gpx
from metrorower.models import Ride, StationsByNumber
from metrorower.nextbike import load_cookie, load_ride, nextbike_client
from metrorower.stations import DEFAULT_STATIONS_PATH, load_stations
from metrorower.track import build_track_points


class ExportSettings(NamedTuple):
    data_dir: Path
    gpx_dir: Path
    min_distance_km: float
    stations: StationsByNumber


class Outcome(StrEnum):
    EXPORTED = "utworzono_GPX"
    ALREADY_EXPORTED = "już_istniało"
    TOO_SHORT = "poniżej_limitu"
    FAILED = "błędy"


class ExportResult(NamedTuple):
    outcome: Outcome
    source: str | None = None


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


def export_loaded_ride(ride: Ride, settings: ExportSettings) -> Outcome:
    distance_km = ride.distance / 1000
    track = ride.track_if_long_enough
    if track is None:
        print(
            f"[{ride.rental_id}] odrzucony: {distance_km:.2f} km "
            f"(< {settings.min_distance_km:g} km; dane z {ride.source})"
        )
        return Outcome.TOO_SHORT

    gpx_path = settings.gpx_dir / gpx_filename(track.date, ride.rental_id)
    track_points = build_track_points(
        ride.rental, track.route_points, settings.stations
    )
    write_gpx(gpx_path, ride, track_points)
    print(
        f"[{ride.rental_id}] zapisano {gpx_path} "
        f"({distance_km:.2f} km, {len(track_points)} punktów; dane z {ride.source})"
    )
    return Outcome.EXPORTED


def export_ride(
    client: httpx.Client, settings: ExportSettings, rental_id: str
) -> ExportResult:
    try:
        ride = load_ride(
            client,
            settings.data_dir / f"{rental_id}.json",
            rental_id,
            settings.min_distance_km * 1000,
        )
        return ExportResult(export_loaded_ride(ride, settings), ride.source)
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        hint = " — cookie wygasło lub jest niepoprawne" if status == 401 else ""
        print(f"[{rental_id}] błąd HTTP {status}{hint}", file=sys.stderr)
    except (httpx.RequestError, ValueError, OSError) as error:
        print(f"[{rental_id}] błąd: {error}", file=sys.stderr)
    return ExportResult(Outcome.FAILED)


def print_summary(outcomes: Counter[Outcome], sources: Counter[str | None]) -> None:
    print(
        f"\nPodsumowanie: pobrano={sources['API']}, cache={sources['cache']}, "
        + ", ".join(f"{outcome}={outcomes[outcome]}" for outcome in Outcome)
    )


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
    settings = ExportSettings(
        args.data_dir, args.gpx_dir, args.min_distance_km, stations
    )
    already_exported = exported_rental_ids(args.gpx_dir)

    outcomes: Counter[Outcome] = Counter()
    sources: Counter[str | None] = Counter()
    with nextbike_client(cookie) as client:
        for rental_id in rental_ids:
            if rental_id in already_exported:
                print(f"[{rental_id}] pomijam: GPX już istnieje")
                outcomes[Outcome.ALREADY_EXPORTED] += 1
                continue
            result = export_ride(client, settings, rental_id)
            outcomes[result.outcome] += 1
            sources[result.source] += 1

    print_summary(outcomes, sources)
    return 1 if outcomes[Outcome.FAILED] else 0
