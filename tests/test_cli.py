from pathlib import Path

from metrorower.cli import (
    EXIT_OK,
    EXIT_SOME_RIDES_FAILED,
    describe,
    exit_code,
    summary,
)
from metrorower.errors import SessionExpired
from metrorower.export import AlreadyExported, Exported, Failed, TooShort
from metrorower.rentals import Source

EXPORTED = Exported("1", Source.API, 4321, Path("gpx/x.gpx"), 12)
TOO_SHORT = TooShort("2", Source.CACHE, 800)
FAILED = Failed("3", SessionExpired(401))


def test_exported_ride_is_described_with_distance_points_and_source():
    assert describe(EXPORTED) == (
        "[1] zapisano gpx/x.gpx (4.32 km, 12 punktów; dane z API)"
    )


def test_too_short_ride_is_described_with_limit():
    assert describe(TOO_SHORT) == "[2] odrzucony: 0.80 km (< 1 km; dane z cache)"


def test_expired_session_hints_at_cookie():
    assert describe(FAILED) == (
        "[3] błąd: HTTP 401 — cookie wygasło lub jest niepoprawne"
    )


def test_summary_counts_sources_and_outcomes():
    results = [EXPORTED, TOO_SHORT, FAILED, AlreadyExported("4")]

    assert summary(results) == (
        "Podsumowanie: pobrano=1, cache=1, utworzono_GPX=1, już_istniało=1, "
        "poniżej_limitu=1, błędy=1"
    )


def test_any_failure_sets_nonzero_exit_code():
    assert exit_code([EXPORTED, TOO_SHORT]) == EXIT_OK
    assert exit_code([EXPORTED, FAILED]) == EXIT_SOME_RIDES_FAILED
