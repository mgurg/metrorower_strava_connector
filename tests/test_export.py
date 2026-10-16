from dataclasses import replace
from datetime import date

import pytest

from metrorower.errors import SessionExpired
from metrorower.export import (
    MIN_EXPORTED_DISTANCE_METERS,
    AlreadyExported,
    Exported,
    ExportSettings,
    Failed,
    RideExporter,
    TooShort,
)
from metrorower.gpx import gpx_filename
from metrorower.rentals import LoadedRental, Source


class FakeRentals:
    def __init__(self, rentals=None, errors=None):
        self.rentals = rentals or {}
        self.errors = errors or {}

    def load(self, rental_id):
        if rental_id in self.errors:
            raise self.errors[rental_id]
        return LoadedRental(self.rentals[rental_id], Source.CACHE)


@pytest.fixture
def exporter_for(tmp_path, scenario):
    def build(rentals):
        settings = ExportSettings(tmp_path, scenario.stations)
        return RideExporter(rentals, settings)

    return build


@pytest.fixture
def long_ride(scenario):
    route = [
        scenario.point_north_of(scenario.start_station, 10, 0),
        scenario.point_north_of(scenario.end_station, 10, 990),
    ]
    return scenario.rental(route)


def test_long_ride_is_written_as_gpx_named_by_local_date(
    exporter_for, long_ride, tmp_path
):
    result = exporter_for(FakeRentals({"1": long_ride})).export("1")

    expected_path = tmp_path / gpx_filename(date(2026, 9, 9), "1")
    assert result == Exported("1", Source.CACHE, 4000, expected_path, 4)
    assert expected_path.exists()


def test_ride_shorter_than_minimum_is_not_written(exporter_for, scenario, tmp_path):
    shorter_than_minimum = MIN_EXPORTED_DISTANCE_METERS - 1
    short_ride = replace(scenario.rental([]), distance_meters=shorter_than_minimum)

    result = exporter_for(FakeRentals({"1": short_ride})).export("1")

    assert result == TooShort("1", Source.CACHE, shorter_than_minimum)
    assert list(tmp_path.iterdir()) == []


def test_loading_error_is_reported_as_failure(exporter_for):
    expired = SessionExpired(401)

    result = exporter_for(FakeRentals(errors={"1": expired})).export("1")

    assert result == Failed("1", expired)


def test_long_ride_without_route_points_is_a_failure(exporter_for, scenario):
    result = exporter_for(FakeRentals({"1": scenario.rental([])})).export("1")

    assert isinstance(result, Failed)
    assert "routePoints" in str(result.error)


def test_already_exported_rides_are_skipped_without_loading(
    exporter_for, long_ride, tmp_path
):
    (tmp_path / gpx_filename(date(2026, 9, 9), "1")).touch()
    rentals = FakeRentals({"2": long_ride})

    results = list(exporter_for(rentals).export_all(["1", "2"]))

    assert results[0] == AlreadyExported("1")
    assert isinstance(results[1], Exported)
