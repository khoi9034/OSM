"""Download Phase 1 OpenStreetMap roads and buildings for downtown Orlando."""

from __future__ import annotations

import argparse
import json
import logging
import platform
import sys
import time
from pathlib import Path
from typing import Callable, TypeVar

import geopandas as gpd
import osmnx as ox
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from osm_extraction_utils import (  # noqa: E402
    ATTRIBUTION,
    build_metadata,
    create_study_area,
    inventory_row,
    load_config,
    repo_root,
    save_geojson,
    utc_timestamp,
    validate_metadata_counts,
    validate_spatial_datasets,
)


DEFAULT_CONFIG = SCRIPT_DIR / "extraction_config.json"
OUTPUT_FILENAMES = {
    "study_area": "orlando_osm_study_area.geojson",
    "roads": "orlando_osm_roads_raw.geojson",
    "buildings": "orlando_osm_buildings_raw.geojson",
    "metadata": "extraction_metadata.json",
    "inventory": "extraction_inventory.csv",
}
T = TypeVar("T")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download raw OSM roads and buildings for downtown Orlando.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Path to extraction_config.json.")
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def configure_osmnx(output_directory: Path) -> None:
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(output_directory / "osmnx_cache")
    ox.settings.requests_timeout = 180
    ox.settings.overpass_rate_limit = True


def retry(label: str, action: Callable[[], T], attempts: int = 3, delay_seconds: int = 10) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except Exception as exc:
            if attempt == attempts:
                raise RuntimeError(f"{label} failed after {attempts} attempts: {exc}") from exc
            logging.warning("%s failed on attempt %s/%s: %s", label, attempt, attempts, exc)
            time.sleep(delay_seconds * attempt)
    raise RuntimeError(f"{label} failed.")


def download_roads(study_area: gpd.GeoDataFrame, network_type: str) -> gpd.GeoDataFrame:
    polygon = study_area.geometry.iloc[0]
    graph = retry(
        "Road download",
        lambda: ox.graph_from_polygon(polygon, network_type=network_type, simplify=True),
    )
    roads = ox.graph_to_gdfs(graph, nodes=False, edges=True, fill_edge_geometry=True)
    return roads.to_crs(study_area.crs) if roads.crs else roads.set_crs(study_area.crs)


def download_buildings(study_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    polygon = study_area.geometry.iloc[0]
    features_from_polygon = getattr(ox, "features_from_polygon", None) or ox.geometries_from_polygon
    buildings = retry("Building download", lambda: features_from_polygon(polygon, tags={"building": True}))
    buildings = buildings[buildings.geometry.notna()].copy()
    buildings = buildings[buildings.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    return buildings.to_crs(study_area.crs) if buildings.crs else buildings.set_crs(study_area.crs)


def write_json(data: dict, output_path: Path) -> None:
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    configure_logging()
    args = parse_args()
    root = repo_root()

    try:
        logging.info("Loading extraction configuration.")
        config = load_config(args.config, root)
        output_directory = config["output_directory"]
        output_directory.mkdir(parents=True, exist_ok=True)
        configure_osmnx(output_directory)

        output_paths = {name: output_directory / filename for name, filename in OUTPUT_FILENAMES.items()}
        timestamp = utc_timestamp()

        logging.info("Creating study-area boundary.")
        study_area = create_study_area(config)
        study_area_failures = validate_spatial_datasets(
            study_area,
            gpd.GeoDataFrame(geometry=[], crs=config["source_crs"]),
            gpd.GeoDataFrame(geometry=[], crs=config["source_crs"]),
        )
        if any("Study-area" in failure for failure in study_area_failures):
            raise ValueError("; ".join(study_area_failures))
        save_geojson(study_area, output_paths["study_area"])

        logging.info("Downloading OSM road network with network_type=%s.", config["road_network_type"])
        roads = download_roads(study_area, config["road_network_type"])
        logging.info("Downloaded %s road features.", len(roads))

        logging.info("Downloading OSM building footprints.")
        buildings = download_buildings(study_area)
        logging.info("Downloaded %s building footprint features.", len(buildings))

        failures = validate_spatial_datasets(study_area, roads, buildings)
        if failures:
            raise ValueError("; ".join(failures))

        logging.info("Writing raw GeoJSON outputs.")
        save_geojson(roads, output_paths["roads"])
        save_geojson(buildings, output_paths["buildings"])

        logging.info("Reloading saved outputs for validation.")
        saved_study_area = gpd.read_file(output_paths["study_area"])
        saved_roads = gpd.read_file(output_paths["roads"])
        saved_buildings = gpd.read_file(output_paths["buildings"])
        failures = validate_spatial_datasets(saved_study_area, saved_roads, saved_buildings)
        if failures:
            raise ValueError("; ".join(failures))

        metadata = build_metadata(
            config=config,
            roads=saved_roads,
            buildings=saved_buildings,
            output_paths=output_paths,
            extraction_timestamp_utc=timestamp,
            osmnx_version=ox.__version__,
            python_version=platform.python_version(),
            root=root,
        )
        metadata_failures = validate_metadata_counts(metadata, saved_roads, saved_buildings)
        if metadata_failures:
            raise ValueError("; ".join(metadata_failures))

        logging.info("Writing extraction metadata and inventory.")
        write_json(metadata, output_paths["metadata"])
        inventory = pd.DataFrame(
            [
                inventory_row("study area", "boundary", saved_study_area, output_paths["study_area"], timestamp, root),
                inventory_row("roads", "raw OSM road edges", saved_roads, output_paths["roads"], timestamp, root),
                inventory_row(
                    "buildings",
                    "raw OSM building footprints",
                    saved_buildings,
                    output_paths["buildings"],
                    timestamp,
                    root,
                ),
            ]
        )
        inventory.to_csv(output_paths["inventory"], index=False)

        logging.info("Extraction complete. Attribution: %s", ATTRIBUTION)
        return 0
    except Exception:
        logging.exception("OSM extraction failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
