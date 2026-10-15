import pytest

from metrorower.stations import equirectangular_distance_metres
from metrorower.track import STATION_SEARCH_WINDOW_SECONDS, build_track_points


def test_points_recorded_before_reaching_closest_to_start_station_are_dropped(
    scenario,
):
    start, end = scenario.start_station, scenario.end_station
    gps_not_fixed_yet = scenario.point_north_of(start, -520, 0)
    route = [
        gps_not_fixed_yet,
        scenario.point_north_of(start, 80, 25),
        scenario.point_north_of(start, 160, 35),
        *scenario.points_halfway_between_stations(3),
        scenario.point_north_of(end, 12, 990),
    ]

    track = build_track_points(scenario.rental(), route, scenario.stations)

    assert track == [
        scenario.point_at(start, -10),
        *route[1:],
        scenario.point_at(end, 1000),
    ]


def test_points_recorded_after_closest_to_end_station_are_dropped(scenario):
    start, end = scenario.start_station, scenario.end_station
    closest_to_end_station = scenario.point_north_of(end, 12, 990)
    waiting_at_dock = [scenario.point_north_of(end, 15, 995)] * 4
    route = [
        scenario.point_north_of(start, 5, 0),
        *scenario.points_halfway_between_stations(3),
        scenario.point_north_of(end, 30, 980),
        closest_to_end_station,
        *waiting_at_dock,
    ]

    track = build_track_points(scenario.rental(), route, scenario.stations)

    assert track[-2] == closest_to_end_station


def test_loop_ride_passing_start_station_after_search_window_keeps_whole_route(
    scenario,
):
    start = scenario.start_station
    passing_start_station = scenario.point_north_of(
        start, 5, STATION_SEARCH_WINDOW_SECONDS + 1
    )
    route = [
        scenario.point_north_of(start, 30, 0),
        scenario.point_north_of(start, 1500, 60),
        passing_start_station,
        scenario.point_north_of(start, 1500, 900),
        scenario.point_north_of(start, 20, 990),
    ]

    track = build_track_points(scenario.loop_rental(), route, scenario.stations)

    assert track == [
        scenario.point_at(start, -10),
        *route,
        scenario.point_at(start, 1000),
    ]


def test_route_without_matching_station_is_left_unchanged(scenario):
    far_from_any_station = (scenario.start_station[0] + 0.1, scenario.start_station[1])
    route = [
        scenario.point_at(far_from_any_station, 0),
        scenario.point_north_of(far_from_any_station, 100, 30),
    ]
    rental_from_unknown_place = scenario.rental() | {
        "startPlace": scenario.place("999", far_from_any_station),
        "endPlace": {},
    }

    track = build_track_points(rental_from_unknown_place, route, scenario.stations)

    assert track == route


def test_single_route_point_lies_between_both_stations(scenario):
    start, end = scenario.start_station, scenario.end_station
    route = [scenario.point_north_of(start, 20, 0)]
    rental = scenario.rental(returned_after_seconds=20)

    track = build_track_points(rental, route, scenario.stations)

    assert track == [
        scenario.point_at(start, -10),
        route[0],
        scenario.point_at(end, 20),
    ]


@pytest.mark.parametrize("missing_field", [None, "startTime", "endTime"])
def test_station_points_never_break_time_order(scenario, missing_field):
    start, end = scenario.start_station, scenario.end_station
    route = [
        scenario.point_north_of(start, 10, 0),
        *scenario.points_halfway_between_stations(2),
        scenario.point_north_of(end, 10, 990),
    ]
    rented_after_first_fix_and_returned_before_last = scenario.rental(
        rented_after_seconds=5, returned_after_seconds=985
    )
    rented_after_first_fix_and_returned_before_last.pop(missing_field, None)

    track = build_track_points(
        rented_after_first_fix_and_returned_before_last, route, scenario.stations
    )

    assert track[0].iso_time == route[0].iso_time
    assert track[-1].iso_time == route[-1].iso_time
    times = [point.iso_time for point in track]
    assert times == sorted(times)


def test_equirectangular_distance_matches_metres_moved_north(scenario):
    start = scenario.start_station
    hundred_metres_north = scenario.point_north_of(start, 100, 0)[:2]

    distance = equirectangular_distance_metres(start, hundred_metres_north)

    assert distance == pytest.approx(100, abs=0.5)


def test_short_ride_recorded_from_end_station_towards_start_keeps_whole_route(
    scenario,
):
    start, end = scenario.start_station, scenario.end_station
    route = [
        scenario.point_north_of(end, 10, 0),
        scenario.point_north_of(start, 2000, 10),
        scenario.point_north_of(start, 10, 20),
    ]
    rental = scenario.rental(returned_after_seconds=30)

    track = build_track_points(rental, route, scenario.stations)

    assert track == [
        scenario.point_at(start, -10),
        *route,
        scenario.point_at(end, 30),
    ]
