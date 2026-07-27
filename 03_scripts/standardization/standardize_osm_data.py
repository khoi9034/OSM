"""Standardize raw OSM road-edge and building data into Phase 2 schemas."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from osm_schema import BUILDING_STANDARDIZED_FIELDS, ROAD_STANDARDIZED_FIELDS  # noqa: E402
from standardization_utils import (  # noqa: E402
    ATTRIBUTION,
    area_fields,
    classify_building,
    classify_road,
    exception_frame,
    float_or_none,
    geometry_valid,
    is_blank,
    length_fields,
    load_config,
    make_building_feature_id,
    make_exception,
    make_road_edge_id,
    normalize_oneway,
    parse_building_levels,
    parse_lanes_count,
    parse_speed_mph,
    record_preservation,
    repo_root,
    schema_missing_fields,
    source_value_to_string,
    standardized_schema_ok,
    utc_timestamp,
)


DEFAULT_CONFIG = SCRIPT_DIR / "standardization_config.json"
LINE_TYPES = {"LineString", "MultiLineString"}
POLYGON_TYPES = {"Polygon", "MultiPolygon"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standardize raw OSM road-edge and building data.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Path to standardization_config.json.")
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as input_file:
        return json.load(input_file)


def write_json(data: dict[str, Any], output_path: Path) -> None:
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")


def require_inputs(config: dict[str, Any]) -> None:
    """Fail clearly when a required Phase 1 input is absent."""
    for key in ["raw_road_input", "raw_building_input", "study_area_input", "extraction_metadata_input"]:
        if not config[key].exists():
            raise FileNotFoundError(f"Missing required input for {key}: {config[key]}")


def row_value(row: pd.Series, *fields: str) -> Any:
    """Return the first nonblank source field value from a row."""
    for field in fields:
        if field in row.index and not is_blank(row[field]):
            return row[field]
    return None


def row_text(row: pd.Series, *fields: str) -> str | None:
    """Return a source value serialized as text, or None when absent."""
    value = row_value(row, *fields)
    return None if is_blank(value) else source_value_to_string(value)


def add_parse_exception(
    rows: list[dict[str, Any]],
    dataset_name: str,
    source_record_id: str,
    field_name: str,
    source_value: Any,
    exception_type: str | None,
) -> None:
    """Append a warning/informational exception from a parser result."""
    if not exception_type:
        return
    severity = "informational" if exception_type == "missing source classification value" else "warning"
    rows.append(
        make_exception(
            dataset_name,
            source_record_id,
            field_name,
            source_value,
            exception_type,
            severity,
            "Value preserved in raw field; standardized field left null or set to conservative review category.",
            review_required=severity != "informational",
        )
    )


def unique_identifier(
    base_id: str,
    row_number: int,
    dataset_name: str,
    field_name: str,
    seen: set[str],
    exceptions: list[dict[str, Any]],
) -> str:
    """Return a unique generated ID and record duplicate-ID exceptions."""
    if base_id not in seen:
        seen.add(base_id)
        return base_id
    unique_id = f"{base_id}_{row_number}"
    exceptions.append(
        make_exception(
            dataset_name,
            unique_id,
            field_name,
            base_id,
            "duplicate generated identifier",
            "blocking",
            "Row-number suffix appended to preserve one output record per source record.",
        )
    )
    seen.add(unique_id)
    return unique_id


def status_from_exceptions(rows: list[dict[str, Any]]) -> tuple[str, str | None]:
    """Summarize per-record exception rows into status fields."""
    if not rows:
        return "standardized", None
    severities = {row["severity"] for row in rows}
    status = "blocking_review_required" if "blocking" in severities else "review_required"
    notes = "; ".join(sorted({row["exception_type"] for row in rows}))
    return status, notes


def standardize_roads(
    roads: gpd.GeoDataFrame,
    analysis_crs: str,
    config: dict[str, Any],
    extraction_timestamp_utc: str,
) -> tuple[gpd.GeoDataFrame, list[dict[str, Any]]]:
    """Return standardized road-edge rows and exception records."""
    projected = roads.to_crs(analysis_crs)
    output_rows: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    mph_per_kph = float(config["parsing_configuration"].get("mph_per_kph", 0.621371))

    for row_number, (_, row) in enumerate(projected.iterrows(), start=1):
        row_exceptions: list[dict[str, Any]] = []
        base_id, id_exception = make_road_edge_id(row, row_number)
        road_edge_id = unique_identifier(base_id, row_number, "roads", "road_edge_id", seen_ids, row_exceptions)
        if id_exception:
            id_exception["source_record_id"] = road_edge_id
            row_exceptions.append(id_exception)

        road_class, class_exception = classify_road(row_value(row, "highway"), config["road_class_mapping"])
        add_parse_exception(row_exceptions, "roads", road_edge_id, "highway", row_value(row, "highway"), class_exception)

        maxspeed_mph, speed_exception = parse_speed_mph(row_value(row, "maxspeed"), mph_per_kph)
        add_parse_exception(row_exceptions, "roads", road_edge_id, "maxspeed", row_value(row, "maxspeed"), speed_exception)

        lanes_count, lanes_exception = parse_lanes_count(row_value(row, "lanes"))
        add_parse_exception(row_exceptions, "roads", road_edge_id, "lanes", row_value(row, "lanes"), lanes_exception)

        oneway_standard, oneway_exception = normalize_oneway(row_value(row, "oneway"))
        add_parse_exception(row_exceptions, "roads", road_edge_id, "oneway", row_value(row, "oneway"), oneway_exception)

        valid_geometry = geometry_valid(row.geometry)
        if not valid_geometry:
            row_exceptions.append(
                make_exception(
                    "roads",
                    road_edge_id,
                    "geometry",
                    "",
                    "invalid source geometry",
                    "warning",
                    "Geometry retained unchanged for later QA review.",
                )
            )

        length_ft, length_m = length_fields(row.geometry)
        status, notes = status_from_exceptions(row_exceptions)
        exceptions.extend(row_exceptions)
        output_rows.append(
            {
                "road_edge_id": road_edge_id,
                "osm_id_raw": row_text(row, "osmid"),
                "source_u": row_text(row, "u"),
                "source_v": row_text(row, "v"),
                "source_key": row_text(row, "key"),
                "road_name": row_text(row, "name"),
                "road_class_source": row_text(row, "highway"),
                "road_class_standard": road_class,
                "maxspeed_raw": row_text(row, "maxspeed"),
                "maxspeed_mph": maxspeed_mph,
                "lanes_raw": row_text(row, "lanes"),
                "lanes_count": lanes_count,
                "oneway_raw": row_text(row, "oneway"),
                "oneway_standard": oneway_standard,
                "surface_raw": row_text(row, "surface"),
                "access_raw": row_text(row, "access"),
                "service_raw": row_text(row, "service"),
                "bridge_raw": row_text(row, "bridge"),
                "tunnel_raw": row_text(row, "tunnel"),
                "junction_raw": row_text(row, "junction"),
                "reversed_raw": row_text(row, "reversed"),
                "source_length_m": float_or_none(row_value(row, "length")),
                "geometry_length_ft": length_ft,
                "geometry_length_m": length_m,
                "geometry_valid": valid_geometry,
                "source_dataset": "orlando_osm_roads_raw.geojson",
                "extraction_timestamp_utc": extraction_timestamp_utc,
                "standardization_status": status,
                "standardization_notes": notes,
                "geometry": row.geometry,
            }
        )

    standardized = gpd.GeoDataFrame(output_rows, geometry="geometry", crs=analysis_crs)
    return standardized[ROAD_STANDARDIZED_FIELDS], exceptions


def standardize_buildings(
    buildings: gpd.GeoDataFrame,
    analysis_crs: str,
    config: dict[str, Any],
    extraction_timestamp_utc: str,
) -> tuple[gpd.GeoDataFrame, list[dict[str, Any]]]:
    """Return standardized building rows and exception records."""
    projected = buildings.to_crs(analysis_crs)
    output_rows: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for row_number, (_, row) in enumerate(projected.iterrows(), start=1):
        row_exceptions: list[dict[str, Any]] = []
        base_id, id_exception = make_building_feature_id(row, row_number)
        building_id = unique_identifier(
            base_id, row_number, "buildings", "building_feature_id", seen_ids, row_exceptions
        )
        if id_exception:
            id_exception["source_record_id"] = building_id
            row_exceptions.append(id_exception)

        building_class, class_exception = classify_building(row_value(row, "building"), config["building_class_mapping"])
        add_parse_exception(
            row_exceptions, "buildings", building_id, "building", row_value(row, "building"), class_exception
        )

        levels_count, levels_exception = parse_building_levels(row_value(row, "building:levels"))
        add_parse_exception(
            row_exceptions,
            "buildings",
            building_id,
            "building:levels",
            row_value(row, "building:levels"),
            levels_exception,
        )

        valid_geometry = geometry_valid(row.geometry)
        if not valid_geometry:
            row_exceptions.append(
                make_exception(
                    "buildings",
                    building_id,
                    "geometry",
                    "",
                    "invalid source geometry",
                    "warning",
                    "Geometry retained unchanged for later QA review.",
                )
            )

        area_sqft, area_sqm = area_fields(row.geometry)
        status, notes = status_from_exceptions(row_exceptions)
        exceptions.extend(row_exceptions)
        output_rows.append(
            {
                "building_feature_id": building_id,
                "osm_id_raw": row_text(row, "osmid", "id"),
                "element_type": row_text(row, "element_type", "element"),
                "building_name": row_text(row, "name"),
                "building_type_source": row_text(row, "building"),
                "building_type_standard": building_class,
                "building_levels_raw": row_text(row, "building:levels"),
                "building_levels_count": levels_count,
                "address_number": row_text(row, "addr:housenumber"),
                "address_street": row_text(row, "addr:street"),
                "address_city": row_text(row, "addr:city"),
                "address_postcode": row_text(row, "addr:postcode"),
                "amenity_raw": row_text(row, "amenity"),
                "shop_raw": row_text(row, "shop"),
                "office_raw": row_text(row, "office"),
                "landuse_raw": row_text(row, "landuse"),
                "area_sqft": area_sqft,
                "area_sqm": area_sqm,
                "geometry_valid": valid_geometry,
                "source_dataset": "orlando_osm_buildings_raw.geojson",
                "extraction_timestamp_utc": extraction_timestamp_utc,
                "standardization_status": status,
                "standardization_notes": notes,
                "geometry": row.geometry,
            }
        )

    standardized = gpd.GeoDataFrame(output_rows, geometry="geometry", crs=analysis_crs)
    return standardized[BUILDING_STANDARDIZED_FIELDS], exceptions


def value_counts(series: pd.Series) -> dict[str, int]:
    """Return stable stringified value counts for summary JSON."""
    counts = series.fillna("<null>").astype(str).value_counts(dropna=False)
    return {str(key): int(value) for key, value in counts.items()}


def parsed_counts(frame: gpd.GeoDataFrame, raw_field: str, parsed_field: str) -> dict[str, int]:
    """Count present, parsed, and unparsed source values."""
    source_present = ~frame[raw_field].map(is_blank)
    parsed = frame[parsed_field].notna()
    return {
        "source_values_present": int(source_present.sum()),
        "parsed": int((source_present & parsed).sum()),
        "unparsed": int((source_present & ~parsed).sum()),
        "missing_source_value": int((~source_present).sum()),
    }


def geometry_type_counts(gdf: gpd.GeoDataFrame) -> dict[str, int]:
    counts = gdf.geometry.dropna().geom_type.value_counts()
    return {str(key): int(value) for key, value in counts.items()}


def exception_counts(exceptions: pd.DataFrame, field: str) -> dict[str, int]:
    if exceptions.empty:
        return {}
    counts = exceptions[field].value_counts()
    return {str(key): int(value) for key, value in counts.items()}


def build_summary(
    root: Path,
    config: dict[str, Any],
    metadata: dict[str, Any],
    roads_raw: gpd.GeoDataFrame,
    buildings_raw: gpd.GeoDataFrame,
    roads_out: gpd.GeoDataFrame,
    buildings_out: gpd.GeoDataFrame,
    exceptions: pd.DataFrame,
) -> dict[str, Any]:
    """Build standardization_summary.json from actual outputs."""
    extraction_timestamp = metadata.get("extraction_timestamp_utc", "")
    return {
        "processing_timestamp_utc": utc_timestamp(),
        "extraction_timestamp_utc": extraction_timestamp,
        "input_paths": {
            "roads": config["raw_road_input"].relative_to(root).as_posix(),
            "buildings": config["raw_building_input"].relative_to(root).as_posix(),
            "study_area": config["study_area_input"].relative_to(root).as_posix(),
        },
        "output_path": config["output_geopackage"].relative_to(root).as_posix(),
        "input_road_count": int(len(roads_raw)),
        "output_road_count": int(len(roads_out)),
        "input_building_count": int(len(buildings_raw)),
        "output_building_count": int(len(buildings_out)),
        "crs": {
            "analysis": config["analysis_crs"],
            "roads_standardized": roads_out.crs.to_string() if roads_out.crs else "",
            "buildings_standardized": buildings_out.crs.to_string() if buildings_out.crs else "",
        },
        "geometry_types": {
            "roads_standardized": geometry_type_counts(roads_out),
            "buildings_standardized": geometry_type_counts(buildings_out),
        },
        "geometry_validity": {
            "roads": {
                "valid": int(roads_out["geometry_valid"].sum()),
                "invalid": int((~roads_out["geometry_valid"]).sum()),
            },
            "buildings": {
                "valid": int(buildings_out["geometry_valid"].sum()),
                "invalid": int((~buildings_out["geometry_valid"]).sum()),
            },
        },
        "standardized_road_class_counts": value_counts(roads_out["road_class_standard"]),
        "standardized_building_class_counts": value_counts(buildings_out["building_type_standard"]),
        "speed_parsing": parsed_counts(roads_out, "maxspeed_raw", "maxspeed_mph"),
        "lane_parsing": parsed_counts(roads_out, "lanes_raw", "lanes_count"),
        "building_level_parsing": parsed_counts(buildings_out, "building_levels_raw", "building_levels_count"),
        "exception_counts_by_type": exception_counts(exceptions, "exception_type"),
        "exception_counts_by_severity": exception_counts(exceptions, "severity"),
        "record_preservation_validation": {
            "roads": record_preservation(len(roads_raw), len(roads_out)),
            "buildings": record_preservation(len(buildings_raw), len(buildings_out)),
        },
        "attribution": ATTRIBUTION,
    }


def write_geopackage(
    output_path: Path,
    study_area: gpd.GeoDataFrame,
    roads: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    analysis_crs: str,
) -> None:
    """Write standardized layers to a fresh GeoPackage."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    study_area.to_crs(analysis_crs).to_file(output_path, layer="orlando_study_area", driver="GPKG")
    roads.to_file(output_path, layer="roads_standardized", driver="GPKG")
    buildings.to_file(output_path, layer="buildings_standardized", driver="GPKG")


