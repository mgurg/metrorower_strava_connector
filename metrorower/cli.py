from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path

from metrorower.errors import InvalidFileError
from metrorower.export import (
    MIN_EXPORTED_DISTANCE_METERS,
    AlreadyExported,
    Exported,
    ExportResult,
    ExportSettings,
    Failed,
    Outcome,
    RideExporter,
    TooShort,
)
from metrorower.files import load_ids
from metrorower.nextbike import NextbikeApi, load_cookie, nextbike_client
from metrorower.rentals import CachedRentals, Source
from metrorower.stations import STATIONS_PATH, load_stations

EXIT_OK = 0
EXIT_SOME_RIDES_FAILED = 1
EXIT_INVALID_INPUT = 2
METERS_PER_KILOMETER = 1000


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
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
    return parser.parse_args(argv)


def describe(result: ExportResult) -> str:
    match result:
        case AlreadyExported(rental_id=rental_id):
            return f"[{rental_id}] pomijam: GPX już istnieje"
        case TooShort(rental_id=rental_id, source=source, distance_meters=meters):
            return (
                f"[{rental_id}] odrzucony: {meters / METERS_PER_KILOMETER:.2f} km "
                f"(< {MIN_EXPORTED_DISTANCE_METERS / METERS_PER_KILOMETER:g} km; "
                f"dane z {source})"
            )
        case Exported(
            rental_id=rental_id,
            source=source,
            distance_meters=meters,
            gpx_path=gpx_path,
            point_count=point_count,
        ):
            return (
                f"[{rental_id}] zapisano {gpx_path} "
                f"({meters / METERS_PER_KILOMETER:.2f} km, {point_count} punktów; "
                f"dane z {source})"
            )
        case Failed(rental_id=rental_id, error=error):
            return f"[{rental_id}] błąd: {error}"


def summary(results: Iterable[ExportResult]) -> str:
    results = list(results)
    outcomes = Counter(result.outcome for result in results)
    sources = Counter(
        result.source for result in results if isinstance(result, (TooShort, Exported))
    )
    counts = [
        f"pobrano={sources[Source.API]}",
        f"cache={sources[Source.CACHE]}",
        *(f"{outcome}={outcomes[outcome]}" for outcome in Outcome),
    ]
    return "Podsumowanie: " + ", ".join(counts)


def exit_code(results: Iterable[ExportResult]) -> int:
    failed = any(isinstance(result, Failed) for result in results)
    return EXIT_SOME_RIDES_FAILED if failed else EXIT_OK


def report_progress(results: Iterable[ExportResult]) -> list[ExportResult]:
    reported: list[ExportResult] = []
    for result in results:
        stream = sys.stderr if isinstance(result, Failed) else sys.stdout
        print(describe(result), file=stream)
        reported.append(result)
    return reported


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(format="%(message)s")

    try:
        rental_ids = load_ids(args.ids)
        cookie = load_cookie(args.cookie)
        stations = load_stations(STATIONS_PATH)
    except InvalidFileError as error:
        print(f"Błąd: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.gpx_dir.mkdir(parents=True, exist_ok=True)
    settings = ExportSettings(args.gpx_dir, stations)

    with nextbike_client(cookie) as client:
        rentals = CachedRentals(args.data_dir, NextbikeApi(client))
        exporter = RideExporter(rentals, settings)
        results = report_progress(exporter.export_all(rental_ids))

    print(f"\n{summary(results)}")
    return exit_code(results)
