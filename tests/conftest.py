from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from metrorower.models import Coordinates, StationsByNumber, TrackPoint

RIDE_START = datetime(2026, 9, 9, 13, 0, tzinfo=UTC)
METRES_PER_DEGREE_OF_LATITUDE = 111_195
START_STATION_NUMBER = "1"
END_STATION_NUMBER = "2"


def iso_time_after(seconds: float) -> str:
    moment = RIDE_START + timedelta(seconds=seconds)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class Scenario:
    start_station: Coordinates = (50.2635, 19.0112)
    end_station: Coordinates = (50.2595, 19.0644)
    stations: StationsByNumber = field(init=False)

    def __post_init__(self) -> None:
        self.stations = {
            START_STATION_NUMBER: self.station_record(
                START_STATION_NUMBER, self.start_station
            ),
            END_STATION_NUMBER: self.station_record(
                END_STATION_NUMBER, self.end_station
            ),
        }

    @staticmethod
    def station_record(number: str, location: Coordinates) -> dict[str, int | float]:
        return {"number": int(number), "lat": location[0], "lng": location[1]}

    @staticmethod
    def point_at(location: Coordinates, seconds_after_start: float) -> TrackPoint:
        return TrackPoint(*location, iso_time_after(seconds_after_start))

    @staticmethod
    def point_north_of(
        location: Coordinates, metres: float, seconds_after_start: float
    ) -> TrackPoint:
        return TrackPoint(
            location[0] + metres / METRES_PER_DEGREE_OF_LATITUDE,
            location[1],
            iso_time_after(seconds_after_start),
        )

    def points_halfway_between_stations(self, count: int) -> list[TrackPoint]:
        halfway = (
            (self.start_station[0] + self.end_station[0]) / 2,
            (self.start_station[1] + self.end_station[1]) / 2,
        )
        return [self.point_at(halfway, 200 + 10 * i) for i in range(count)]

    def rental(
        self, rented_after_seconds: float = -10, returned_after_seconds: float = 1000
    ) -> dict[str, Any]:
        return {
            "startTime": RIDE_START.timestamp() + rented_after_seconds,
            "endTime": RIDE_START.timestamp() + returned_after_seconds,
            "startPlace": self.place(START_STATION_NUMBER, self.start_station),
            "endPlace": self.place(END_STATION_NUMBER, self.end_station),
        }

    def loop_rental(self) -> dict[str, Any]:
        return self.rental() | {
            "endPlace": self.place(START_STATION_NUMBER, self.start_station)
        }

    @staticmethod
    def place(station_number: str, location: Coordinates) -> dict[str, Any]:
        return {"lat": location[0], "lng": location[1], "name": station_number}


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
    [Callable[[httpx.Request], httpx.Response]], httpx.Client
]:
    def build(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    return build
