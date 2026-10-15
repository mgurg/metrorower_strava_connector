import pytest

from nextbike_to_gpx import (
    STATION_SEARCH_WINDOW_SECONDS,
    build_track_points,
    equirectangular_distance_metres,
)


def test_points_recorded_before_reaching_closest_to_start_station_are_dropped(
    start_station,
    end_station,
    stations,
    rental,
    station_point,
    point_north_of,
    points_halfway_between_stations,
):
    gps_not_fixed_yet = point_north_of(start_station, -520, 0)
    route = [
        gps_not_fixed_yet,
        point_north_of(start_station, 80, 25),
        point_north_of(start_station, 160, 35),
        *points_halfway_between_stations(3),
        point_north_of(end_station, 12, 990),
    ]

    track = build_track_points(rental(), route, stations)

    assert track == [
        station_point(start_station, -10),
        *route[1:],
        station_point(end_station, 1000),
    ]


def test_points_recorded_after_closest_to_end_station_are_dropped(
    start_station,
    end_station,
    stations,
    rental,
    point_north_of,
    points_halfway_between_stations,
):
    closest_to_end_station = point_north_of(end_station, 12, 990)
    waiting_at_dock = [point_north_of(end_station, 15, 995)] * 4
    route = [
        point_north_of(start_station, 5, 0),
        *points_halfway_between_stations(3),
        point_north_of(end_station, 30, 980),
        closest_to_end_station,
        *waiting_at_dock,
    ]

    track = build_track_points(rental(), route, stations)

    assert track[-2] == closest_to_end_station


def test_loop_ride_passing_start_station_after_search_window_keeps_whole_route(
    start_station, stations, rental, station_point, point_north_of
):
    passing_start_station = point_north_of(
        start_station, 5, STATION_SEARCH_WINDOW_SECONDS + 1
    )
    route = [
        point_north_of(start_station, 30, 0),
        point_north_of(start_station, 1500, 60),
        passing_start_station,
        point_north_of(start_station, 1500, 900),
        point_north_of(start_station, 20, 990),
    ]
    loop_rental = rental() | {"endPlace": {"name": "1"}}

    track = build_track_points(loop_rental, route, stations)

    assert track == [
        station_point(start_station, -10),
        *route,
        station_point(start_station, 1000),
    ]


def test_route_without_matching_station_is_left_unchanged(
    start_station, stations, rental, station_point, point_north_of
):
    far_from_any_station = (start_station[0] + 0.1, start_station[1])
    route = [
        station_point(far_from_any_station, 0),
        point_north_of(far_from_any_station, 100, 30),
    ]
    rental_from_unknown_place = rental() | {
        "startPlace": {"lat": far_from_any_station[0], "lng": far_from_any_station[1]},
        "endPlace": {},
    }

    track = build_track_points(rental_from_unknown_place, route, stations)

    assert track == route


def test_single_route_point_lies_between_both_stations(
    start_station, end_station, stations, rental, station_point, point_north_of
):
    route = [point_north_of(start_station, 20, 0)]

    track = build_track_points(rental(returned_after_seconds=20), route, stations)

    assert track == [
        station_point(start_station, -10),
        route[0],
        station_point(end_station, 20),
    ]


@pytest.mark.parametrize("missing_field", [None, "startTime", "endTime"])
def test_station_points_never_break_time_order(
    missing_field,
    start_station,
    end_station,
    stations,
    rental,
    point_north_of,
    points_halfway_between_stations,
):
    route = [
        point_north_of(start_station, 10, 0),
        *points_halfway_between_stations(2),
        point_north_of(end_station, 10, 990),
    ]
    rented_after_first_fix_and_returned_before_last = rental(
        rented_after_seconds=5, returned_after_seconds=985
    )
    rented_after_first_fix_and_returned_before_last.pop(missing_field, None)

    track = build_track_points(
        rented_after_first_fix_and_returned_before_last, route, stations
    )

    assert track[0].iso_time == route[0].iso_time
    assert track[-1].iso_time == route[-1].iso_time
    times = [point.iso_time for point in track]
    assert times == sorted(times)


def test_equirectangular_distance_matches_metres_moved_north(
    start_station, point_north_of
):
    hundred_metres_north = point_north_of(start_station, 100, 0)[:2]

    distance = equirectangular_distance_metres(start_station, hundred_metres_north)

    assert distance == pytest.approx(100, abs=0.5)
