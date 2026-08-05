"""
Application cache precomputation module.

This module builds the in-memory cache used by the dashboard. At startup it queries
DuckDB, derives per-country map and inspector-card data for both attacker and receiver
views, and stores the result for fast runtime access. When debug mode is enabled, the
same cache is also written to app_cache.json for inspection.
"""

import atexit
import json
from pathlib import Path

import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
from tqdm import tqdm

from components.inspector_card import cache_inspector_card_content
from components.map import build_country_shape_svg_data_uri
from data_helpers.antimeridian import fix_antimeridian_tearing
from data_helpers.db import (
    get_incident_info_by_country,
    get_incidents_by_country,
)
from data_helpers.schema import (
    AppCache,
    AppCacheKeys,
    ArcInfoCols,
    GeoJsonKeys,
    IncidentType,
)

DYADIC_DATABASE_FILE = Path(__file__).parent / "incidents.duckdb"
DYADIC_SOURCE_CSV = Path(__file__).parent / "data" / "eurepoc_dyadic_dataset_0_1.csv"
COUNTRIES_GEOJSON_FILE = (
    Path(__file__).parent / "data" / "map_data" / "countries.geo.json"
)

with open(COUNTRIES_GEOJSON_FILE, "r") as f:
    COUNTRIES_JSON = json.loads(fix_antimeridian_tearing(gpd.read_file(f)).to_json())


def precompute_app_cache(
    countries_json: dict,
    dyadic_database_file: Path,
    debug: bool = False,
) -> AppCache | None:
    """
    Pre-compute the cache used by the dashboard.

    The function builds the full in-memory cache for both incident perspectives,
    optionally writes it to app_cache.json for debugging, and returns the cache.

    Args:
        countries_json: GeoJSON feature collection containing country geometries.
        dyadic_database_file: Path to the DuckDB file with incident data.
        debug: When True, write the cache to app_cache.json before returning it.

    Returns:
        The populated cache dictionary, or None if the caller chooses to stop on debug output.
        In the current implementation, the cache is returned even in debug mode.
    """
    dbconn = duckdb.connect(database=str(dyadic_database_file), read_only=True)

    @atexit.register
    def close_database_connection():
        """Close the DuckDB connection when the program exits."""
        if dbconn is not None:
            dbconn.close()
            print("✅ DuckDB connection closed.")

    # Initialize the two-level cache structure
    # Top level: "attacker" and "receiver" perspectives (the two ways to view the data)
    # Second level: "DEFAULT" (global view) and ISO Alpha-2 codes (country-specific views)
    APP_CACHE: AppCache = {
        IncidentType.ATTACKER: {},
        IncidentType.RECEIVER: {},
    }
    ARC_CACHE: dict[str, dict[str,list]] = {
        IncidentType.ATTACKER: {},
        IncidentType.RECEIVER: {},
    }  # For storing arc data per country/perspective

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
        base_geojson = get_incidents_by_country(countries_json, dbconn, incident_type)

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
                dyadic_database=dbconn,
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
                single_country_info=single_country_info,
                incident_type=incident_type,
                dyadic_database=dbconn,
            )

            # ========================================================================
            # Step 5: Store All Country-Specific Data in Cache
            # ========================================================================
            # Save the complete set of pre-computed data for this country and perspective
            # This data will be retrieved instantly when the user clicks on this country
            APP_CACHE[incident_type][iso] = {
                AppCacheKeys.NAME: country_name,  # Human-readable country name
                AppCacheKeys.SVG: svg_uri,  # SVG of country shape
                AppCacheKeys.INSPECTOR_CARD_CONTENT: inspector_card_content,  # Summary HTML content
            }
            # Store arc data separately for clientside callbacks
            ARC_CACHE[incident_type][iso] = arc_data
            
    # Add Arc data to the main cache for both perspectives
    APP_CACHE[AppCacheKeys.ARC_DATA] = ARC_CACHE

    # ============================================================================
    # PHASE 3: Persist Cache to Disk
    # ============================================================================
    # Write the entire cache to app_cache.json for inspection/debugging
    # This file is not used at runtime (in-memory cache is used instead)
    # but it's useful for:
    # - Debugging data structure issues
    # - Inspecting what gets cached
    # - Manual testing and analysis
    if debug:
        with open("app_cache.json", "w") as f:
            json.dump(APP_CACHE, f, indent=2)
        print("✅ Pre-computing country cache complete. Cache saved to app_cache.json.")

    # Return the complete cache dictionary for use by the Dash application
    print("✅ Pre-computing country cache complete")
    return APP_CACHE
