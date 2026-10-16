from datetime import UTC, date, datetime
from xml.etree import ElementTree as ET

from metrorower.gpx import (
    GPX_NAMESPACE,
    exported_rental_ids,
    gpx_filename,
    gpx_time,
    rental_id_from_gpx_filename,
    write_gpx,
)
from metrorower.models import Rental, TrackPoint

NS = {"gpx": GPX_NAMESPACE}
RIDE_START = datetime(2026, 9, 9, 13, 7, 16, tzinfo=UTC)


def test_written_gpx_contains_track_points_and_description(tmp_path):
    rental = Rental("360039555", 5064, RIDE_START, bike_number="583444")
    track_points = [
        TrackPoint(50.2635, 19.0112, RIDE_START),
        TrackPoint(50.2595, 19.0644, datetime(2026, 9, 9, 13, 27, 52, tzinfo=UTC)),
    ]
    path = tmp_path / "ride.gpx"

    write_gpx(path, rental, track_points)

    root = ET.parse(path).getroot()
    assert root.tag == f"{{{GPX_NAMESPACE}}}gpx"
    assert root.findtext("gpx:trk/gpx:name", namespaces=NS) == "Nextbike 360039555"
    assert root.findtext("gpx:trk/gpx:desc", namespaces=NS) == (
        "Dystans: 5064 m; rower: 583444"
    )
    written_points = [
        (
            float(point.attrib["lat"]),
            float(point.attrib["lon"]),
            point.findtext("gpx:time", default="", namespaces=NS),
        )
        for point in root.iterfind("gpx:trk/gpx:trkseg/gpx:trkpt", NS)
    ]
    assert written_points == [
        (50.2635, 19.0112, "2026-09-09T13:07:16.000Z"),
        (50.2595, 19.0644, "2026-09-09T13:27:52.000Z"),
    ]
    assert list(tmp_path.iterdir()) == [path]


def test_description_without_bike_number_has_only_distance(tmp_path):
    rental = Rental("1", 1200, RIDE_START)
    path = tmp_path / "ride.gpx"

    write_gpx(path, rental, [TrackPoint(50.0, 19.0, RIDE_START)])

    description = ET.parse(path).getroot().findtext("gpx:trk/gpx:desc", namespaces=NS)
    assert description == "Dystans: 1200 m"


def test_gpx_time_is_utc_with_milliseconds():
    assert gpx_time(datetime(2026, 9, 9, 13, 7, 39, 526_000, tzinfo=UTC)) == (
        "2026-09-09T13:07:39.526Z"
    )


def test_rental_id_is_read_back_from_gpx_filename():
    assert rental_id_from_gpx_filename(gpx_filename(date(2026, 9, 9), "360039555")) == (
        "360039555"
    )


def test_only_gpx_files_named_by_exporter_count_as_exported(tmp_path):
    for name in [
        gpx_filename(date(2026, 9, 9), "360039555"),
        "20260909_metrorower_360039555.gpx.tmp",
        "my_ride.gpx",
        "2026_metrorower_1.gpx",
    ]:
        (tmp_path / name).touch()

    assert exported_rental_ids(tmp_path) == {"360039555"}
