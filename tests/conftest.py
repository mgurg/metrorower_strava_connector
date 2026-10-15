from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from nextbike_to_gpx import Coordinates, StationsByNumber, TrackPoint

RIDE_START = datetime(2026, 9, 9, 13, 0, tzinfo=UTC)
METRES_PER_DEGREE_OF_LATITUDE = 111_195

PointNorthOf = Callable[[Coordinates, float, float], TrackPoint]
StationPoint = Callable[[Coordinates, float], TrackPoint]


@pytest.fixture
def start_station() -> Coordinates:
    return (50.2635, 19.0112)


@pytest.fixture
def end_station() -> Coordinates:
    return (50.2595, 19.0644)


@pytest.fixture
def stations(start_station: Coordinates, end_station: Coordinates) -> StationsByNumber:
    return {
        "1": {"number": 1, "lat": start_station[0], "lng": start_station[1]},
        "2": {"number": 2, "lat": end_station[0], "lng": end_station[1]},
    }


def iso_time_after(seconds: float) -> str:
    moment = RIDE_START + timedelta(seconds=seconds)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@pytest.fixture
def station_point() -> StationPoint:
    def build(station: Coordinates, seconds_after_start: float) -> TrackPoint:
        return TrackPoint(*station, iso_time_after(seconds_after_start))

    return build


@pytest.fixture
def point_north_of() -> PointNorthOf:
    def build(
        station: Coordinates, metres: float, seconds_after_start: float
    ) -> TrackPoint:
        return TrackPoint(
            station[0] + metres / METRES_PER_DEGREE_OF_LATITUDE,
            station[1],
            iso_time_after(seconds_after_start),
        )

    return build


@pytest.fixture
def points_halfway_between_stations(
    start_station: Coordinates, end_station: Coordinates, station_point: StationPoint
) -> Callable[[int], list[TrackPoint]]:
    halfway = (
        (start_station[0] + end_station[0]) / 2,
        (start_station[1] + end_station[1]) / 2,
    )

    def build(count: int) -> list[TrackPoint]:
        return [station_point(halfway, 200 + 10 * i) for i in range(count)]

    return build


@pytest.fixture
def rental(
    start_station: Coordinates, end_station: Coordinates
) -> Callable[..., dict[str, Any]]:
    def build(
        rented_after_seconds: float = -10, returned_after_seconds: float = 1000
    ) -> dict[str, Any]:
        return {
            "startTime": RIDE_START.timestamp() + rented_after_seconds,
            "endTime": RIDE_START.timestamp() + returned_after_seconds,
            "startPlace": {
                "lat": start_station[0],
                "lng": start_station[1],
                "name": "1",
            },
            "endPlace": {"lat": end_station[0], "lng": end_station[1], "name": "2"},
        }

    return build
