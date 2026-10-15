import json

import httpx
import pytest

from metrorower.models import TrackPoint
from metrorower.nextbike import load_ride, parse_route_points, validate_rental

RENTAL_ID = "360039555"


def fail_if_called(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"nieoczekiwane zapytanie do API: {request.url}")


def test_route_points_are_sorted_by_time_and_converted_to_iso():
    rental = {
        "routePoints": [
            {"lat": 50.2, "lng": 19.2, "ts": 1_788_959_284_487},
            {"lat": 50.1, "lng": 19.1, "ts": 1_788_959_259_526},
        ]
    }

    assert parse_route_points(rental) == [
        TrackPoint(50.1, 19.1, "2026-09-09T13:07:39.526Z"),
        TrackPoint(50.2, 19.2, "2026-09-09T13:08:04.487Z"),
    ]


@pytest.mark.parametrize(
    "route_points",
    [
        [],
        None,
        [{"lat": 91, "lng": 19.1, "ts": 0}],
        [{"lat": 50.1, "lng": 19.1}],
        [{"lat": "abc", "lng": 19.1, "ts": 0}],
    ],
    ids=["empty", "missing", "latitude-out-of-range", "no-time", "not-a-number"],
)
def test_invalid_route_points_are_rejected(route_points):
    with pytest.raises(ValueError, match="routePoints"):
        parse_route_points({"routePoints": route_points})


def test_ride_shorter_than_minimum_has_no_track_and_needs_no_route_points():
    distance, track = validate_rental({"distance": 999}, minimum_metres=1000)

    assert (distance, track) == (999, None)


@pytest.mark.parametrize("distance", [None, "4000", True])
def test_non_numeric_distance_is_rejected(distance):
    with pytest.raises(ValueError, match="distance"):
        validate_rental({"distance": distance}, minimum_metres=1000)


def test_track_date_uses_warsaw_time_not_utc(api_rental):
    late_evening_utc_is_next_day_in_warsaw = 1_788_996_600

    _, track = validate_rental(
        api_rental(startTime=late_evening_utc_is_next_day_in_warsaw), minimum_metres=0
    )

    assert track is not None
    assert track.date == "20260910"


def test_valid_cache_is_used_without_calling_api(tmp_path, api_rental, nextbike_api):
    cache = tmp_path / f"{RENTAL_ID}.json"
    cache.write_text(json.dumps(api_rental()), encoding="utf-8")

    ride = load_ride(nextbike_api(fail_if_called), cache, RENTAL_ID, 1000)

    assert ride.source == "cache"
    assert ride.track_if_long_enough is not None


@pytest.mark.parametrize("cache_content", ["{broken json", "[]", '{"distance": "x"}'])
def test_invalid_cache_is_downloaded_again_and_replaced(
    tmp_path, api_rental, nextbike_api, cache_content
):
    cache = tmp_path / f"{RENTAL_ID}.json"
    cache.write_text(cache_content, encoding="utf-8")
    fresh_rental = api_rental()

    ride = load_ride(
        nextbike_api(lambda request: httpx.Response(200, json=fresh_rental)),
        cache,
        RENTAL_ID,
        1000,
    )

    assert ride.source == "API"
    assert json.loads(cache.read_text(encoding="utf-8")) == fresh_rental


def test_downloaded_ride_is_requested_by_id_and_cached(
    tmp_path, api_rental, nextbike_api
):
    requested_ids = []

    def api(request: httpx.Request) -> httpx.Response:
        requested_ids.append(json.loads(request.content)["id"])
        return httpx.Response(200, json=api_rental())

    cache = tmp_path / f"{RENTAL_ID}.json"
    load_ride(nextbike_api(api), cache, RENTAL_ID, 1000)

    assert requested_ids == [RENTAL_ID]
    assert cache.exists()


def test_invalid_api_response_is_not_cached(tmp_path, nextbike_api):
    cache = tmp_path / f"{RENTAL_ID}.json"

    with pytest.raises(ValueError):
        load_ride(
            nextbike_api(lambda request: httpx.Response(200, json={"distance": None})),
            cache,
            RENTAL_ID,
            1000,
        )

    assert not cache.exists()


def test_expired_cookie_raises_http_error(tmp_path, nextbike_api):
    unauthorized = nextbike_api(lambda request: httpx.Response(401))

    with pytest.raises(httpx.HTTPStatusError):
        load_ride(unauthorized, tmp_path / f"{RENTAL_ID}.json", RENTAL_ID, 1000)
