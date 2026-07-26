# Phase 1: OSM Extraction Methodology

## Objective

Phase 1 defines the initial downtown Orlando study area, downloads raw OpenStreetMap roads and building footprints, and records enough metadata to reproduce the extraction.

## Study-Area Definition

The study area is named `Orlando_OSM_Study_Area`. It is centered on downtown Orlando at latitude `28.5383` and longitude `-81.3792` with an approximately three-mile radius, stored as `4,828` meters in the extraction configuration.

The boundary is created from the center point in code. The point is projected, buffered, and transformed back to the source coordinate system for OpenStreetMap queries.

## Coordinate Systems

- Source and OSM query CRS: `EPSG:4326`
- Local distance and area CRS: `EPSG:2236`, NAD 1983 StatePlane Florida East FIPS 0901 Feet

## Road Extraction Method

The road network is downloaded with OSMnx using `graph_from_polygon` and `network_type="drive"`. The resulting graph is converted to edge GeoDataFrames, preserving the OSM attributes returned by OSMnx, including optional tags when present.

## Building Extraction Method

Building footprints are downloaded with OSMnx using the tag query `building=*`. Polygon and multipolygon features are retained. Tags such as `building=yes` are preserved as source values and are not reclassified in this phase.

## Raw-Data Preservation

Raw outputs are written under `01_raw_data/osm/`. These generated files are intentionally ignored by Git so extraction snapshots do not inflate the repository or imply permanent analytical results.

## Output Datasets

- `01_raw_data/osm/orlando_osm_study_area.geojson`
- `01_raw_data/osm/orlando_osm_roads_raw.geojson`
- `01_raw_data/osm/orlando_osm_buildings_raw.geojson`
- `01_raw_data/osm/extraction_metadata.json`
- `01_raw_data/osm/extraction_inventory.csv`

## Validation Checks

The extraction script verifies that the study-area geometry exists and is valid, roads and buildings are not empty, roads contain line geometry, buildings contain polygon or multipolygon geometry, all spatial outputs have a CRS, files were written, and metadata feature counts match the saved datasets.

## Reproducibility

Run the extraction from the repository root:

```bash
python 03_scripts/extraction/download_osm_data.py
```

An alternate configuration can be supplied:

```bash
python 03_scripts/extraction/download_osm_data.py --config 03_scripts/extraction/extraction_config.json
```

## Current Limitations

- OSM changes continuously.
- Completeness varies by location and feature type.
- Complex OSM relations may require additional review.
- This phase does not determine whether OSM is accurate or operationally suitable.
- Downloaded outputs are snapshots from the extraction timestamp.

## Attribution

© OpenStreetMap contributors

OSM data is distributed under the Open Database License and requires attribution.
