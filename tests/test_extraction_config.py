from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03_scripts" / "extraction"))

from osm_extraction_utils import REQUIRED_CONFIG_KEYS, load_config, resolve_repo_path  # noqa: E402


def valid_config() -> dict:
    return {
        "study_area_name": "Orlando_OSM_Study_Area",
        "center_latitude": 28.5383,
        "center_longitude": -81.3792,
        "radius_meters": 4828,
        "source_crs": "EPSG:4326",
        "projected_crs": "EPSG:2236",
        "road_network_type": "drive",
        "output_directory": "01_raw_data/osm",
    }


def test_included_config_has_required_keys():
    config_path = Path(__file__).resolve().parents[1] / "03_scripts" / "extraction" / "extraction_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert REQUIRED_CONFIG_KEYS <= set(config)


def test_load_config_resolves_output_directory(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(valid_config()), encoding="utf-8")

    config = load_config(config_path, tmp_path)

    assert config["output_directory"] == tmp_path / "01_raw_data" / "osm"


def test_load_config_requires_expected_keys(tmp_path: Path):
    config = valid_config()
    del config["source_crs"]
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="source_crs"):
        load_config(config_path, tmp_path)


def test_resolve_repo_path_keeps_absolute_paths(tmp_path: Path):
    assert resolve_repo_path(tmp_path, Path("C:/Projects/OSM")) == tmp_path
