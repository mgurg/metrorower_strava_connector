from __future__ import annotations


class MetrorowerError(Exception):
    pass


class InvalidFileError(MetrorowerError):
    pass


class InvalidRentalData(MetrorowerError):
    pass


class NetworkError(MetrorowerError):
    pass


class NextbikeApiError(MetrorowerError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class SessionExpired(NextbikeApiError):
    def __str__(self) -> str:
        return f"HTTP {self.status_code} — cookie wygasło lub jest niepoprawne"
