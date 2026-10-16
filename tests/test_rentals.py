import json

import pytest

from metrorower.errors import InvalidRentalData, SessionExpired
from metrorower.rentals import CachedRentals, Source

RENTAL_ID = "360039555"


class FakeFetcher:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requested_ids = []

    def fetch(self, rental_id):
        self.requested_ids.append(rental_id)
        if self.error is not None:
            raise self.error
        return self.response


def test_valid_cache_is_used_without_calling_api(tmp_path, api_rental):
    (tmp_path / f"{RENTAL_ID}.json").write_text(
        json.dumps(api_rental()), encoding="utf-8"
    )
    fetcher = FakeFetcher()

    loaded = CachedRentals(tmp_path, fetcher).load(RENTAL_ID)

    assert loaded.source is Source.CACHE
    assert loaded.rental.rental_id == RENTAL_ID
    assert fetcher.requested_ids == []


@pytest.mark.parametrize("cache_content", ["{broken json", "[]", '{"distance": "x"}'])
def test_invalid_cache_is_downloaded_again_and_replaced(
    tmp_path, api_rental, cache_content, caplog
):
    cache = tmp_path / f"{RENTAL_ID}.json"
    cache.write_text(cache_content, encoding="utf-8")
    fresh_rental = api_rental()

    loaded = CachedRentals(tmp_path, FakeFetcher(fresh_rental)).load(RENTAL_ID)

    assert loaded.source is Source.API
    assert json.loads(cache.read_text(encoding="utf-8")) == fresh_rental
    assert "nieprawidłowy cache" in caplog.text


def test_downloaded_rental_is_cached(tmp_path, api_rental):
    fetcher = FakeFetcher(api_rental())

    CachedRentals(tmp_path, fetcher).load(RENTAL_ID)

    assert fetcher.requested_ids == [RENTAL_ID]
    assert (tmp_path / f"{RENTAL_ID}.json").exists()


def test_invalid_api_response_is_not_cached(tmp_path):
    with pytest.raises(InvalidRentalData):
        CachedRentals(tmp_path, FakeFetcher({"distance": None})).load(RENTAL_ID)

    assert list(tmp_path.iterdir()) == []


def test_api_error_is_propagated(tmp_path):
    with pytest.raises(SessionExpired):
        CachedRentals(tmp_path, FakeFetcher(error=SessionExpired(401))).load(RENTAL_ID)
