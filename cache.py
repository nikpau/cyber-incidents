"""
Application Cache Precomputation Module
========================================

This module handles the critical startup phase of the cyber incidents dashboard:
pre-computing all visualization data structures for optimal runtime performance.

Instead of querying the database and generating visualizations on-demand for each
user interaction, this module pre-computes all possible views at startup. This includes:

1. **Base Map View**: Global map with incident counts for all countries
2. **Per-Country Views**: For each country in the dataset:
   - Arc data (attack flow lines showing connections to/from the country)
   - Inspector card content (summary statistics and incident details)
   - SVG representation of the country's geometry
   - Country metadata (name, ISO code)

Two incident types are pre-computed for each country:
- **Attacker View**: Perspective showing attacks originating from each country
  (answering "which countries did this country attack?")
- **Receiver View**: Perspective showing attacks targeting each country
  (answering "which countries attacked this country?")

The pre-computed cache is stored in memory during app execution and persisted to
`app_cache.json` for debugging/inspection purposes.

Performance Impact:
- Eliminates database queries during interactive map operations
- Enables instant response to user clicks (perspective toggles, country selection)
- Scales well regardless of the number of users or concurrent interactions
- Trade-off: Startup time (typically 5-30 seconds depending on data size)

Cache Structure:
```
{
    "attacker": {
        "DEFAULT": { base_geojson, max_incident_count, ... },
        "US": { arc_data, inspector_card_content, svg, ... },
        "CN": { ... },
        ...
    },
    "receiver": {
        "DEFAULT": { ... },
        "US": { ... },
        ...
    }
}
```

Dependencies:
- duckdb: Query engine for incident data
- geopandas: GeoDataFrame for geographic data processing
- pandas/numpy: Data manipulation and sanitization
- tqdm: Progress bar for user feedback during startup
- components: Functions to render SVG, inspector cards, and map data
- data_helpers.db: Database query functions
"""

import json

import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
from tqdm import tqdm

from components.inspector_card import cache_inspector_card_content
from components.map import build_country_shape_svg_data_uri
from data_helpers.db import (
    DYADIC_DATABASE,
    get_incident_info_by_country,
    get_incidents_by_country,
)
from static import AppCacheKeys, ArcInfoCols, GeoJsonKeys, IncidentType


