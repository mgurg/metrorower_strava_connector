from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from metrorower.errors import InvalidFileError


def load_ids(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError as error:
        raise InvalidFileError(f"Nie znaleziono pliku z ID: {path}") from error

    ids: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        value = line.strip()
        if not value or value.casefold() == "id":
            continue
        if not value.isdecimal():
            raise InvalidFileError(
                f"Nieprawidłowe ID w {path}, wiersz {line_number}: {value!r}"
            )
        ids.append(value)

    if not ids:
        raise InvalidFileError(f"Plik {path} nie zawiera żadnych ID przejazdów")
    return list(dict.fromkeys(ids))


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InvalidFileError(f"nie można odczytać {path}: {error}") from error


def write_atomically(path: Path, write: Callable[[Path], object]) -> None:
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        write(temporary_path)
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def save_json(path: Path, data: dict[str, Any]) -> None:
    write_atomically(
        path,
        lambda temporary_path: temporary_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        ),
    )
