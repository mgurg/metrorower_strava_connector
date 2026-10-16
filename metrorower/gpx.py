from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from metrorower.files import write_atomically
from metrorower.models import Rental, TrackPoint

GPX_NAMESPACE = "http://www.topografix.com/GPX/1/1"
ET.register_namespace("", GPX_NAMESPACE)


def gpx_filename(start_date: date, rental_id: str) -> str:
    return f"{start_date:%Y%m%d}_metrorower_{rental_id}.gpx"


def rental_id_from_gpx_filename(name: str) -> str | None:
    match = re.fullmatch(r"\d{8}_metrorower_(\d+)\.gpx", name)
    return match[1] if match else None


def exported_rental_ids(gpx_dir: Path) -> set[str]:
    return {
        rental_id
        for path in gpx_dir.iterdir()
        if (rental_id := rental_id_from_gpx_filename(path.name)) is not None
    }


def gpx_time(moment: datetime) -> str:
    utc = moment.astimezone(UTC)
    return utc.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def track_description(rental: Rental) -> str:
    description = f"Dystans: {rental.distance_meters:.0f} m"
    if rental.bike_number:
        description += f"; rower: {rental.bike_number}"
    return description


def gpx_tag(name: str) -> str:
    return f"{{{GPX_NAMESPACE}}}{name}"


def write_gpx(path: Path, rental: Rental, track_points: Sequence[TrackPoint]) -> None:
    name = f"Nextbike {rental.rental_id}"
    gpx = ET.Element(gpx_tag("gpx"), {"version": "1.1", "creator": "metrorower"})
    metadata = ET.SubElement(gpx, gpx_tag("metadata"))
    ET.SubElement(metadata, gpx_tag("name")).text = name

    track = ET.SubElement(gpx, gpx_tag("trk"))
    ET.SubElement(track, gpx_tag("name")).text = name
    ET.SubElement(track, gpx_tag("desc")).text = track_description(rental)
    segment = ET.SubElement(track, gpx_tag("trkseg"))

    for point in track_points:
        track_point = ET.SubElement(
            segment,
            gpx_tag("trkpt"),
            {"lat": str(point.latitude), "lon": str(point.longitude)},
        )
        ET.SubElement(track_point, gpx_tag("time")).text = gpx_time(point.time)

    ET.indent(gpx, space="  ")
    tree = ET.ElementTree(gpx)
    write_atomically(
        path,
        lambda temporary_path: tree.write(
            temporary_path, encoding="utf-8", xml_declaration=True
        ),
    )
