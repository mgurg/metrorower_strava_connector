from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

from metrorower.errors import MetrorowerError
from metrorower.gpx import exported_rental_ids, gpx_filename, write_gpx
from metrorower.rentals import RentalRepository, Source
from metrorower.stations import Stations
from metrorower.track import build_track_points

MIN_EXPORTED_DISTANCE_METERS = 1000


class Outcome(StrEnum):
    EXPORTED = "utworzono_GPX"
    ALREADY_EXPORTED = "już_istniało"
    TOO_SHORT = "poniżej_limitu"
    FAILED = "błędy"


@dataclass(frozen=True)
class ExportSettings:
    gpx_dir: Path
    stations: Stations


@dataclass(frozen=True)
class AlreadyExported:
    outcome: ClassVar[Outcome] = Outcome.ALREADY_EXPORTED
    rental_id: str


@dataclass(frozen=True)
class TooShort:
    outcome: ClassVar[Outcome] = Outcome.TOO_SHORT
    rental_id: str
    source: Source
    distance_meters: float


@dataclass(frozen=True)
class Exported:
    outcome: ClassVar[Outcome] = Outcome.EXPORTED
    rental_id: str
    source: Source
    distance_meters: float
    gpx_path: Path
    point_count: int


@dataclass(frozen=True)
class Failed:
    outcome: ClassVar[Outcome] = Outcome.FAILED
    rental_id: str
    error: MetrorowerError | OSError


ExportResult = AlreadyExported | TooShort | Exported | Failed


class RideExporter:
    def __init__(self, rentals: RentalRepository, settings: ExportSettings) -> None:
        self._rentals = rentals
        self._settings = settings

    def export_all(self, rental_ids: Iterable[str]) -> Iterator[ExportResult]:
        already_exported = exported_rental_ids(self._settings.gpx_dir)
        for rental_id in rental_ids:
            if rental_id in already_exported:
                yield AlreadyExported(rental_id)
            else:
                yield self.export(rental_id)

    def export(self, rental_id: str) -> ExportResult:
        try:
            return self._export(rental_id)
        except (MetrorowerError, OSError) as error:
            return Failed(rental_id, error)

    def _export(self, rental_id: str) -> ExportResult:
        rental, source = self._rentals.load(rental_id)
        if rental.distance_meters < MIN_EXPORTED_DISTANCE_METERS:
            return TooShort(rental_id, source, rental.distance_meters)

        track_points = build_track_points(rental, self._settings.stations)
        gpx_path = self._settings.gpx_dir / gpx_filename(
            rental.local_start_date, rental_id
        )
        write_gpx(gpx_path, rental, track_points)
        return Exported(
            rental_id, source, rental.distance_meters, gpx_path, len(track_points)
        )
