# OpenStreetMap Operational Readiness Assessment

## Project Overview

This project evaluates whether OpenStreetMap road and building data can support professional GIS workflows in Orlando, Florida. The planned workflow combines OSM extraction, schema standardization, geometry validation, attribute-completeness analysis, comparison with authoritative GIS data, and a documented fitness-for-use recommendation.

## Business Question

Can OpenStreetMap road and building data support professional GIS workflows in Orlando, and what validation is required before operational use?

## Study Area

The initial study area will cover downtown Orlando and an approximately three-mile surrounding area.

## Planned Datasets

- OpenStreetMap roads
- OpenStreetMap building footprints
- Authoritative City of Orlando or Orange County GIS data
- Aerial imagery

## Planned Workflow

Extract -> Preserve raw data -> Standardize -> Validate geometry -> Measure attribute completeness -> Compare with authoritative data -> Assess fitness for use -> Publish findings

## Repository Structure

```text
OSM/
|-- 01_raw_data/
|   |-- osm/
|   `-- authoritative/
|-- 02_geodatabases/
|   |-- raw/
|   `-- analysis/
|-- 03_scripts/
|   |-- extraction/
|   |-- standardization/
|   |-- qa/
|   |-- comparison/
|   `-- reporting/
|-- 04_maps/
|-- 05_tables/
|-- 06_documentation/
|   |-- methodology/
|   |-- workflow_diagrams/
|   `-- findings/
|-- 07_notebooks/
`-- tests/
```

## Tools

- Python
- ArcPy
- ArcGIS Pro
- OpenStreetMap
- Overpass API
- GeoJSON
- File geodatabases
- Authoritative City of Orlando or Orange County GIS data
- Aerial imagery

## Current Status

Phase 1 OSM extraction is complete. Phase 2 profiling and standardization is complete after the profiling and standardization scripts run successfully against the local Phase 1 outputs.

No authoritative-data comparison, final QA score, or fitness-for-use conclusion has been completed yet.

## Phase 1: OSM Extraction

Phase 1 uses downtown Orlando as the center of the initial study area, covering approximately a three-mile radius. Python and OSMnx retrieve public motor-vehicle roads and building footprints from OpenStreetMap.

Raw OSM tags are preserved so later phases can standardize schemas, validate geometry, measure attribute completeness, and compare OSM features with authoritative GIS data. Downloaded data is intentionally excluded from Git because OSM extracts are local snapshots.

Install dependencies inside a virtual environment or ArcGIS Pro Python environment:

```bash
python -m pip install -r requirements.txt
```

Run the extraction from the repository root:

```bash
python 03_scripts/extraction/download_osm_data.py
```

OSM data changes over time, so feature counts and tags depend on the extraction date.

## Phase 2: Profiling and Standardization

Phase 2 profiles the actual raw OSM road-edge and building schemas, measures initial attribute completeness, and creates controlled operational road and building datasets for later QA/QC and authoritative comparison.

Run profiling from the repository root:

```bash
python 03_scripts/standardization/profile_osm_data.py
```

Run standardization from the repository root:

```bash
python 03_scripts/standardization/standardize_osm_data.py
```

Optional ArcGIS Pro file geodatabase export:

```bash
python 03_scripts/standardization/export_to_file_gdb.py
```

Generated spatial and tabular outputs remain excluded from Git, including raw GeoJSON files, GeoPackages, file geodatabases, CSV reports, and JSON analytical summaries. Code, tests, configuration, and methodology documentation are version controlled.

## Data Attribution

(c) OpenStreetMap contributors

OSM data is distributed under the Open Database License and requires attribution.

## License

Original code and documentation in this repository are licensed under the MIT License. Third-party geographic data remains governed by its source license.
