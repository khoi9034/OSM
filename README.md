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

Extract → Preserve raw data → Standardize → Validate geometry → Measure attribute completeness → Compare with authoritative data → Assess fitness for use → Publish findings

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

This repository is currently in the initialization phase. No datasets have been downloaded, no analysis has been completed, and no analytical findings have been produced yet.

## Data Attribution

© OpenStreetMap contributors

OSM data is distributed under the Open Database License and requires attribution.

## License

Original code and documentation in this repository are licensed under the MIT License. Third-party geographic data remains governed by its source license.
