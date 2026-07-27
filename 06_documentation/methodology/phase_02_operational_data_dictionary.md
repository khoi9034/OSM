# Phase 2 Operational Data Dictionary

## Roads Standardized

| Field name | Dataset | Data type | Definition | Source field | Transformation rule | Null meaning | Example |
|---|---|---|---|---|---|---|---|
| `road_edge_id` | roads | text | Stable project identifier for one OSMnx road edge. | `u`, `v`, `key`, `osmid` | Concatenate deterministic source identifiers; suffix duplicates when required. | Identifier could not be generated without a blocking exception. | `road_edge_1_2_0_99` |
| `osm_id_raw` | roads | text | Raw OSM identifier value. | `osmid` | Preserve source value as text. | Source value absent. | `99` |
| `source_u` | roads | text | Raw OSMnx start node identifier. | `u` | Preserve source value as text. | Source value absent. | `123` |
| `source_v` | roads | text | Raw OSMnx end node identifier. | `v` | Preserve source value as text. | Source value absent. | `456` |
| `source_key` | roads | text | Raw OSMnx edge key. | `key` | Preserve source value as text. | Source value absent. | `0` |
| `road_name` | roads | text | Source road name. | `name` | Preserve source value as text. | Name absent in OSM. | `Orange Ave` |
| `road_class_source` | roads | text | Raw OSM highway classification. | `highway` | Preserve source value as text. | Highway tag absent. | `residential` |
| `road_class_standard` | roads | text | Project-standard operational road class. | `highway` | Map configured OSM values conservatively. | Classification could not be safely assigned. | `Local street` |
| `maxspeed_raw` | roads | text | Raw source speed value. | `maxspeed` | Preserve source value as text. | Speed tag absent. | `30 mph` |
| `maxspeed_mph` | roads | float | Parsed speed in miles per hour. | `maxspeed` | Parse plain mph or explicit km/h only. | Unknown, ambiguous, or unparsed speed. | `30` |
| `lanes_raw` | roads | text | Raw source lane value. | `lanes` | Preserve source value as text. | Lane tag absent. | `2` |
| `lanes_count` | roads | integer | Parsed lane count. | `lanes` | Parse positive whole numbers only. | Unknown, ambiguous, or unparsed lane count. | `2` |
| `oneway_raw` | roads | text | Raw one-way value. | `oneway` | Preserve source value as text. | Source value absent. | `True` |
| `oneway_standard` | roads | text | Controlled one-way value. | `oneway` | Normalize explicit yes/no/reverse values. | Not used; unknown is stored as `Unknown`. | `No` |
| `surface_raw` | roads | text | Raw road surface value. | `surface` | Preserve source value as text. | Surface tag absent. | `asphalt` |
| `access_raw` | roads | text | Raw access tag. | `access` | Preserve source value as text. | Access tag absent. | `private` |
| `service_raw` | roads | text | Raw service tag. | `service` | Preserve source value as text. | Service tag absent. | `driveway` |
| `bridge_raw` | roads | text | Raw bridge tag. | `bridge` | Preserve source value as text. | Bridge tag absent. | `yes` |
| `tunnel_raw` | roads | text | Raw tunnel tag. | `tunnel` | Preserve source value as text. | Tunnel tag absent. | `yes` |
| `junction_raw` | roads | text | Raw junction tag. | `junction` | Preserve source value as text. | Junction tag absent. | `roundabout` |
| `reversed_raw` | roads | text | Raw OSMnx network reverse-direction metadata. | `reversed` | Preserve source value as text; do not parse as JSON. | Source value absent. | `False` |
| `source_length_m` | roads | float | Raw OSMnx length in meters. | `length` | Preserve numeric source length when parseable. | Source length absent or not numeric. | `42.5` |
| `geometry_length_ft` | roads | float | Calculated geometry length in EPSG:2236 feet. | geometry | Reproject to EPSG:2236 and calculate length. | Geometry missing. | `139.4` |
| `geometry_length_m` | roads | float | Calculated geometry length in meters. | geometry | Convert EPSG:2236 feet to meters. | Geometry missing. | `42.5` |
| `geometry_valid` | roads | boolean | Whether source geometry is present, non-empty, and valid. | geometry | Evaluate geometry validity without repair. | Not expected. | `True` |
| `source_dataset` | roads | text | Raw dataset filename. | constant | Store source dataset name. | Not expected. | `orlando_osm_roads_raw.geojson` |
| `extraction_timestamp_utc` | roads | text | Phase 1 extraction timestamp. | metadata | Copy from extraction metadata. | Metadata value absent. | `2026-07-26T00:00:00Z` |
| `standardization_status` | roads | text | Per-record standardization status. | exceptions | `standardized`, `review_required`, or `blocking_review_required`. | Not expected. | `standardized` |
| `standardization_notes` | roads | text | Exception summary for the record. | exceptions | Join exception types for that record. | No exceptions. | `unparsed speed value` |
| `geometry` | roads | geometry | Road-edge geometry. | geometry | Reproject to EPSG:2236; do not repair. | Geometry missing in source. | `LineString` |

