"""Utility functions for Phase 1 OpenStreetMap extraction."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from pyproj import CRS
from shapely.geometry import Point


PROJECT_NAME = "OpenStreetMap Operational Readiness Assessment"
ATTRIBUTION = "© OpenStreetMap contributors"
RADIUS_METERS_PER_MILE = 1609.344
REQUIRED_CONFIG_KEYS = {
    "study_area_name",
    "center_latitude",
    "center_longitude",
    "radius_meters",
    "source_crs",
    "projected_crs",
    "road_network_type",
    "output_directory",
}


def repo_root() -> Path:
    """Return the repository root from this script location."""
    return Path(__file__).resolve().parents[2]


def resolve_repo_path(path_value: str | Path, root: Path) -> Path:
    """Resolve a path against the repository root unless it is absolute."""
    path = Path(path_value)
    return path if path.is_absolute() else root / path


def load_config(config_path: str | Path, root: Path | None = None) -> dict[str, Any]:
    """Load and validate the extraction configuration."""
    root = root or repo_root()
    resolved_config_path = resolve_repo_path(config_path, root)
    with resolved_config_path.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    missing = sorted(REQUIRED_CONFIG_KEYS - set(config))
    if missing:
        raise ValueError(f"Missing required configuration keys: {', '.join(missing)}")

    config["config_path"] = resolved_config_path
    config["output_directory"] = resolve_repo_path(config["output_directory"], root)
    return config


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def projected_distance_from_meters(distance_meters: float, projected_crs: str) -> float:
    """Convert meters to the linear unit used by a projected CRS."""
    crs = CRS.from_user_input(projected_crs)
    unit_conversion_factor = crs.axis_info[0].unit_conversion_factor
    return distance_meters / unit_conversion_factor


def create_study_area(config: dict[str, Any]) -> gpd.GeoDataFrame:
    """Create a circular study area around the configured center point."""
    source_crs = config["source_crs"]
    projected_crs = config["projected_crs"]
    radius_meters = float(config["radius_meters"])
    center = Point(float(config["center_longitude"]), float(config["center_latitude"]))

    point = gpd.GeoDataFrame(
        {
            "study_area_name": [config["study_area_name"]],
            "center_latitude": [float(config["center_latitude"])],
            "center_longitude": [float(config["center_longitude"])],
            "radius_meters": [radius_meters],
            "radius_miles": [radius_meters / RADIUS_METERS_PER_MILE],
        },
        geometry=[center],
        crs=source_crs,
    )
    buffer_distance = projected_distance_from_meters(radius_meters, projected_crs)
    buffered = point.to_crs(projected_crs).geometry.buffer(buffer_distance)
    study_area = gpd.GeoDataFrame(point.drop(columns="geometry"), geometry=buffered, crs=projected_crs)
    return study_area.to_crs(source_crs)


def geometry_types(gdf: gpd.GeoDataFrame) -> list[str]:
    """Return sorted geometry type names for a GeoDataFrame."""
    return sorted(gdf.geometry.dropna().geom_type.unique().tolist())


def bounding_box(gdf: gpd.GeoDataFrame) -> dict[str, float] | None:
    """Return a GeoDataFrame bounding box as named coordinates."""
    if gdf.empty:
        return None
    minx, miny, maxx, maxy = gdf.total_bounds
    return {"minx": float(minx), "miny": float(miny), "maxx": float(maxx), "maxy": float(maxy)}


def normalize_geojson_value(value: Any) -> Any:
    """Convert mixed OSM tag values into GeoJSON-friendly scalar values."""
    if isinstance(value, (list, tuple, set)):
        return json.dumps(list(value), ensure_ascii=False, default=str)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def prepare_for_geojson(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reset source indexes and serialize non-scalar OSM tag values."""
    output = gdf.copy()
    if not isinstance(output.index, pd.RangeIndex):
        output = output.reset_index()
    for column in output.columns:
        if column != output.geometry.name:
            output[column] = output[column].map(normalize_geojson_value)
    return output