def precompute_app_cache(
    countries_json: dict, dyadic_database: duckdb.DuckDBPyConnection
) -> dict[str, dict[str, dict]]:
    """
    Pre-compute all visualization data structures for the cyber incidents dashboard.

    This function is the core of the application's startup routine. It builds the complete
    APP_CACHE dictionary that powers all interactive features of the dashboard. By
    pre-computing all data at startup, the app can respond instantly to user interactions
    without waiting for database queries.

    High-Level Workflow:
    1. Initialize a two-tier cache structure (by incident_type: "attacker"/"receiver")
    2. For each incident type:
       a. Query the database for global statistics (base map view)
       b. Iterate through all countries in the GeoDataFrame
       c. For each country:
          - Extract ISO Alpha-2 code and country name
          - Generate SVG data URI representing the country's shape
          - Query incident data specific to this country and perspective
          - Transform incident data into arc data (flow visualization format)
          - Generate inspector card HTML content (summary statistics)
          - Store all above data in the cache dictionary
    3. Persist the entire cache to disk (app_cache.json) for inspection/debugging
    4. Return the complete cache dictionary for use by Dash callbacks

    Cache Data Structure Details:

    For the "DEFAULT" country entry (global view):
    {
        "base_geojson_dict": GeoJSON features with all countries and incident counts
        "inspector_card_content": Empty string (no specific country selected)
        "name": "Cybercrime Incident Inspector"
        "svg": URL to application logo SVG
        "max_incident_count": Integer representing the highest incident count across all countries
    }

    For each individual country (ISO code like "US", "CN", "RU"):
    {
        "name": Country name (e.g., "United States")
        "svg": Data URI containing SVG of country's geometric shape
        "arc_data": List of dictionaries representing attack flows
                   Each arc contains: origin_lat, origin_lon, dest_lat, dest_lon, name
                   For attacker view: arcs FROM this country TO targets
                   For receiver view: arcs FROM attackers TO this country
        "inspector_card_content": Pre-rendered HTML showing incident statistics,
                                  attack/target summaries, and incident timeline
    }

    Arc Data Format:
    Arc data is a list of dictionaries where each dictionary represents one attack flow:
    {
        "origin_lat": float,      # Latitude of attack origin
        "origin_lon": float,      # Longitude of attack origin
        "dest_lat": float,        # Latitude of attack destination
        "dest_lon": float,        # Longitude of attack destination
        "name": str or null,      # Name/label of the incident (e.g., attack campaign name)
    }

    All NaN and NA values are converted to Python None (JSON null) for safe serialization.

    Args:
        countries_json (dict): GeoJSON FeatureCollection containing world countries.
                              Expected structure:
                              {
                                  "features": [
                                      {
                                          "properties": {
                                              "iso_a2_eh": "US",
                                              "name": "United States"
                                          },
                                          "geometry": {...}
                                      },
                                      ...
                                  ]
                              }
                              Each feature should have:
                              - properties.iso_a2_eh: ISO Alpha-2 country code
                              - properties.name or admin: Country name
                              - geometry: GeoJSON geometry object

        dyadic_database (duckdb.DuckDBPyConnection): Active DuckDB connection to the
                                                     cyber incidents database.
                                                     Used to query incident data for
                                                     each country and perspective.

    Returns:
        dict[str, dict[str, dict]]: Nested dictionary structure:
            - Level 1 keys: IncidentType.ATTACKER, IncidentType.RECEIVER (incident perspectives)
            - Level 2 keys: "DEFAULT" (global view) or ISO Alpha-2 country codes
            - Level 3: Country/view-specific data (described above)

            Example return structure:
            {
                IncidentType.ATTACKER: {
                    "DEFAULT": {...},
                    "US": {...},
                    "CN": {...}
                },
                IncidentType.RECEIVER: {
                    "DEFAULT": {...},
                    "US": {...},
                    "CN": {...}
                }
            }

    Raises:
        FileNotFoundError: If app_cache.json cannot be written to disk
        ValueError: If countries_json doesn't contain required feature properties
        duckdb.Error: If database queries fail or return unexpected data structure
        KeyError: If expected columns are missing from database query results

    Side Effects:
        - Writes app_cache.json to the current working directory
        - Prints progress messages to stdout using tqdm progress bars
        - Modifies the GeoDataFrame in-place (data transformations)
        - Performs extensive database queries (may take 5-30 seconds depending on data size)

    Performance Characteristics:
        - Time Complexity: O(C * log N) where C = number of countries, N = total incidents
        - Space Complexity: O(C * A) where C = countries, A = average arcs per country
        - Typical runtime: 5-30 seconds for global cyber incident dataset
        - Typical output file size: 2-50 MB depending on incident data volume

    Notes:
        - Countries with invalid or missing ISO codes ("-99" or None) are skipped
        - If a country has no incidents for a given perspective, arc_data is set to empty list
        - SVG generation uses the country's actual geometric shape for visual representation
        - The cache is designed to be memory-resident during app execution (no real-time I/O)
        - Persistence to app_cache.json is primarily for debugging; the app uses in-memory cache
        - Pre-computation assumes the database and countries_json are static for a single session

    Example Usage:
        >>> from static import COUNTRIES_JSON, DYADIC_DATABASE
        >>> cache = precompute_app_cache(COUNTRIES_JSON, DYADIC_DATABASE)
        >>> attack_source_countries = cache[IncidentType.ATTACKER].keys()
        >>> us_attacker_data = cache[IncidentType.ATTACKER]["US"]
        >>> global_max_incidents = cache[IncidentType.ATTACKER]["DEFAULT"]["max_incident_count"]
    """

    # Initialize the two-level cache structure
    # Top level: "attacker" and "receiver" perspectives (the two ways to view the data)
    # Second level: "DEFAULT" (global view) and ISO Alpha-2 codes (country-specific views)
    APP_CACHE: dict[str, dict[str, dict]] = {
        IncidentType.ATTACKER: {},
        IncidentType.RECEIVER: {},
    }

    print("⏳ Pre-computing country cache... This will take a few seconds.")

    # Convert the GeoJSON features to a GeoPandas GeoDataFrame for easier iteration
    # and geometric operations (extracting country shapes, etc.)
    countries_gdf = gpd.GeoDataFrame.from_features(countries_json["features"])
    # Apply your antimeridian fix here if you are using it!

    # Main loop: Process each perspective separately
    # This allows us to cache both "who attacked whom" and "who attacked us" views
    for incident_type in [IncidentType.ATTACKER, IncidentType.RECEIVER]:
        # ============================================================================
        # PHASE 1: Cache the Global Base Map View
        # ============================================================================
        # Query the database for incident counts aggregated by country
        # This creates the base map visualization with all countries colored by incident frequency
        base_geojson = get_incidents_by_country(
            countries_json, dyadic_database, incident_type
        )

        # Convert GeoDataFrame to GeoJSON dict for safe JSON serialization
        # This ensures all data types are JSON-compatible (no numpy types, etc.)
        safe_base_geojson = json.loads(base_geojson.to_json())

        # Store the base map data with metadata about this perspective
        # max_incident_count is used for colorbar scaling (square-root transformation)
        APP_CACHE[incident_type]["DEFAULT"] = {
            AppCacheKeys.BASE_GEOJSON_DICT: safe_base_geojson,  # GeoJSON for all countries
            AppCacheKeys.INSPECTOR_CARD_CONTENT: "",  # Empty for default (no country selected)
            AppCacheKeys.NAME: "Cybercrime Incident Inspector",  # UI label for the app
            AppCacheKeys.SVG: "/assets/eurepoc_logo.svg",  # Application logo SVG
            AppCacheKeys.MAX_INCIDENT_COUNT: int(
                base_geojson["incident_count"].max()
            ),  # For colorbar
        }

        # ============================================================================
        # PHASE 2: Cache Individual Country Views
        # ============================================================================
        # Iterate through every country in the GeoDataFrame
        # tqdm provides a progress bar showing which incident_type and country we're processing
        for _, row in tqdm(
            countries_gdf.iterrows(),
            total=countries_gdf.shape[0],
            desc=f"Caching {incident_type} views",
            unit=" countries",
        ):
            # Extract the ISO Alpha-2 country code from the GeoDataFrame row
            # This is a two-letter code like "US", "CN", "RU", etc.
            # Using the "eh" variant of ISO codes to handle disputed/overseas
            # territories consistently.
            iso = row.get(GeoJsonKeys.ISO_A2_EH)  # ISO alpha-2 code

            # Skip countries with invalid or missing ISO codes
            # "-99" is a common placeholder for disputed/invalid territories
            if not iso or iso == "-99":  # Skip invalid or missing ISOs
                continue
            
            # Handle Australia as special case: it has overseas territories
            # that we do not need to include in the main map view. We will use 
            # the mainland polygon only.
            # This is due to us having to use the "eh" variant of ISO codes for consistency with the EuRepoC dataset.
            if iso == "AU" and row.get(GeoJsonKeys.ADMIN) != "Australia":
                continue

            # Extract the country name from the GeoDataFrame
            # Try primary name field first, fall back to admin 
            # field, then "Unknown"
            country_name = (
                row.get(GeoJsonKeys.NAME)
                or row.get(GeoJsonKeys.ADMIN)
                or "Unknown Country"
            )

            # ========================================================================
            # Step 1: Generate SVG Data URI for Country Shape
            # ========================================================================
            # SVG data URI: embeds the SVG image directly in the card without network request
            # Default to app logo if geometry is invalid or empty
            geom = row.get(GeoJsonKeys.GEOMETRY)
            svg_uri = "/assets/eurepoc_logo.svg"  # Default fallback
            if geom and not geom.is_empty:
                # Generate SVG by converting the country's geographic shape to SVG path
                svg_uri = build_country_shape_svg_data_uri(
                    iso_alpha_2=iso,
                    geometry=geom,
                )

            # ========================================================================
            # Step 2: Query Incident Data for This Country
            # ========================================================================
            # Query the database for all incidents involving this country
            # Results differ by incident_type:
            # - "attacker": incidents where this country is the attack source
            # - "receiver": incidents where this country is the attack target
            single_country_info = get_incident_info_by_country(
                countries_json=countries_json,
                dyadic_database=dyadic_database,
                iso_alpha_2=iso,
                incident_type=incident_type,
            )

            # ========================================================================
            # Step 3: Transform Incident Data into Arc Data (Flow Visualization)
            # ========================================================================
            # If no incidents exist for this country/perspective, use empty list
            if single_country_info is None or single_country_info.empty:
                arc_data = []
            else:
                # Convert the incident data to a DataFrame for easier manipulation
                single_country_info = pd.DataFrame(single_country_info)

                # Select only the columns needed for arc visualization:
                # - origin_lat/origin_lon: Starting point of attack flow
                # - dest_lat/dest_lon: Ending point of attack flow
                # - name: Incident/campaign name for tooltips
                arc_info = single_country_info[
                    [
                        ArcInfoCols.ORIGIN_LAT,
                        ArcInfoCols.ORIGIN_LON,
                        ArcInfoCols.DEST_LAT,
                        ArcInfoCols.DEST_LON,
                        ArcInfoCols.NAME,
                    ]
                ]

                # Sanitize the DataFrame by converting any NaN/NA values to None
                # This is critical for JSON serialization (NaN/NA are not JSON-compatible)
                # Python None becomes JSON null, which is safe and expected
                arc_info = arc_info.replace({np.nan: None, pd.NA: None})

                # Convert the sanitized DataFrame to a list of dictionaries
                # Each dict represents one attack arc with lat/lon coordinates
                arc_data = arc_info.to_dict(orient="records")

            # ========================================================================
            # Step 4: Generate Inspector Card Content (Summary Statistics)
            # ========================================================================
            # Pre-render HTML containing country-specific statistics
            # Includes: attack/target summaries, incident timeline, etc.
            # This is rendered once at cache time, not on every user click (performance!)
            inspector_card_content = cache_inspector_card_content(
                single_country_info=single_country_info, incident_type=incident_type
            )

            # ========================================================================
            # Step 5: Store All Country-Specific Data in Cache
            # ========================================================================
            # Save the complete set of pre-computed data for this country and perspective
            # This data will be retrieved instantly when the user clicks on this country
            APP_CACHE[incident_type][iso] = {
                AppCacheKeys.NAME: country_name,  # Human-readable country name
                AppCacheKeys.SVG: svg_uri,  # SVG of country shape
                AppCacheKeys.ARC_DATA: arc_data,  # Attack flow visualization data
                AppCacheKeys.INSPECTOR_CARD_CONTENT: inspector_card_content,  # Summary HTML content
            }

    # ============================================================================
    # PHASE 3: Persist Cache to Disk
    # ============================================================================
    # Write the entire cache to app_cache.json for inspection/debugging
    # This file is not used at runtime (in-memory cache is used instead)
    # but it's useful for:
    # - Debugging data structure issues
    # - Inspecting what gets cached
    # - Manual testing and analysis
    with open("app_cache.json", "w") as f:
        json.dump(APP_CACHE, f, indent=2)
    print("✅ Pre-computing country cache complete.Cache saved to app_cache.json.")

    # Return the complete cache dictionary for use by the Dash application
    return APP_CACHE


# ============================================================================
# Module Execution: Cache Initialization
# ============================================================================
# When cache.py is run directly (not imported), this section initializes the
# application cache from the static data sources.
#
# This script is typically run during development to pre-compute and inspect
# the cache structure. In production, the cache is initialized by app.py on startup.
#
# Usage:
#   python cache.py
#
# This will generate app_cache.json in the working directory.
if __name__ == "__main__":
    from data_helpers.db import DYADIC_DATABASE
    from static import COUNTRIES_JSON

    precompute_app_cache(COUNTRIES_JSON, DYADIC_DATABASE)
