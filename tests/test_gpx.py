from xml.etree import ElementTree as ET

from metrorower.gpx import (
    GPX_NAMESPACE,
    exported_rental_ids,
    gpx_filename,
    rental_id_from_gpx_filename,
    write_gpx,
)
from metrorower.models import Ride, TrackPoint

NS = {"gpx": GPX_NAMESPACE}


def test_written_gpx_contains_track_points_and_description(tmp_path):
    ride = Ride("360039555", {"bike": {"number": "583444"}}, "cache", 5064, None)
    track_points = [
        TrackPoint(50.2635, 19.0112, "2026-09-09T13:07:16.000Z"),
        TrackPoint(50.2595, 19.0644, "2026-09-09T13:27:52.000Z"),
    ]
    path = tmp_path / "ride.gpx"

    write_gpx(path, ride, track_points)

    root = ET.parse(path).getroot()
    assert root.tag == f"{{{GPX_NAMESPACE}}}gpx"
    assert root.findtext("gpx:trk/gpx:name", namespaces=NS) == "Nextbike 360039555"
    assert root.findtext("gpx:trk/gpx:desc", namespaces=NS) == (
        "Dystans: 5064 m; rower: 583444"
    )
    written_points = [
        TrackPoint(
            float(point.attrib["lat"]),
            float(point.attrib["lon"]),
            point.findtext("gpx:time", default="", namespaces=NS),
        )
        for point in root.iterfind("gpx:trk/gpx:trkseg/gpx:trkpt", NS)
    ]
    assert written_points == track_points
    assert list(tmp_path.iterdir()) == [path]


def test_description_without_bike_number_has_only_distance(tmp_path):
    ride = Ride("1", {}, "cache", 1200, None)
    path = tmp_path / "ride.gpx"

    write_gpx(path, ride, [TrackPoint(50.0, 19.0, "2026-09-09T13:00:00.000Z")])

    description = ET.parse(path).getroot().findtext("gpx:trk/gpx:desc", namespaces=NS)
    assert description == "Dystans: 1200 m"


def test_rental_id_is_read_back_from_gpx_filename():
    assert rental_id_from_gpx_filename(gpx_filename("20260909", "360039555")) == (
        "360039555"
    )


def test_only_gpx_files_named_by_exporter_count_as_exported(tmp_path):
    for name in [
        gpx_filename("20260909", "360039555"),
        "20260909_metrorower_360039555.gpx.tmp",
        "my_ride.gpx",
        "2026_metrorower_1.gpx",
    ]:
        (tmp_path / name).touch()

    assert exported_rental_ids(tmp_path) == {"360039555"}
