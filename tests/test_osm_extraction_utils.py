from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03_scripts" / "extraction"))

from osm_extraction_utils import (  # noqa: E402
    build_metadata,
    create_study_area,
    inventory_row,
    validate_metadata_counts,
    validate_spatial_datasets,
)


def config() -> dict:
    return {
        "study_area_name": "Orlando_OSM_Study_Area",
        "center_latitude": 28.5383,
        "center_longitude": -81.3792,
        "radius_meters": 4828,
        "source_crs": "EPSG:4326",
        "projected_crs": "EPSG:2236",
        "road_network_type": "drive",
        "output_directory": Path("01_raw_data/osm"),
    }


def test_create_study_area_buffers_and_returns_source_crs():
    study_area = create_study_area(config())

    assert len(study_area) == 1
    assert study_area.crs.to_string() == "EPSG:4326"
    assert study_area.geometry.iloc[0].is_valid
    assert study_area.to_crs("EPSG:2236").area.iloc[0] > 0


def test_validate_spatial_datasets_accepts_expected_geometry_types():
    study_area = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])], crs="EPSG:4326")
    roads = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326")
    buildings = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])], crs="EPSG:4326")

    assert validate_spatial_datasets(study_area, roads, buildings) == []


def test_validate_spatial_datasets_reports_empty_roads():
    study_area = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])], crs="EPSG:4326")
    roads = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    buildings = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])], crs="EPSG:4326")

    assert "Roads dataset is empty." in validate_spatial_datasets(study_area, roads, buildings)


def test_validate_spatial_datasets_reports_missing_road_geometry():
    study_area = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])], crs="EPSG:4326")
    roads = gpd.GeoDataFrame({"name": ["missing geometry"]}, geometry=[None], crs="EPSG:4326")
    buildings = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])], crs="EPSG:4326")

    assert validate_spatial_datasets(study_area, roads, buildings) == ["Roads contain non-line geometry types: []"]


def test_build_metadata_and_inventory_rows_match_counts(tmp_path: Path):
    roads = gpd.GeoDataFrame(geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:4326")
    buildings = gpd.GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])], crs="EPSG:4326")
    output_paths = {
        "study_area": tmp_path / "study.geojson",
        "roads": tmp_path / "roads.geojson",
        "buildings": tmp_path / "buildings.geojson",
        "metadata": tmp_path / "metadata.json",
        "inventory": tmp_path / "inventory.csv",
    }

    metadata = build_metadata(
        config=config(),
        roads=roads,
        buildings=buildings,
        output_paths=output_paths,
        extraction_timestamp_utc="2026-07-26T00:00:00Z",
        osmnx_version="test",
        python_version="test",
        root=tmp_path,
    )
    row = inventory_row("roads", "raw OSM road edges", roads, output_paths["roads"], "2026-07-26T00:00:00Z", tmp_path)

    assert metadata["road_feature_count"] == 1
    assert metadata["building_feature_count"] == 1
    assert validate_metadata_counts(metadata, roads, buildings) == []
    assert row["geometry_types"] == "LineString"
    assert row["output_path"] == "roads.geojson"
