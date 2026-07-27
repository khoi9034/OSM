# ArcGIS Pro Phase 2 Manual Review

## Purpose

Use this workflow to visually and tabularly review Phase 2 standardized OSM outputs without altering raw data.

## Inputs

- `01_raw_data/osm/orlando_osm_study_area.geojson`
- `01_raw_data/osm/orlando_osm_roads_raw.geojson`
- `01_raw_data/osm/orlando_osm_buildings_raw.geojson`
- `02_geodatabases/analysis/osm_analysis.gpkg`
- `05_tables/standardization_exceptions.csv`

## Review Steps

1. Open ArcGIS Pro and create or open a local project for manual review.
2. Add the raw GeoJSON study-area, road, and building layers.
3. Add `orlando_study_area`, `roads_standardized`, and `buildings_standardized` from `02_geodatabases/analysis/osm_analysis.gpkg`.
4. Set the map coordinate system to `EPSG:2236`, NAD 1983 StatePlane Florida East FIPS 0901 Feet.
5. Compare raw and standardized road attributes, keeping in mind that each standardized row is a road edge.
6. Inspect `road_edge_id`, `source_u`, `source_v`, `source_key`, and `osm_id_raw` for traceability.
7. Review `road_class_source` beside `road_class_standard`.
8. Review `building_type_source` beside `building_type_standard`.
9. Verify that road `geometry_length_ft` and `geometry_length_m` are populated and nonnegative.
10. Verify that building `area_sqft` and `area_sqm` are populated and nonnegative.
11. Select records where `geometry_valid = false` in each standardized layer.
12. Open `05_tables/standardization_exceptions.csv` and filter by `severity`.
13. Review at least ten source-to-output examples across roads and buildings.
14. Document observations in a separate review note without editing raw GeoJSON files or standardized outputs.

## Optional File Geodatabase Export

Run this only from an ArcGIS Pro Python environment:

```bash
python 03_scripts/standardization/export_to_file_gdb.py
```

Expected feature classes:

- `Orlando_OSM_Study_Area`
- `OSM_Roads_Standardized`
- `OSM_Buildings_Standardized`

If ArcPy is unavailable, the script exits with an explanatory message and does not install anything.