def validate_outputs(
    roads_raw: gpd.GeoDataFrame,
    buildings_raw: gpd.GeoDataFrame,
    roads_out: gpd.GeoDataFrame,
    buildings_out: gpd.GeoDataFrame,
) -> None:
    """Raise on violations that would make Phase 2 output unreliable."""
    if not record_preservation(len(roads_raw), len(roads_out)):
        raise ValueError("Road record preservation failed.")
    if not record_preservation(len(buildings_raw), len(buildings_out)):
        raise ValueError("Building record preservation failed.")
    if not standardized_schema_ok(roads_out, buildings_out):
        missing = {
            "roads": schema_missing_fields(roads_out, ROAD_STANDARDIZED_FIELDS),
            "buildings": schema_missing_fields(buildings_out, BUILDING_STANDARDIZED_FIELDS),
        }
        raise ValueError(f"Standardized schema fields missing: {missing}")
    road_types = set(roads_out.geometry.dropna().geom_type.unique())
    building_types = set(buildings_out.geometry.dropna().geom_type.unique())
    if not road_types.issubset(LINE_TYPES):
        raise ValueError(f"Standardized roads contain non-line geometry: {sorted(road_types)}")
    if not building_types.issubset(POLYGON_TYPES):
        raise ValueError(f"Standardized buildings contain non-polygon geometry: {sorted(building_types)}")


