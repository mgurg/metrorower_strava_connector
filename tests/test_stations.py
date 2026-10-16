import json

import pytest

from metrorower.errors import InvalidFileError
from metrorower.geo import Coordinates
from metrorower.models import Place
from metrorower.stations import (
    MAX_PLACE_TO_STATION_METERS,
    STATIONS_PATH,
    Station,
    load_stations,
)


def write_stations(tmp_path, stations):
    path = tmp_path / "stations.json"
    path.write_text(json.dumps(stations), encoding="utf-8")
    return path


def test_stations_are_indexed_by_number_as_text(tmp_path):
    raw_station = {"number": 27163, "lat": 50.26, "lng": 19.01}

    stations = load_stations(write_stations(tmp_path, [raw_station]))

    assert stations["27163"] == Station(27163, Coordinates(50.26, 19.01))


def test_bundled_stations_file_is_valid():
    assert len(load_stations(STATIONS_PATH)) > 0


@pytest.mark.parametrize(
    "stations",
    [
        [],
        {"number": 1, "lat": 50.0, "lng": 19.0},
        [{"number": True, "lat": 50.0, "lng": 19.0}],
        [{"number": "1", "lat": 50.0, "lng": 19.0}],
        [{"number": 1, "lat": 50.0}],
        [{"number": 1, "lat": 95.0, "lng": 19.0}],
    ],
    ids=[
        "empty",
        "not-a-list",
        "boolean-number",
        "text-number",
        "no-longitude",
        "latitude-out-of-range",
    ],
)
def test_invalid_stations_file_is_rejected(tmp_path, stations):
    with pytest.raises(InvalidFileError):
        load_stations(write_stations(tmp_path, stations))


def test_place_with_known_station_number_uses_that_station(scenario):
    far_away = Coordinates(0.0, 0.0)
    place = Place("2", far_away)

    assert scenario.stations.locate(place, far_away) == scenario.end_station


def test_place_without_station_number_uses_nearest_station_in_range(scenario):
    near_start = scenario.point_north_of(
        scenario.start_station, MAX_PLACE_TO_STATION_METERS - 50, 0
    ).coordinates

    location = scenario.stations.locate(Place(location=near_start), near_start)

    assert location == scenario.start_station


def test_place_farther_than_limit_from_every_station_has_no_station(scenario):
    beyond_limit = scenario.point_north_of(
        scenario.start_station, -(MAX_PLACE_TO_STATION_METERS + 50), 0
    ).coordinates

    assert scenario.stations.locate(Place(location=beyond_limit), beyond_limit) is None


def test_place_without_coordinates_falls_back_to_route_point(scenario):
    near_end = scenario.point_north_of(scenario.end_station, 20, 0).coordinates

    location = scenario.stations.locate(Place(), near_end)

    assert location == scenario.end_station
