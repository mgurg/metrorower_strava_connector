from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree as ET

from metrorower.files import write_atomically
from metrorower.models import Ride, TrackPoint

GPX_NAMESPACE = "http://www.topografix.com/GPX/1/1"
ET.register_namespace("", GPX_NAMESPACE)


def gpx_filename(date: str, rental_id: str) -> str:
    return f"{date}_metrorower_{rental_id}.gpx"


def rental_id_from_gpx_filename(name: str) -> str | None:
    match = re.fullmatch(r"\d{8}_metrorower_(\d+)\.gpx", name)
    return match[1] if match else None


def exported_rental_ids(gpx_dir: Path) -> set[str]:
    return {
        rental_id
        for path in gpx_dir.iterdir()
        if (rental_id := rental_id_from_gpx_filename(path.name)) is not None
    }


def write_gpx(path: Path, ride: Ride, track_points: list[TrackPoint]) -> None:
    name = f"Nextbike {ride.rental_id}"
    gpx = ET.Element(
        f"{{{GPX_NAMESPACE}}}gpx",
        {"version": "1.1", "creator": "metrorower"},
    )
    metadata = ET.SubElement(gpx, f"{{{GPX_NAMESPACE}}}metadata")
    ET.SubElement(metadata, f"{{{GPX_NAMESPACE}}}name").text = name

    track = ET.SubElement(gpx, f"{{{GPX_NAMESPACE}}}trk")
    ET.SubElement(track, f"{{{GPX_NAMESPACE}}}name").text = name
    bike = ride.rental.get("bike")
    description = f"Dystans: {ride.distance} m"
    if isinstance(bike, dict) and bike.get("number"):
        description += f"; rower: {bike['number']}"
    ET.SubElement(track, f"{{{GPX_NAMESPACE}}}desc").text = description
    segment = ET.SubElement(track, f"{{{GPX_NAMESPACE}}}trkseg")

    for latitude, longitude, time in track_points:
        track_point = ET.SubElement(
            segment,
            f"{{{GPX_NAMESPACE}}}trkpt",
            {"lat": str(latitude), "lon": str(longitude)},
        )
        ET.SubElement(track_point, f"{{{GPX_NAMESPACE}}}time").text = time

    ET.indent(gpx, space="  ")
    tree = ET.ElementTree(gpx)
    write_atomically(
        path,
        lambda temporary_path: tree.write(
            temporary_path, encoding="utf-8", xml_declaration=True
        ),
    )
