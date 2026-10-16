from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from metrorower.geo import Coordinates
from metrorower.models import Place, Rental, TrackPoint
from metrorower.nextbike import NextbikeApi
from metrorower.stations import Station, Stations

RIDE_START = datetime(2026, 9, 9, 13, 0, tzinfo=UTC)
METERS_PER_DEGREE_OF_LATITUDE = 111_195
START_STATION_NUMBER = 1
END_STATION_NUMBER = 2
DEFAULT_START_STATION = Coordinates(50.2635, 19.0112)
DEFAULT_END_STATION = Coordinates(50.2595, 19.0644)


def time_after(seconds: float) -> datetime:
    return RIDE_START + timedelta(seconds=seconds)


@dataclass
class Scenario:
    start_station: Coordinates = DEFAULT_START_STATION
    end_station: Coordinates = DEFAULT_END_STATION
    stations: Stations = field(init=False)

    def __post_init__(self) -> None:
        self.stations = Stations(
            [
                Station(START_STATION_NUMBER, self.start_station),
                Station(END_STATION_NUMBER, self.end_station),
            ]
        )

    @staticmethod
    def point_at(location: Coordinates, seconds_after_start: float) -> TrackPoint:
        return TrackPoint(*location, time_after(seconds_after_start))

    @staticmethod
    def point_north_of(
        location: Coordinates, meters: float, seconds_after_start: float
    ) -> TrackPoint:
        return TrackPoint(
            location.latitude + meters / METERS_PER_DEGREE_OF_LATITUDE,
            location.longitude,
            time_after(seconds_after_start),
        )

    def points_halfway_between_stations(self, count: int) -> list[TrackPoint]:
        halfway = Coordinates(
            (self.start_station.latitude + self.end_station.latitude) / 2,
            (self.start_station.longitude + self.end_station.longitude) / 2,
        )
        return [self.point_at(halfway, 200 + 10 * i) for i in range(count)]

    def rental(
        self,
        route: list[TrackPoint],
        rented_after_seconds: float = -10,
        returned_after_seconds: float | None = 1000,
    ) -> Rental:
        return Rental(
            rental_id="1",
            distance_meters=4000,
            start_time=time_after(rented_after_seconds),
            end_time=(
                None
                if returned_after_seconds is None
                else time_after(returned_after_seconds)
            ),
            start_place=self.place(START_STATION_NUMBER, self.start_station),
            end_place=self.place(END_STATION_NUMBER, self.end_station),
            route_points=tuple(route),
        )

    def loop_rental(self, route: list[TrackPoint]) -> Rental:
        return replace(
            self.rental(route),
            end_place=self.place(START_STATION_NUMBER, self.start_station),
        )

    @staticmethod
    def place(station_number: int, location: Coordinates) -> Place:
        return Place(str(station_number), location)


@pytest.fixture
def scenario() -> Scenario:
    return Scenario()


@pytest.fixture
def api_rental() -> Callable[..., dict[str, Any]]:
    def build(distance: float = 4000, **fields: Any) -> dict[str, Any]:
        return {
            "distance": distance,
            "startTime": RIDE_START.timestamp(),
            "routePoints": [
                {"lat": 50.26, "lng": 19.01, "ts": RIDE_START.timestamp() * 1000},
                {
                    "lat": 50.27,
                    "lng": 19.02,
                    "ts": RIDE_START.timestamp() * 1000 + 15_000,
                },
            ],
        } | fields

    return build


@pytest.fixture
def nextbike_api() -> Callable[
    [Callable[[httpx.Request], httpx.Response]], NextbikeApi
]:
    def build(handler: Callable[[httpx.Request], httpx.Response]) -> NextbikeApi:
        return NextbikeApi(httpx.Client(transport=httpx.MockTransport(handler)))

    return build
