from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03_scripts" / "standardization"))

from standardization_utils import (  # noqa: E402
    area_fields,
    classify_building,
    classify_road,
    completeness_rows,
    exception_frame,
    geometry_valid,
    is_blank,
    json_like,
    length_fields,
    list_like,
    load_config,
    make_building_feature_id,
    make_exception,
    make_road_edge_id,
    normalize_oneway,
    parse_building_levels,
    parse_lanes_count,
    parse_speed_mph,
    profile_field,
    record_preservation,
    standardized_schema_ok,
)
from standardize_osm_data import standardize_buildings, standardize_roads  # noqa: E402


ROAD_MAPPING = {
    "motorway": "Limited-access road",
    "primary": "Major arterial-style road",
    "residential": "Local street",
    "service": "Service road",
    "track": "Track",
}
BUILDING_MAPPING = {
    "apartments": "Residential",
    "commercial": "Commercial",
    "warehouse": "Industrial",
    "school": "Educational",
    "yes": "Unclassified building",
}


def config() -> dict:
    return {
        "analysis_crs": "EPSG:2236",
        "road_class_mapping": ROAD_MAPPING,
        "building_class_mapping": BUILDING_MAPPING,
        "parsing_configuration": {"mph_per_kph": 0.621371},
    }


def test_standardization_config_loading_resolves_paths(tmp_path: Path):
    data = {
        "raw_road_input": "roads.geojson",
        "raw_building_input": "buildings.geojson",
        "study_area_input": "study.geojson",
        "extraction_metadata_input": "metadata.json",
        "analysis_crs": "EPSG:2236",
        "output_geopackage": "out.gpkg",
        "table_output_directory": "05_tables",
        "road_class_mapping": ROAD_MAPPING,
        "building_class_mapping": BUILDING_MAPPING,
        "parsing_configuration": {"frequency_fields": {"roads": [], "buildings": []}},
        "expected_source_fields": {"roads": [], "buildings": []},
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_config(path, tmp_path)

    assert loaded["raw_road_input"] == tmp_path / "roads.geojson"
    assert loaded["table_output_directory"] == tmp_path / "05_tables"


def test_blank_json_and_list_like_detection():
    assert is_blank(None)
    assert is_blank(" ")
    assert is_blank("[]")
    assert is_blank("[ ]")
    assert json_like('{"a": 1}')
    assert list_like(["a"])
    assert list_like(np.array(["a"]))
    assert list_like("a;b")
    assert list_like('["a", "b"]')


def test_field_profile_and_completeness_treat_blanks_as_nulls():
    gdf = gpd.GeoDataFrame(
        {"name": ["Main", " ", "[]"], "tags": ['["a"]', "a;b", None]},
        geometry=[LineString([(0, 0), (1, 0)])] * 3,
        crs="EPSG:2236",
    )

    row = profile_field("roads", gdf, "name", True)
    completeness = completeness_rows("roads", gdf, ["name", "missing"])

    assert row["non_null_count"] == 1
    assert profile_field("roads", gdf, "tags")["contains_list_like_values"]
    assert completeness[1]["field_present"] is False


def test_stable_identifier_creation():
    road_id, road_exception = make_road_edge_id(pd.Series({"u": 1, "v": 2, "key": 0, "osmid": 99}), 1)
    building_id, building_exception = make_building_feature_id(pd.Series({"element": "way", "id": 10}), 1)

    assert road_id == "road_edge_1_2_0_99"
    assert road_exception is None
    assert building_id == "building_way_10"
    assert building_exception is None


def test_classification_parsers_and_rejections():
    assert classify_road("residential", ROAD_MAPPING) == ("Local street", None)
    assert classify_road(np.array(["residential"]), ROAD_MAPPING) == ("Local street", None)
    assert classify_road(None, ROAD_MAPPING) == ("Unknown", "missing source classification value")
    assert classify_building("apartments", BUILDING_MAPPING) == ("Residential", None)
    assert classify_building("odd", BUILDING_MAPPING) == ("Other", "unknown building classification")
    assert parse_speed_mph("30 mph") == (30.0, None)
    assert parse_speed_mph("50 km/h") == (31.07, None)
    assert parse_speed_mph("30;40") == (None, "ambiguous multi-value field")
    assert parse_lanes_count("2") == (2, None)
    assert parse_lanes_count("2|3") == (None, "ambiguous multi-value field")
    assert normalize_oneway(True) == ("Yes", None)
    assert normalize_oneway("-1") == ("Reverse", None)
    assert parse_building_levels("2.5") == (2.5, None)
    assert parse_building_levels("2;3") == (None, "ambiguous multi-value field")


def test_projected_measurement_helpers():
    length_ft, length_m = length_fields(LineString([(0, 0), (10, 0)]))
    area_sqft, area_sqm = area_fields(Polygon([(0, 0), (10, 0), (10, 10), (0, 0)]))

    assert length_ft == 10
    assert length_m == pytest.approx(3.048006096)
    assert area_sqft == 50
    assert area_sqm == pytest.approx(4.645170185988092)


def test_exception_frame_and_record_preservation():
    row = make_exception("roads", "road_1", "maxspeed", "signals", "unparsed speed value", "warning", "left null")
    frame = exception_frame([row])

    assert list(frame.columns)[0] == "dataset_name"
    assert frame.loc[0, "exception_type"] == "unparsed speed value"
    assert record_preservation(2, 2)
    assert not record_preservation(2, 1)


def test_standardized_schema_and_count_preservation():
    roads = gpd.GeoDataFrame(
        {
            "u": [1],
            "v": [2],
            "key": [0],
            "osmid": [99],
            "highway": ["residential"],
            "maxspeed": ["30"],
            "lanes": ["2"],
            "oneway": [False],
            "length": [10.0],
        },
        geometry=[LineString([(0, 0), (10, 0)])],
        crs="EPSG:2236",
    )
    buildings = gpd.GeoDataFrame(
        {"element": ["way"], "id": [10], "building": ["apartments"], "building:levels": ["3"]},
        geometry=[Polygon([(0, 0), (10, 0), (10, 10), (0, 0)])],
        crs="EPSG:2236",
    )

    roads_out, road_exceptions = standardize_roads(roads, "EPSG:2236", config(), "2026-07-26T00:00:00Z")
    buildings_out, building_exceptions = standardize_buildings(
        buildings, "EPSG:2236", config(), "2026-07-26T00:00:00Z"
    )

    assert len(roads_out) == len(roads)
    assert len(buildings_out) == len(buildings)
    assert standardized_schema_ok(roads_out, buildings_out)
    assert road_exceptions == []
    assert building_exceptions == []


def test_invalid_geometry_is_reported_not_repaired():
    invalid = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    buildings = gpd.GeoDataFrame(
        {"element": ["way"], "id": [10], "building": ["yes"]},
        geometry=[invalid],
        crs="EPSG:2236",
    )

    buildings_out, exceptions = standardize_buildings(buildings, "EPSG:2236", config(), "2026-07-26T00:00:00Z")

    assert not geometry_valid(invalid)
    assert not bool(buildings_out.loc[0, "geometry_valid"])
    assert any(row["exception_type"] == "invalid source geometry" for row in exceptions)
