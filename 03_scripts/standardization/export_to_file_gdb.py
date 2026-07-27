"""Optionally export Phase 2 GeoPackage layers to an ArcGIS file geodatabase."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from standardization_utils import load_config, repo_root  # noqa: E402


DEFAULT_CONFIG = SCRIPT_DIR / "standardization_config.json"
DEFAULT_GDB_RELATIVE = Path("02_geodatabases/analysis/osm_analysis.gdb")
LAYER_MAP = {
    "orlando_study_area": "Orlando_OSM_Study_Area",
    "roads_standardized": "OSM_Roads_Standardized",
    "buildings_standardized": "OSM_Buildings_Standardized",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export standardized GeoPackage layers to a file geodatabase.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Path to standardization_config.json.")
    parser.add_argument("--output-gdb", default=DEFAULT_GDB_RELATIVE, help="Output file geodatabase path.")
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def load_arcpy() -> Any | None:
    """Return ArcPy when available in the active Python environment."""
    try:
        import arcpy  # type: ignore[import-not-found]
    except ImportError:
        return None
    return arcpy


def field_names(arcpy: Any, feature_class: str) -> list[str]:
    return [field.name for field in arcpy.ListFields(feature_class) if field.type not in {"OID", "Geometry"}]


def export_layers(arcpy: Any, geopackage: Path, output_gdb: Path) -> dict[str, dict[str, Any]]:
    """Export configured GeoPackage layers and confirm feature counts."""
    if not geopackage.exists():
        raise FileNotFoundError(f"Standardized GeoPackage is missing: {geopackage}")

    output_gdb.parent.mkdir(parents=True, exist_ok=True)
    if not arcpy.Exists(str(output_gdb)):
        arcpy.management.CreateFileGDB(str(output_gdb.parent), output_gdb.stem)

    results: dict[str, dict[str, Any]] = {}
    for layer_name, feature_class_name in LAYER_MAP.items():
        source = f"{geopackage}\\{layer_name}"
        target = str(output_gdb / feature_class_name)
        if arcpy.Exists(target):
            arcpy.management.Delete(target)
        arcpy.conversion.ExportFeatures(source, target)
        count = int(arcpy.management.GetCount(target)[0])
        fields = field_names(arcpy, target)
        truncated = [field for field in fields if len(field) >= 64]
        results[layer_name] = {
            "feature_class": feature_class_name,
            "feature_count": count,
            "field_count": len(fields),
            "possible_truncated_fields": truncated,
        }
    return results


def main() -> int:
    configure_logging()
    args = parse_args()
    root = repo_root()
    config = load_config(args.config, root)
    output_gdb = Path(args.output_gdb)
    output_gdb = output_gdb if output_gdb.is_absolute() else root / output_gdb

    arcpy = load_arcpy()
    if arcpy is None:
        print("ArcPy is unavailable. Run this script from an ArcGIS Pro Python environment to export a file GDB.")
        return 0

    try:
        results = export_layers(arcpy, config["output_geopackage"], output_gdb)
        for layer_name, result in results.items():
            logging.info(
                "%s -> %s (%s features)",
                layer_name,
                result["feature_class"],
                result["feature_count"],
            )
        logging.info("File geodatabase export complete: %s", output_gdb)
        return 0
    except Exception:
        logging.exception("File geodatabase export failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
