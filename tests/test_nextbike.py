from datetime import UTC, date, datetime

import httpx
import pytest

from metrorower.errors import (
    InvalidRentalData,
    NetworkError,
    NextbikeApiError,
    SessionExpired,
)
from metrorower.geo import Coordinates
from metrorower.models import Place, TrackPoint
from metrorower.nextbike import parse_rental

RENTAL_ID = "360039555"


def test_route_points_are_sorted_by_time(api_rental):
    rental = parse_rental(
        api_rental(
            routePoints=[
                {"lat": 50.2, "lng": 19.2, "ts": 1_788_959_284_487},
                {"lat": 50.1, "lng": 19.1, "ts": 1_788_959_259_526},
            ]
        ),
        RENTAL_ID,
    )

    assert rental.route_points == (
        TrackPoint(50.1, 19.1, datetime(2026, 9, 9, 13, 7, 39, 526_000, tzinfo=UTC)),
        TrackPoint(50.2, 19.2, datetime(2026, 9, 9, 13, 8, 4, 487_000, tzinfo=UTC)),
    )


@pytest.mark.parametrize(
    "route_points",
    [
        {"lat": 50.1},
        [{"lat": 91, "lng": 19.1, "ts": 0}],
        [{"lat": 50.1, "lng": 19.1}],
        [{"lat": "abc", "lng": 19.1, "ts": 0}],
    ],
    ids=["not-a-list", "latitude-out-of-range", "no-time", "not-a-number"],
)
def test_invalid_route_points_are_rejected(api_rental, route_points):
    with pytest.raises(InvalidRentalData, match="routePoints"):
        parse_rental(api_rental(routePoints=route_points), RENTAL_ID)


def test_rental_without_route_points_is_parsed_with_empty_route(api_rental):
    rental = parse_rental(api_rental(distance=999, routePoints=None), RENTAL_ID)

    assert rental.route_points == ()


@pytest.mark.parametrize("field", ["distance", "startTime"])
@pytest.mark.parametrize("value", [None, "4000", True])
def test_non_numeric_required_field_is_rejected(api_rental, field, value):
    with pytest.raises(InvalidRentalData, match=field):
        parse_rental(api_rental(**{field: value}), RENTAL_ID)


@pytest.mark.parametrize("data", [[], "text", None])
def test_response_other_than_object_is_rejected(data):
    with pytest.raises(InvalidRentalData):
        parse_rental(data, RENTAL_ID)


def test_places_and_bike_are_parsed(api_rental):
    rental = parse_rental(
        api_rental(
            startPlace={"name": 27163, "lat": 50.26, "lng": 19.01},
            endPlace={"lat": "x"},
            bike={"number": 583444},
        ),
        RENTAL_ID,
    )

    assert rental.start_place == Place("27163", Coordinates(50.26, 19.01))
    assert rental.end_place == Place()
    assert rental.bike_number == "583444"


def test_start_date_uses_warsaw_time_not_utc(api_rental):
    late_evening_utc_is_next_day_in_warsaw = 1_788_996_600

    rental = parse_rental(
        api_rental(startTime=late_evening_utc_is_next_day_in_warsaw), RENTAL_ID
    )

    assert rental.local_start_date == date(2026, 9, 10)


def test_rental_is_requested_by_id(nextbike_api, api_rental):
    requested = []

    def api(request: httpx.Request) -> httpx.Response:
        requested.append(request.read())
        return httpx.Response(200, json=api_rental())

    assert nextbike_api(api).fetch(RENTAL_ID) == api_rental()
    assert requested == [f'{{"id":"{RENTAL_ID}"}}'.encode()]


def test_unauthorized_response_means_expired_session(nextbike_api):
    with pytest.raises(SessionExpired, match="cookie"):
        nextbike_api(lambda request: httpx.Response(401)).fetch(RENTAL_ID)


def test_other_http_error_reports_status(nextbike_api):
    with pytest.raises(NextbikeApiError, match="HTTP 500") as error:
        nextbike_api(lambda request: httpx.Response(500)).fetch(RENTAL_ID)

    assert not isinstance(error.value, SessionExpired)


def test_connection_failure_is_network_error(nextbike_api):
    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(NetworkError):
        nextbike_api(unreachable).fetch(RENTAL_ID)


@pytest.mark.parametrize("content", [b"<html>", b"[]"], ids=["not-json", "not-object"])
def test_unexpected_api_body_is_invalid_rental_data(nextbike_api, content):
    with pytest.raises(InvalidRentalData):
        nextbike_api(lambda request: httpx.Response(200, content=content)).fetch(
            RENTAL_ID
        )
