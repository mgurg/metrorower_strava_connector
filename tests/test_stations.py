import json

import pytest

from metrorower.stations import (
    DEFAULT_STATIONS_PATH,
    MAX_PLACE_TO_STATION_METRES,
    load_stations,
    station_location,
)


def write_stations(tmp_path, stations):
    path = tmp_path / "stations.json"
    path.write_text(json.dumps(stations), encoding="utf-8")
    return path


def test_stations_are_indexed_by_number_as_text(tmp_path):
    station = {"number": 27163, "lat": 50.26, "lng": 19.01}

    stations = load_stations(write_stations(tmp_path, [station]))

    assert stations == {"27163": station}


def test_bundled_stations_file_is_valid():
    assert load_stations(DEFAULT_STATIONS_PATH)


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
    with pytest.raises(ValueError):
        load_stations(write_stations(tmp_path, stations))


def test_place_without_station_number_uses_nearest_station_in_range(scenario):
    near_start = scenario.point_north_of(
        scenario.start_station, MAX_PLACE_TO_STATION_METRES - 50, 0
    )
    place = {"lat": near_start.latitude, "lng": near_start.longitude}

    location = station_location(place, near_start, scenario.stations)

    assert location == scenario.start_station


def test_place_farther_than_limit_from_every_station_has_no_station(scenario):
    beyond_limit = scenario.point_north_of(
        scenario.start_station, -(MAX_PLACE_TO_STATION_METRES + 50), 0
    )
    place = {"lat": beyond_limit.latitude, "lng": beyond_limit.longitude}

    assert station_location(place, beyond_limit, scenario.stations) is None


def test_place_without_coordinates_falls_back_to_route_point(scenario):
    near_end = scenario.point_north_of(scenario.end_station, 20, 0)

    location = station_location(None, near_end, scenario.stations)

    assert location == scenario.end_station
