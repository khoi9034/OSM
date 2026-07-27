"""Small shared helpers for Phase 2 profiling and standardization."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from pyproj import CRS

from osm_schema import BUILDING_STANDARDIZED_FIELDS, EXCEPTION_FIELDS, ROAD_STANDARDIZED_FIELDS


ATTRIBUTION = "(c) OpenStreetMap contributors"
FEET_TO_METERS = CRS.from_user_input("EPSG:2236").axis_info[0].unit_conversion_factor
REQUIRED_CONFIG_KEYS = {
    "raw_road_input",
    "raw_building_input",
    "study_area_input",
    "extraction_metadata_input",
    "analysis_crs",
    "output_geopackage",
    "table_output_directory",
    "road_class_mapping",
    "building_class_mapping",
    "parsing_configuration",
    "expected_source_fields",
}


def sequence_like(value: Any) -> bool:
    """Return True for non-string source sequences such as OSM list arrays."""
    return isinstance(value, (list, tuple, set)) or (
        not isinstance(value, (str, bytes, dict)) and isinstance(value, Iterable)
    )


def repo_root() -> Path:
    """Return the repository root from this script location."""
    return Path(__file__).resolve().parents[2]


def resolve_repo_path(path_value: str | Path, root: Path) -> Path:
    """Resolve repository-relative paths."""
    path = Path(path_value)
    return path if path.is_absolute() else root / path


def load_config(config_path: str | Path, root: Path | None = None) -> dict[str, Any]:
    """Load standardization configuration and resolve path fields."""
    root = root or repo_root()
    resolved = resolve_repo_path(config_path, root)
    with resolved.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    missing = sorted(REQUIRED_CONFIG_KEYS - set(config))
    if missing:
        raise ValueError(f"Missing required configuration keys: {', '.join(missing)}")

    for key in [
        "raw_road_input",
        "raw_building_input",
        "study_area_input",
        "extraction_metadata_input",
        "output_geopackage",
        "table_output_directory",
    ]:
        config[key] = resolve_repo_path(config[key], root)
    config["config_path"] = resolved
    return config


def utc_timestamp() -> str:
    """Return a compact UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_blank(value: Any) -> bool:
    """Return True for nulls, blank strings, and empty list/dict values."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        if bool(pd.isna(value)):
            return True
    except (TypeError, ValueError):
        pass
    if sequence_like(value):
        items = list(value)
        return not items or all(is_blank(item) for item in items)
    if isinstance(value, dict):
        return not value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return True
        if stripped in {"[]", "{}"}:
            return True
        if stripped.startswith(("[", "{")):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return False
            return is_blank(parsed)
    return False


def source_value_to_string(value: Any, max_length: int = 240) -> str:
    """Serialize a source value without expanding or interpreting it."""
    if is_blank(value):
        return ""
    if sequence_like(value):
        text = json.dumps(list(value), ensure_ascii=True, default=str)
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=True, default=str)
    else:
        text = str(value)
    return text if len(text) <= max_length else text[: max_length - 3] + "..."


def json_like(value: Any) -> bool:
    """Detect JSON-looking strings that parse as JSON."""
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped.startswith(("[", "{")):
        return False
    try:
        json.loads(stripped)
    except json.JSONDecodeError:
        return False
    return True


def list_like(value: Any) -> bool:
    """Detect actual or string-encoded list-like source values."""
    if sequence_like(value):
        return True
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if stripped.startswith("["):
        try:
            return isinstance(json.loads(stripped), list)
        except json.JSONDecodeError:
            return True
    return ";" in stripped or "|" in stripped


def value_tokens(value: Any) -> list[Any]:
    """Return conservative tokens for parser-only use."""
    if is_blank(value):
        return []
    if sequence_like(value):
        return [item for item in value if not is_blank(item)]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [item for item in parsed if not is_blank(item)]
            except json.JSONDecodeError:
                pass
        if ";" in stripped or "|" in stripped:
            return [item.strip() for item in re.split(r"[;|]", stripped) if item.strip()]
        return [stripped]
    return [value]


def distinct_token_strings(value: Any) -> list[str]:
    """Return distinct parser token strings, preserving deterministic order."""
    seen: set[str] = set()
    result: list[str] = []
    for token in value_tokens(value):
        text = source_value_to_string(token).strip()
        key = text.lower()
        if key and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def complete_mask(series: pd.Series) -> pd.Series:
    """Return True where source values count as present."""
    return ~series.map(is_blank)


def profile_field(dataset_name: str, gdf: gpd.GeoDataFrame, field_name: str, expected: bool = False) -> dict[str, Any]:
    """Build one source-field inventory row."""
    total = len(gdf)
    if field_name not in gdf.columns:
        return {
            "dataset_name": dataset_name,
            "field_name": field_name,
            "source_dtype": "absent",
            "total_record_count": total,
            "non_null_count": 0,
            "null_count": total,
            "percent_complete": 0.0,
            "unique_value_count": 0,
            "sample_values": "",
            "contains_list_like_values": False,
            "contains_json_like_values": False,
            "notes": "Expected field absent" if expected else "Field absent",
        }

    series = gdf[field_name]
    mask = complete_mask(series)
    complete_values = series[mask]
    sample_values = [source_value_to_string(value, 80) for value in complete_values.head(5)]
    type_names = sorted({type(value).__name__ for value in complete_values})
    notes = []
    if len(type_names) > 1:
        notes.append("Mixed Python value types: " + ", ".join(type_names))
    if expected:
        notes.append("Expected source field")
    return {
        "dataset_name": dataset_name,
        "field_name": field_name,
        "source_dtype": str(series.dtype),
        "total_record_count": total,
        "non_null_count": int(mask.sum()),
        "null_count": int(total - mask.sum()),
        "percent_complete": round(float(mask.mean() * 100), 2) if total else 0.0,
        "unique_value_count": int(complete_values.map(source_value_to_string).nunique()),
        "sample_values": " | ".join(sample_values),
        "contains_list_like_values": bool(series[mask].map(list_like).any()) if total else False,
        "contains_json_like_values": bool(series[mask].map(json_like).any()) if total else False,
        "notes": "; ".join(notes),
    }


def field_inventory_rows(dataset_name: str, gdf: gpd.GeoDataFrame, expected_fields: Iterable[str]) -> list[dict[str, Any]]:
    """Inventory actual fields and expected-but-absent fields."""
    expected = set(expected_fields)
    rows = [profile_field(dataset_name, gdf, field, field in expected) for field in gdf.columns]
    for field in sorted(expected - set(gdf.columns)):
        rows.append(profile_field(dataset_name, gdf, field, True))
    return rows


def completeness_rows(dataset_name: str, gdf: gpd.GeoDataFrame, fields: Iterable[str]) -> list[dict[str, Any]]:
    """Build initial completeness baseline rows for selected fields."""
    rows = []
    for field in fields:
        row = profile_field(dataset_name, gdf, field, True)
        rows.append(
            {
                "dataset_name": dataset_name,
                "field_name": field,
                "field_present": field in gdf.columns,
                "total_record_count": row["total_record_count"],
                "non_null_count": row["non_null_count"],
                "null_count": row["null_count"],
                "percent_complete": row["percent_complete"],
                "notes": row["notes"],
            }
        )
    return rows


def frequency_rows(dataset_name: str, gdf: gpd.GeoDataFrame, fields: Iterable[str]) -> list[dict[str, Any]]:
    """Create source-value frequency rows without splitting source values."""
    rows: list[dict[str, Any]] = []
    total = len(gdf)
    for field in fields:
        if field not in gdf.columns:
            rows.append(
                {
                    "dataset_name": dataset_name,
                    "field_name": field,
                    "source_value": "<field absent>",
                    "record_count": 0,
                    "percent_of_dataset": 0.0,
                }
            )
            continue
        values = gdf[field].map(lambda value: source_value_to_string(value, 500) or "<blank>")
        for source_value, count in values.value_counts(dropna=False).sort_values(ascending=False).items():
            rows.append(
                {
                    "dataset_name": dataset_name,
                    "field_name": field,
                    "source_value": source_value,
                    "record_count": int(count),
                    "percent_of_dataset": round(float(count / total * 100), 2) if total else 0.0,
                }
            )
    return rows


def geometry_profile_row(dataset_name: str, gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    """Summarize geometry type, CRS, validity, and bounds."""
    valid = gdf.geometry.is_valid.fillna(False)
    bounds = gdf.total_bounds if len(gdf) else [None, None, None, None]
    return {
        "dataset_name": dataset_name,
        "feature_count": int(len(gdf)),
        "geometry_types": ";".join(sorted(gdf.geometry.dropna().geom_type.unique().tolist())),
        "crs": gdf.crs.to_string() if gdf.crs else "",
        "valid_geometry_count": int(valid.sum()),
        "invalid_geometry_count": int((~valid).sum()),
        "minx": bounds[0],
        "miny": bounds[1],
        "maxx": bounds[2],
        "maxy": bounds[3],
    }


def slug(value: Any) -> str:
    """Make a short deterministic identifier component."""
    text = source_value_to_string(value, 120)
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text.strip())
    return text.strip("_") or "blank"


def make_exception(
    dataset_name: str,
    source_record_id: str,
    field_name: str,
    source_value: Any,
    exception_type: str,
    severity: str,
    action_taken: str,
    review_required: bool = True,
) -> dict[str, Any]:
    """Create a standard exception row."""
    return {
        "dataset_name": dataset_name,
        "source_record_id": source_record_id,
        "field_name": field_name,
        "source_value": source_value_to_string(source_value, 500),
        "exception_type": exception_type,
        "severity": severity,
        "action_taken": action_taken,
        "review_required": review_required,
    }


def make_road_edge_id(row: pd.Series, row_number: int) -> tuple[str, dict[str, Any] | None]:
    """Create a stable road-edge ID from OSMnx edge identifiers."""
    missing = [field for field in ["u", "v", "key", "osmid"] if field not in row.index or is_blank(row[field])]
    if missing:
        fallback = f"road_edge_missing_id_{row_number}"
        return fallback, make_exception(
            "roads",
            fallback,
            ",".join(missing),
            "",
            "missing source identifier",
            "blocking",
            "Fallback row-number identifier assigned to preserve record count.",
        )
    return f"road_edge_{slug(row['u'])}_{slug(row['v'])}_{slug(row['key'])}_{slug(row['osmid'])}", None


def make_building_feature_id(row: pd.Series, row_number: int) -> tuple[str, dict[str, Any] | None]:
    """Create a stable building feature ID from OSM element metadata."""
    element_field = "element" if "element" in row.index else "element_type"
    id_field = "id" if "id" in row.index else "osmid"
    missing = [field for field in [element_field, id_field] if field not in row.index or is_blank(row[field])]
    if missing:
        fallback = f"building_missing_id_{row_number}"
        return fallback, make_exception(
            "buildings",
            fallback,
            ",".join(missing),
            "",
            "missing source identifier",
            "blocking",
            "Fallback row-number identifier assigned to preserve record count.",
        )
    return f"building_{slug(row[element_field])}_{slug(row[id_field])}", None


def parse_speed_mph(value: Any, mph_per_kph: float = 0.621371) -> tuple[float | None, str | None]:
    """Parse unambiguous maxspeed values into miles per hour."""
    tokens = distinct_token_strings(value)
    if not tokens:
        return None, None
    if len(tokens) > 1:
        return None, "ambiguous multi-value field"

    text = tokens[0].lower().strip()
    if text in {"signals", "variable", "national", "none", "walk"}:
        return None, "unparsed speed value"
    mph_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:mph)?", text)
    if mph_match:
        speed = float(mph_match.group(1))
        return (speed, None) if speed > 0 else (None, "impossible numeric value")
    kph_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:km/h|kph)", text)
    if kph_match:
        speed = float(kph_match.group(1))
        return (round(speed * mph_per_kph, 2), None) if speed > 0 else (None, "impossible numeric value")
    return None, "unparsed speed value"


def parse_lanes_count(value: Any) -> tuple[int | None, str | None]:
    """Parse unambiguous positive whole-number lane values."""
    tokens = distinct_token_strings(value)
    if not tokens:
        return None, None
    if len(tokens) > 1:
        return None, "ambiguous multi-value field"
    text = tokens[0].strip()
    if re.fullmatch(r"\d+", text):
        lanes = int(text)
        return (lanes, None) if lanes > 0 else (None, "impossible numeric value")
    return None, "unparsed lane value"


def normalize_oneway(value: Any) -> tuple[str, str | None]:
    """Normalize explicit one-way values into a controlled nullable label."""
    tokens = distinct_token_strings(value)
    if not tokens:
        return "Unknown", None
    if len(tokens) > 1:
        return "Unknown", "ambiguous multi-value field"
    text = tokens[0].lower().strip()
    if text in {"yes", "true", "1"}:
        return "Yes", None
    if text in {"no", "false", "0"}:
        return "No", None
    if text in {"-1", "reverse", "reversed"}:
        return "Reverse", None
    if text in {"unknown"}:
        return "Unknown", None
    return "Unknown", "unparsed oneway value"


def parse_building_levels(value: Any) -> tuple[float | None, str | None]:
    """Parse unambiguous positive building-level values."""
    tokens = distinct_token_strings(value)
    if not tokens:
        return None, None
    if len(tokens) > 1:
        return None, "ambiguous multi-value field"
    text = tokens[0].strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        levels = float(text)
        return (levels, None) if levels > 0 else (None, "impossible numeric value")
    return None, "unparsed building-level value"


def classify_road(value: Any, mapping: dict[str, str]) -> tuple[str | None, str | None]:
    """Map OSM highway values to project road classes."""
    tokens = distinct_token_strings(value)
    if not tokens:
        return "Unknown", "missing source classification value"
    if len(tokens) > 1:
        return None, "ambiguous multi-value field"
    key = tokens[0].lower().strip()
    if key in mapping:
        return mapping[key], None
    return "Other or unmapped", "unknown road classification"


def classify_building(value: Any, mapping: dict[str, str]) -> tuple[str, str | None]:
    """Map OSM building values to project building classes."""
    tokens = distinct_token_strings(value)
    if not tokens:
        return "Unknown", "missing source classification value"
    if len(tokens) > 1:
        return "Unknown", "ambiguous multi-value field"
    key = tokens[0].lower().strip()
    if key in mapping:
        return mapping[key], None
    return "Other", "unknown building classification"


def geometry_valid(value: Any) -> bool:
    """Return False for missing or invalid geometries."""
    return bool(value is not None and not value.is_empty and value.is_valid)


def length_fields(geometry: Any) -> tuple[float | None, float | None]:
    """Calculate geometry length in EPSG:2236 feet and meters."""
    if geometry is None:
        return None, None
    length_ft = float(geometry.length)
    return length_ft, length_ft * FEET_TO_METERS


def area_fields(geometry: Any) -> tuple[float | None, float | None]:
    """Calculate geometry area in EPSG:2236 square feet and square meters."""
    if geometry is None:
        return None, None
    area_sqft = float(geometry.area)
    return area_sqft, area_sqft * (FEET_TO_METERS**2)


def float_or_none(value: Any) -> float | None:
    """Parse a source numeric value without treating unknowns as zero."""
    if is_blank(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def deduplicate_ids(
    ids: list[str],
    dataset_name: str,
    field_name: str,
    exceptions: list[dict[str, Any]],
) -> list[str]:
    """Append row numbers to duplicate generated IDs and log exceptions."""
    seen: set[str] = set()
    output: list[str] = []
    for row_number, value in enumerate(ids):
        if value in seen:
            unique = f"{value}_{row_number}"
            exceptions.append(
                make_exception(
                    dataset_name,
                    unique,
                    field_name,
                    value,
                    "duplicate generated identifier",
                    "blocking",
                    "Row-number suffix appended to preserve one output record per source record.",
                )
            )
            output.append(unique)
        else:
            output.append(value)
            seen.add(value)
    return output


def schema_missing_fields(gdf: gpd.GeoDataFrame, expected_fields: list[str]) -> list[str]:
    """Return missing standardized schema fields."""
    return [field for field in expected_fields if field not in gdf.columns]


def record_preservation(input_count: int, output_count: int) -> bool:
    """Validate one input record produced one output record."""
    return int(input_count) == int(output_count)


def exception_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Return exceptions with stable columns even when empty."""
    return pd.DataFrame(rows, columns=EXCEPTION_FIELDS)


def standardized_schema_ok(roads: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame) -> bool:
    """Validate standardized datasets expose the required fields."""
    return not schema_missing_fields(roads, ROAD_STANDARDIZED_FIELDS) and not schema_missing_fields(
        buildings, BUILDING_STANDARDIZED_FIELDS
    )