def save_geojson(gdf: gpd.GeoDataFrame, output_path: Path) -> gpd.GeoDataFrame:
    """Write a GeoDataFrame to GeoJSON and return the written representation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prepared = prepare_for_geojson(gdf)
    prepared.to_file(output_path, driver="GeoJSON")
    return prepared


def validate_spatial_datasets(
    study_area: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
) -> list[str]:
    """Validate the Phase 1 spatial datasets without repairing geometry."""
    failures: list[str] = []
    if study_area.empty or study_area.geometry.isna().all():
        failures.append("Study-area geometry is missing.")
    elif not study_area.geometry.is_valid.all():
        failures.append("Study-area geometry is invalid.")

    road_types = set(geometry_types(roads))
    building_types = set(geometry_types(buildings))

    if roads.empty:
        failures.append("Roads dataset is empty.")
    elif not road_types or not road_types.issubset({"LineString", "MultiLineString"}):
        failures.append(f"Roads contain non-line geometry types: {geometry_types(roads)}")

    if buildings.empty:
        failures.append("Buildings dataset is empty.")
    elif not building_types or not building_types.issubset({"Polygon", "MultiPolygon"}):
        failures.append(f"Buildings contain non-polygon geometry types: {geometry_types(buildings)}")

    for label, gdf in (("study area", study_area), ("roads", roads), ("buildings", buildings)):
        if gdf.crs is None:
            failures.append(f"{label} dataset is missing a CRS.")
    return failures


def inventory_row(
    dataset_name: str,
    dataset_type: str,
    gdf: gpd.GeoDataFrame,
    output_path: Path,
    extraction_timestamp_utc: str,
    root: Path,
) -> dict[str, Any]:
    """Build one inventory row for a produced spatial dataset."""
    return {
        "dataset_name": dataset_name,
        "dataset_type": dataset_type,
        "feature_count": int(len(gdf)),
        "geometry_types": ";".join(geometry_types(gdf)),
        "crs": gdf.crs.to_string() if gdf.crs else "",
        "output_path": output_path.relative_to(root).as_posix(),
        "extraction_timestamp_utc": extraction_timestamp_utc,
        "source": "OpenStreetMap",
        "attribution": ATTRIBUTION,
    }


def build_metadata(
    config: dict[str, Any],
    roads: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    output_paths: dict[str, Path],
    extraction_timestamp_utc: str,
    osmnx_version: str,
    python_version: str,
    root: Path,
) -> dict[str, Any]:
    """Build extraction metadata from actual saved datasets."""
    radius_meters = float(config["radius_meters"])
    return {
        "project_name": PROJECT_NAME,
        "extraction_timestamp_utc": extraction_timestamp_utc,
        "study_area_name": config["study_area_name"],
        "center_latitude": float(config["center_latitude"]),
        "center_longitude": float(config["center_longitude"]),
        "radius_meters": radius_meters,
        "radius_miles": radius_meters / RADIUS_METERS_PER_MILE,
        "source_crs": config["source_crs"],
        "analysis_crs": config["projected_crs"],
        "osm_extraction_method": "OSMnx graph_from_polygon for roads and features_from_polygon for building footprints",
        "osmnx_version": osmnx_version,
        "python_version": python_version,
        "road_network_type": config["road_network_type"],
        "road_feature_count": int(len(roads)),
        "building_feature_count": int(len(buildings)),
        "road_geometry_types": geometry_types(roads),
        "building_geometry_types": geometry_types(buildings),
        "road_bounding_box": bounding_box(roads),
        "building_bounding_box": bounding_box(buildings),
        "output_file_paths": {name: path.relative_to(root).as_posix() for name, path in output_paths.items()},
        "attribution": ATTRIBUTION,
    }


def validate_metadata_counts(
    metadata: dict[str, Any],
    roads: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
) -> list[str]:
    """Check metadata counts against saved spatial datasets."""
    failures: list[str] = []
    if metadata["road_feature_count"] != len(roads):
        failures.append("Metadata road count does not match saved roads dataset.")
    if metadata["building_feature_count"] != len(buildings):
        failures.append("Metadata building count does not match saved buildings dataset.")
    return failures