## Buildings Standardized

| Field name | Dataset | Data type | Definition | Source field | Transformation rule | Null meaning | Example |
|---|---|---|---|---|---|---|---|
| `building_feature_id` | buildings | text | Stable project identifier for one OSM building feature. | `element`, `id` or `osmid` | Concatenate deterministic source identifiers; suffix duplicates when required. | Identifier could not be generated without a blocking exception. | `building_way_10` |
| `osm_id_raw` | buildings | text | Raw OSM identifier value. | `id` or `osmid` | Preserve source value as text. | Source value absent. | `10` |
| `element_type` | buildings | text | Raw OSM element type. | `element` or `element_type` | Preserve source value as text. | Source value absent. | `way` |
| `building_name` | buildings | text | Source building name. | `name` | Preserve source value as text. | Name absent in OSM. | `City Hall` |
| `building_type_source` | buildings | text | Raw OSM building tag. | `building` | Preserve source value as text. | Building tag absent. | `apartments` |
| `building_type_standard` | buildings | text | Project-standard operational building class. | `building` | Map configured OSM values conservatively. | Not used; missing source is stored as `Unknown`. | `Residential` |
| `building_levels_raw` | buildings | text | Raw building-level value. | `building:levels` | Preserve source value as text. | Level tag absent. | `3` |
| `building_levels_count` | buildings | float | Parsed building levels. | `building:levels` | Parse positive numeric values only. | Unknown, ambiguous, or unparsed level count. | `3` |
| `address_number` | buildings | text | Source address number. | `addr:housenumber` | Preserve source value as text. | Address number absent. | `400` |
| `address_street` | buildings | text | Source address street. | `addr:street` | Preserve source value as text. | Address street absent. | `S Orange Ave` |
| `address_city` | buildings | text | Source address city. | `addr:city` | Preserve source value as text. | Address city absent. | `Orlando` |
| `address_postcode` | buildings | text | Source postal code. | `addr:postcode` | Preserve source value as text. | Postal code absent. | `32801` |
| `amenity_raw` | buildings | text | Raw amenity tag retained for review. | `amenity` | Preserve source value as text; do not override `building`. | Amenity tag absent. | `school` |
| `shop_raw` | buildings | text | Raw shop tag retained for review. | `shop` | Preserve source value as text; do not override `building`. | Shop tag absent. | `supermarket` |
| `office_raw` | buildings | text | Raw office tag retained for review. | `office` | Preserve source value as text; do not override `building`. | Office tag absent. | `government` |
| `landuse_raw` | buildings | text | Raw landuse tag retained for review. | `landuse` | Preserve source value as text. | Landuse tag absent. | `commercial` |
| `area_sqft` | buildings | float | Calculated footprint area in EPSG:2236 square feet. | geometry | Reproject to EPSG:2236 and calculate area. | Geometry missing. | `1250.5` |
| `area_sqm` | buildings | float | Calculated footprint area in square meters. | geometry | Convert EPSG:2236 square feet to square meters. | Geometry missing. | `116.2` |
| `geometry_valid` | buildings | boolean | Whether source geometry is present, non-empty, and valid. | geometry | Evaluate geometry validity without repair. | Not expected. | `True` |
| `source_dataset` | buildings | text | Raw dataset filename. | constant | Store source dataset name. | Not expected. | `orlando_osm_buildings_raw.geojson` |
| `extraction_timestamp_utc` | buildings | text | Phase 1 extraction timestamp. | metadata | Copy from extraction metadata. | Metadata value absent. | `2026-07-26T00:00:00Z` |
| `standardization_status` | buildings | text | Per-record standardization status. | exceptions | `standardized`, `review_required`, or `blocking_review_required`. | Not expected. | `review_required` |
| `standardization_notes` | buildings | text | Exception summary for the record. | exceptions | Join exception types for that record. | No exceptions. | `unknown building classification` |
| `geometry` | buildings | geometry | Building footprint geometry. | geometry | Reproject to EPSG:2236; do not repair. | Geometry missing in source. | `Polygon` |
