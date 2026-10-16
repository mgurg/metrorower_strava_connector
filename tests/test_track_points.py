from dataclasses import replace

import pytest

from metrorower.errors import InvalidRentalData
from metrorower.geo import Coordinates, distance_meters
from metrorower.models import Place
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

    track = build_track_points(scenario.rental(route), scenario.stations)

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

    track = build_track_points(scenario.rental(route), scenario.stations)

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

    track = build_track_points(scenario.loop_rental(route), scenario.stations)

    assert track == [
        scenario.point_at(start, -10),
        *route,
        scenario.point_at(start, 1000),
    ]


def test_route_without_matching_station_is_left_unchanged(scenario):
    far_from_any_station = Coordinates(
        scenario.start_station.latitude + 0.1, scenario.start_station.longitude
    )
    route = [
        scenario.point_at(far_from_any_station, 0),
        scenario.point_north_of(far_from_any_station, 100, 30),
    ]
    rental_from_unknown_place = replace(
        scenario.rental(route),
        start_place=Place("999", far_from_any_station),
        end_place=Place(),
    )

    track = build_track_points(rental_from_unknown_place, scenario.stations)

    assert track == route


def test_single_route_point_lies_between_both_stations(scenario):
    start, end = scenario.start_station, scenario.end_station
    route = [scenario.point_north_of(start, 20, 0)]
    rental = scenario.rental(route, returned_after_seconds=20)

    track = build_track_points(rental, scenario.stations)

    assert track == [
        scenario.point_at(start, -10),
        route[0],
        scenario.point_at(end, 20),
    ]


@pytest.mark.parametrize(
    "returned_after_seconds",
    [985, None],
    ids=["returned-before-last-fix", "no-end-time"],
)
def test_station_points_never_break_time_order(scenario, returned_after_seconds):
    start, end = scenario.start_station, scenario.end_station
    route = [
        scenario.point_north_of(start, 10, 0),
        *scenario.points_halfway_between_stations(2),
        scenario.point_north_of(end, 10, 990),
    ]
    rented_after_first_fix = scenario.rental(
        route,
        rented_after_seconds=5,
        returned_after_seconds=returned_after_seconds,
    )

    track = build_track_points(rented_after_first_fix, scenario.stations)

    assert track[0].time == route[0].time
    assert track[-1].time == route[-1].time
    times = [point.time for point in track]
    assert times == sorted(times)


def test_distance_matches_meters_moved_north(scenario):
    start = scenario.start_station
    hundred_meters_north = scenario.point_north_of(start, 100, 0).coordinates

    distance = distance_meters(start, hundred_meters_north)

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
    rental = scenario.rental(route, returned_after_seconds=30)

    track = build_track_points(rental, scenario.stations)

    assert track == [
        scenario.point_at(start, -10),
        *route,
        scenario.point_at(end, 30),
    ]


def test_rental_without_route_points_has_no_track(scenario):
    with pytest.raises(InvalidRentalData, match="routePoints"):
        build_track_points(scenario.rental([]), scenario.stations)
