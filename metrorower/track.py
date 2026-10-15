from __future__ import annotations

from datetime import datetime
from typing import Any

from metrorower.models import Coordinates, StationsByNumber, TrackPoint, rental_time
from metrorower.stations import equirectangular_distance_metres, station_location

STATION_SEARCH_WINDOW_SECONDS = 120


def seconds_between(a: TrackPoint, b: TrackPoint) -> float:
    return abs(
        (
            datetime.fromisoformat(b.iso_time) - datetime.fromisoformat(a.iso_time)
        ).total_seconds()
    )


def index_closest_to_station_near_edge(
    route_points: list[TrackPoint],
    indices_from_edge: range,
    station: Coordinates | None,
) -> int:
    edge_index = indices_from_edge[0]
    if station is None:
        return edge_index
    indices_within_window = [
        index
        for index in indices_from_edge
        if seconds_between(route_points[edge_index], route_points[index])
        <= STATION_SEARCH_WINDOW_SECONDS
    ]
    return min(
        indices_within_window,
        key=lambda index: equirectangular_distance_metres(
            route_points[index][:2], station
        ),
    )


def build_track_points(
    rental: dict[str, Any],
    route_points: list[TrackPoint],
    stations: StationsByNumber,
) -> list[TrackPoint]:
    start_station = station_location(
        rental.get("startPlace"), route_points[0], stations
    )
    end_station = station_location(rental.get("endPlace"), route_points[-1], stations)

    indices = range(len(route_points))
    first = index_closest_to_station_near_edge(route_points, indices, start_station)
    last = index_closest_to_station_near_edge(route_points, indices[::-1], end_station)
    windows_overlap = first > last
    if windows_overlap:
        first, last = 0, len(route_points) - 1
    track_points = route_points[first : last + 1]

    if start_station is not None:
        first_time = track_points[0].iso_time
        start_time = min(rental_time(rental, "startTime", first_time), first_time)
        track_points.insert(0, TrackPoint(*start_station, start_time))
    if end_station is not None:
        last_time = track_points[-1].iso_time
        end_time = max(rental_time(rental, "endTime", last_time), last_time)
        track_points.append(TrackPoint(*end_station, end_time))
    return track_points