def main() -> int:
    configure_logging()
    args = parse_args()
    root = repo_root()

    try:
        config = load_config(args.config, root)
        require_inputs(config)
        metadata = read_json(config["extraction_metadata_input"])
        extraction_timestamp = metadata.get("extraction_timestamp_utc", "")

        logging.info("Reading raw OSM inputs.")
        study_area = gpd.read_file(config["study_area_input"])
        roads_raw = gpd.read_file(config["raw_road_input"])
        buildings_raw = gpd.read_file(config["raw_building_input"])

        logging.info("Standardizing roads and buildings in %s.", config["analysis_crs"])
        roads_out, road_exceptions = standardize_roads(
            roads_raw, config["analysis_crs"], config, extraction_timestamp
        )
        buildings_out, building_exceptions = standardize_buildings(
            buildings_raw, config["analysis_crs"], config, extraction_timestamp
        )
        exceptions = exception_frame(road_exceptions + building_exceptions)

        validate_outputs(roads_raw, buildings_raw, roads_out, buildings_out)

        logging.info("Writing GeoPackage and summary tables.")
        write_geopackage(config["output_geopackage"], study_area, roads_out, buildings_out, config["analysis_crs"])
        table_dir = config["table_output_directory"]
        table_dir.mkdir(parents=True, exist_ok=True)
        exceptions.to_csv(table_dir / "standardization_exceptions.csv", index=False)
        write_json(
            build_summary(root, config, metadata, roads_raw, buildings_raw, roads_out, buildings_out, exceptions),
            table_dir / "standardization_summary.json",
        )

        logging.info("Standardization complete: %s road edges, %s buildings.", len(roads_out), len(buildings_out))
        return 0
    except Exception:
        logging.exception("OSM standardization failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
