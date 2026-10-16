from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import Any, NamedTuple, Protocol

from metrorower.errors import InvalidFileError, InvalidRentalData
from metrorower.files import load_json, save_json
from metrorower.models import Rental
from metrorower.nextbike import parse_rental

logger = logging.getLogger(__name__)


class Source(StrEnum):
    API = "API"
    CACHE = "cache"


class LoadedRental(NamedTuple):
    rental: Rental
    source: Source


class RentalRepository(Protocol):
    def load(self, rental_id: str) -> LoadedRental: ...


class RawRentalFetcher(Protocol):
    def fetch(self, rental_id: str) -> dict[str, Any]: ...


class CachedRentals:
    def __init__(self, cache_dir: Path, fetcher: RawRentalFetcher) -> None:
        self._cache_dir = cache_dir
        self._fetcher = fetcher

    def cache_path(self, rental_id: str) -> Path:
        return self._cache_dir / f"{rental_id}.json"

    def load(self, rental_id: str) -> LoadedRental:
        path = self.cache_path(rental_id)
        if path.exists():
            try:
                return LoadedRental(
                    parse_rental(load_json(path), rental_id), Source.CACHE
                )
            except (InvalidFileError, InvalidRentalData) as error:
                logger.warning(
                    "[%s] nieprawidłowy cache (%s), pobieram ponownie", rental_id, error
                )

        data = self._fetcher.fetch(rental_id)
        rental = parse_rental(data, rental_id)
        save_json(path, data)
        return LoadedRental(rental, Source.API)
