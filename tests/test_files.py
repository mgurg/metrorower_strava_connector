import pytest

from metrorower.files import load_ids, write_atomically


def test_ids_skip_header_blank_lines_and_duplicates_keeping_order(tmp_path):
    path = tmp_path / "ids.txt"
    path.write_text("﻿ID\n360039555\n\n 359818673 \n360039555\n", encoding="utf-8")

    assert load_ids(path) == ["360039555", "359818673"]


def test_non_numeric_id_is_reported_with_line_number(tmp_path):
    path = tmp_path / "ids.txt"
    path.write_text("ID\n360039555\n36003-9555\n", encoding="utf-8")

    with pytest.raises(ValueError, match="wiersz 3"):
        load_ids(path)


@pytest.mark.parametrize("content", ["", "ID\n\n"])
def test_ids_file_without_ids_is_rejected(tmp_path, content):
    path = tmp_path / "ids.txt"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="nie zawiera"):
        load_ids(path)


def test_missing_ids_file_is_reported(tmp_path):
    with pytest.raises(ValueError, match="Nie znaleziono"):
        load_ids(tmp_path / "ids.txt")


def test_failed_atomic_write_keeps_previous_content_and_no_temporary_file(tmp_path):
    path = tmp_path / "ride.json"
    path.write_text("previous", encoding="utf-8")

    def write_partially_then_fail(temporary_path):
        temporary_path.write_text("partial", encoding="utf-8")
        raise OSError("disk full")

    with pytest.raises(OSError):
        write_atomically(path, write_partially_then_fail)

    assert path.read_text(encoding="utf-8") == "previous"
    assert list(tmp_path.iterdir()) == [path]
