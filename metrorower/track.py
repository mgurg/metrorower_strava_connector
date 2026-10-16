from __future__ import annotations

from metrorower.errors import InvalidRentalData
from metrorower.geo import Coordinates, distance_meters
from metrorower.models import Rental, TrackPoint
from metrorower.stations import Stations

STATION_SEARCH_WINDOW_SECONDS = 120


def seconds_between(a: TrackPoint, b: TrackPoint) -> float:
    return abs((b.time - a.time).total_seconds())


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
        key=lambda index: distance_meters(route_points[index].coordinates, station),
    )


def build_track_points(rental: Rental, stations: Stations) -> list[TrackPoint]:
    route_points = list(rental.route_points)
    if not route_points:
        raise InvalidRentalData("brak punktów routePoints")

    start_station = stations.locate(rental.start_place, route_points[0].coordinates)
    end_station = stations.locate(rental.end_place, route_points[-1].coordinates)

    indices = range(len(route_points))
    first = index_closest_to_station_near_edge(route_points, indices, start_station)
    last = index_closest_to_station_near_edge(route_points, indices[::-1], end_station)
    windows_overlap = first > last
    if windows_overlap:
        first, last = 0, len(route_points) - 1
    track_points = route_points[first : last + 1]

    if start_station is not None:
        start_time = min(rental.start_time, track_points[0].time)
        track_points.insert(0, TrackPoint(*start_station, start_time))
    if end_station is not None:
        last_time = track_points[-1].time
        end_time = max(rental.end_time or last_time, last_time)
        track_points.append(TrackPoint(*end_station, end_time))
    return track_points
