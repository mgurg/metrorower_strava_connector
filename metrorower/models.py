from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import NamedTuple
from zoneinfo import ZoneInfo

from metrorower.geo import Coordinates

LOCAL_TIMEZONE = ZoneInfo("Europe/Warsaw")


class TrackPoint(NamedTuple):
    latitude: float
    longitude: float
    time: datetime

    @property
    def coordinates(self) -> Coordinates:
        return Coordinates(self.latitude, self.longitude)


@dataclass(frozen=True)
class Place:
    station_number: str | None = None
    location: Coordinates | None = None


@dataclass(frozen=True)
class Rental:
    rental_id: str
    distance_meters: float
    start_time: datetime
    end_time: datetime | None = None
    start_place: Place = Place()
    end_place: Place = Place()
    bike_number: str | None = None
    route_points: tuple[TrackPoint, ...] = ()

    @property
    def local_start_date(self) -> date:
        return self.start_time.astimezone(LOCAL_TIMEZONE).date()
