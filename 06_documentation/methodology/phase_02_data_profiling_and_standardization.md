# Phase 2: Data Profiling and Standardization

## Objective

Phase 2 profiles the raw OpenStreetMap road-edge and building datasets from Phase 1, measures initial source-field completeness, and transforms flexible OSM tags into controlled operational schemas. The output is intended for later QA/QC, authoritative-data comparison, and downstream geospatial production. It is not a final quality score.

## Why OSM Requires Profiling

OSM is community maintained and tag driven. Two features of the same general type may carry different fields, different value formats, or no value for an expected field. Profiling the actual files before standardization prevents the workflow from assuming tags that are absent in the Orlando extract.

## Flexible OSM Tags

OSM tags are key-value pairs. Common fields such as `highway`, `building`, `maxspeed`, `lanes`, and `building:levels` may be blank, scalar strings, list-like strings, JSON-like strings, or mixed source values. Phase 2 preserves those raw values and parses only conservative, unambiguous cases.

## Source Schema Versus Target Schema

The raw schema is whatever OSM and OSMnx returned during extraction. The target schema is a project-controlled operational schema with stable field names, standardized class values, parsed numeric fields, geometry validity flags, lineage identifiers, and exception notes.

## Road-Edge Representation

The road dataset is an OSMnx network-edge dataset. A row represents a road edge, not necessarily a unique real-world roadway. Directed edges, parallel edges, and split geometry may appear as separate records. Phase 2 preserves every input edge as one standardized output edge.

## Controlled Road Schema

The standardized road layer is `roads_standardized` in `02_geodatabases/analysis/osm_analysis.gpkg`. It stores source identifiers, source tags, standardized operational road class, parsed speed and lane values where safe, one-way normalization, projected geometry length, geometry validity, lineage, and review status.

## Controlled Building Schema

The standardized building layer is `buildings_standardized` in the same GeoPackage. It stores source identifiers, source building tags, standardized operational building class, parsed levels where safe, address/supporting tags, projected area, geometry validity, lineage, and review status.

## Classification Mappings

Road `highway` values are mapped to project categories such as `Limited-access road`, `Major arterial-style road`, `Local street`, and `Service road`. These categories are project-standardized operational groupings, not official government functional classes.

Building `building` values are mapped to project categories such as `Residential`, `Commercial`, `Industrial`, `Educational`, `Healthcare`, `Religious`, `Civic/Government`, and `Accessory/Non-occupiable structure`. Supporting fields such as `amenity`, `shop`, and `office` are retained but do not override `building`.

## Conservative Parsing Rules

Speed is parsed only from plain numeric mph values or explicit `km/h`/`kph` values. Lanes are parsed only from positive whole numbers. Building levels are parsed only from positive numeric values. Multi-value, conflicting, symbolic, malformed, or impossible values remain null in parsed fields and are written to the exception report.

## Measurement Coordinate System

Standardized geometry is stored in `EPSG:2236`, NAD 1983 StatePlane Florida East FIPS 0901 Feet. Road length and building area are calculated after projection. Phase 2 does not measure distance or area in `EPSG:4326`.

## Exception Handling

The workflow writes `05_tables/standardization_exceptions.csv`. Exceptions include missing identifiers, duplicate generated identifiers, unparsed values, unknown classifications, invalid geometry, ambiguous multi-value fields, and impossible numeric values. Missing optional OSM tags are not automatically blocking.

## Record Lineage

Road outputs use `road_edge_id`, generated from `u`, `v`, `key`, and `osmid` when available. Building outputs use `building_feature_id`, generated from the OSM element type and identifier. Raw identifier fields are preserved in standardized attributes.

## Geometry Policy

Geometry validity is checked and reported. Phase 2 does not repair geometry, run buffer-zero fixes, dissolve features, aggregate records, or drop invalid geometry. Repair decisions belong in a later QA phase.

## Generated Outputs

- `05_tables/osm_field_inventory.csv`
- `05_tables/osm_attribute_completeness_baseline.csv`
- `05_tables/osm_geometry_profile.csv`
- `05_tables/osm_key_value_frequencies.csv`
- `05_tables/osm_source_profile_summary.json`
- `02_geodatabases/analysis/osm_analysis.gpkg`
- `05_tables/standardization_exceptions.csv`
- `05_tables/standardization_summary.json`

These outputs are local analytical products and are ignored by Git.

## Current Limitations

- The workflow does not compare OSM against authoritative road or building datasets.
- The workflow does not assign a final quality score or fitness-for-use conclusion.
- Unknown or ambiguous values are preserved for manual review rather than guessed.
- Invalid geometry is reported but not repaired.
- File geodatabase export requires ArcPy from an ArcGIS Pro Python environment.

## Next Phase

The next phase should review exceptions, evaluate geometry and attribute quality, and compare standardized OSM outputs with authoritative local GIS data before making any operational suitability conclusion.
