"""Profile raw OSM roads and buildings for Phase 2 standardization."""

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

from osm_schema import FIELD_INVENTORY_FIELDS  # noqa: E402
from standardization_utils import (  # noqa: E402
    completeness_rows,
    field_inventory_rows,
    frequency_rows,
    geometry_profile_row,
    load_config,
    repo_root,
    utc_timestamp,
)


DEFAULT_CONFIG = SCRIPT_DIR / "standardization_config.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile raw OSM roads and buildings.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Path to standardization_config.json.")
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def read_geodata(path: Path, label: str) -> gpd.GeoDataFrame:
    """Read a GeoJSON input after confirming it exists."""
    if not path.exists():
        raise FileNotFoundError(f"Missing {label} input: {path}")
    return gpd.read_file(path)


def relative_path(path: Path, root: Path) -> str:
    """Return a repository-relative path when possible."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def dtype_summary(gdf: gpd.GeoDataFrame) -> dict[str, str]:
    """Return field dtype strings safe for JSON output."""
    return {field: str(gdf[field].dtype) for field in gdf.columns}


def profile_summary(
    root: Path,
    config: dict[str, Any],
    roads: gpd.GeoDataFrame,
    buildings: gpd.GeoDataFrame,
    study_area: gpd.GeoDataFrame,
    inventory: pd.DataFrame,
) -> dict[str, Any]:
    """Build the compact source-profile JSON summary."""
    threshold = float(config["parsing_configuration"].get("high_null_rate_threshold_percent", 50))
    high_null = inventory[
        (inventory["field_name"] != "geometry")
        & (inventory["source_dtype"] != "absent")
        & (inventory["percent_complete"] < threshold)
    ]
    return {
        "processing_timestamp_utc": utc_timestamp(),
        "input_paths": {
            "roads": relative_path(config["raw_road_input"], root),
            "buildings": relative_path(config["raw_building_input"], root),
            "study_area": relative_path(config["study_area_input"], root),
        },
        "feature_counts": {
            "roads": int(len(roads)),
            "buildings": int(len(buildings)),
            "study_area": int(len(study_area)),
        },
        "crs": {
            "roads": roads.crs.to_string() if roads.crs else "",
            "buildings": buildings.crs.to_string() if buildings.crs else "",
            "study_area": study_area.crs.to_string() if study_area.crs else "",
        },
        "geometry_types": {
            "roads": sorted(roads.geometry.dropna().geom_type.unique().tolist()),
            "buildings": sorted(buildings.geometry.dropna().geom_type.unique().tolist()),
            "study_area": sorted(study_area.geometry.dropna().geom_type.unique().tolist()),
        },
        "actual_fields": {
            "roads": list(roads.columns),
            "buildings": list(buildings.columns),
            "study_area": list(study_area.columns),
        },
        "actual_field_types": {
            "roads": dtype_summary(roads),
            "buildings": dtype_summary(buildings),
            "study_area": dtype_summary(study_area),
        },
        "fields_with_mixed_value_types": inventory[
            inventory["notes"].fillna("").str.contains("Mixed Python value types", regex=False)
        ][["dataset_name", "field_name", "notes"]].to_dict("records"),
        "fields_with_json_like_values": inventory[inventory["contains_json_like_values"]][
            ["dataset_name", "field_name"]
        ].to_dict("records"),
        "fields_with_list_like_values": inventory[inventory["contains_list_like_values"]][
            ["dataset_name", "field_name"]
        ].to_dict("records"),
        "high_null_rate_fields": high_null[["dataset_name", "field_name", "percent_complete"]].to_dict("records"),
        "notes": [
            "Blank strings, whitespace-only strings, empty lists, empty JSON arrays, and nulls count as incomplete.",
            "No final quality score or fitness-for-use conclusion is calculated in Phase 2.",
        ],
    }


def write_json(data: dict[str, Any], output_path: Path) -> None:
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")


def main() -> int:
    configure_logging()
    args = parse_args()
    root = repo_root()

    try:
        config = load_config(args.config, root)
        output_dir = config["table_output_directory"]
        output_dir.mkdir(parents=True, exist_ok=True)

        logging.info("Reading raw OSM inputs.")
        study_area = read_geodata(config["study_area_input"], "study-area")
        roads = read_geodata(config["raw_road_input"], "road")
        buildings = read_geodata(config["raw_building_input"], "building")

        expected = config["expected_source_fields"]
        inventory_rows = (
            field_inventory_rows("roads", roads, expected["roads"])
            + field_inventory_rows("buildings", buildings, expected["buildings"])
            + field_inventory_rows("study_area", study_area, [])
        )
        inventory = pd.DataFrame(inventory_rows, columns=FIELD_INVENTORY_FIELDS)
        completeness = pd.DataFrame(
            completeness_rows("roads", roads, expected["roads"])
            + completeness_rows("buildings", buildings, expected["buildings"])
        )
        geometry_profile = pd.DataFrame(
            [
                geometry_profile_row("study_area", study_area),
                geometry_profile_row("roads", roads),
                geometry_profile_row("buildings", buildings),
            ]
        )
        frequency_fields = config["parsing_configuration"]["frequency_fields"]
        frequencies = pd.DataFrame(
            frequency_rows("roads", roads, frequency_fields["roads"])
            + frequency_rows("buildings", buildings, frequency_fields["buildings"])
        )

        logging.info("Writing profiling tables.")
        inventory.to_csv(output_dir / "osm_field_inventory.csv", index=False)
        completeness.to_csv(output_dir / "osm_attribute_completeness_baseline.csv", index=False)
        geometry_profile.to_csv(output_dir / "osm_geometry_profile.csv", index=False)
        frequencies.to_csv(output_dir / "osm_key_value_frequencies.csv", index=False)
        write_json(
            profile_summary(root, config, roads, buildings, study_area, inventory),
            output_dir / "osm_source_profile_summary.json",
        )

        logging.info("Profiling complete: %s roads, %s buildings.", len(roads), len(buildings))
        return 0
    except Exception:
        logging.exception("OSM source profiling failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
