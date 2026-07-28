from pathlib import Path
from typing import Literal

import duckdb
import geopandas as gpd
import matplotlib.colors as mcolors
import pandas as pd

import static

# Single source of truth for map and colorbar palette.
#COLORMAP_HEX_STOPS = ["#386641", "#6a994e", "#f2e8cf", "#7c2729", "#920000"]
COLORMAP_HEX_STOPS = ["#335c67", "#fff3b0", "#e09f3e", "#9e2a2b", "#540b0e"]
#COLORMAP_HEX_STOPS = ["#386641", "#6a994e", "#f2e8cf", "#7c2729", "#920000"]
#COLORMAP_HEX_STOPS = ["#386641", "#6a994e", "#f2e8cf", "#7c2729", "#920000"]
COLORMAP = mcolors.LinearSegmentedColormap.from_list(
    "cyber_incidents_copper",
    COLORMAP_HEX_STOPS,
)

# DB connection in read-only mode to prevent concurrency errors when 
# multiple worker processes access the app simultaneously.
DYADIC_DATABASE = duckdb.connect(database="incidents.duckdb", read_only=True)

def get_colorbar_gradient_css() -> str:
    """Return a CSS linear-gradient string based on the shared colormap stops."""
    if len(COLORMAP_HEX_STOPS) == 1:
        return COLORMAP_HEX_STOPS[0]

    denom = len(COLORMAP_HEX_STOPS) - 1
    color_stops = [
        f"{color} {int((idx / denom) * 100)}%"
        for idx, color in enumerate(COLORMAP_HEX_STOPS)
    ]
    return f"linear-gradient(to right, {', '.join(color_stops)})"

def one_off_init_dyadic_source_csv_to_duckdb(dyadic_source_csv: Path) -> None:
    """
    One-off function to transfer the dyadic source CSV file into a DuckDB database. 
    This function creates a DuckDB database file named 'incidents.duckdb' and 
    populates it with the data from the specified CSV file.
    """
    # Check if the DuckDB database file already exists
    db_path = Path("incidents.duckdb")
    if db_path.exists():
        print(f"DuckDB database '{db_path}' already exists. Skipping initialization.")
        return
    
    dyadic_database = duckdb.connect(database="incidents.duckdb", read_only=False)
    dyadic_database.execute(
        "CREATE TABLE dyadic_source AS SELECT * FROM "
        f"read_csv_auto('{dyadic_source_csv}')"
    )
    dyadic_database.close()

def get_incidents_by_country(
    countries_json: dict,
    dyadic_database: duckdb.DuckDBPyConnection, 
    incident_type: str = Literal["attacker", "receiver"]
    ) -> gpd.GeoDataFrame:
    """
    Get the number of incidents by country from the dyadic database and 
    return a dictionary with country codes and incident counts, based on 
    incident_type (either "attacker" or "receiver").
    """
    # Load the GeoJSON file to get country codes
    geojson_data = countries_json
        
    # Extract ISO 3166-1 alpha-2 country codes from the GeoJSON data
    country_codes = [
        feature["properties"]["iso_a2_eh"] for feature in geojson_data["features"]
    ]
    
    # Query the dyadic database to get incident counts by country
    grouping_var = (
        "initiator_alpha_2" if incident_type == "attacker" 
        else "receiver_country_alpha_2_code"
    )
    query = f"""
        SELECT {grouping_var} AS country_code, COUNT(*) AS incident_count
        FROM dyadic_source
        WHERE {grouping_var} IS NOT NULL
        GROUP BY {grouping_var}
    """
    result = dyadic_database.execute(query).fetchdf()
    
    # Create a dictionary with country codes and incident counts
    incidents_by_country = {code: 0 for code in country_codes if len(code) == 2}  # Initialize with zero counts for all countries
    for _, row in result.iterrows():
        if row["country_code"] in incidents_by_country:
            incidents_by_country[row["country_code"]] = row["incident_count"]
    
    # Inject the incident counts into the GeoJSON data
    for feature in geojson_data["features"]:
        country_code = feature["properties"].get("iso_a2_eh")
        feature["properties"]["incident_count"] = incidents_by_country.get(country_code, 0)
        feature["properties"]["fill_color"] = get_color_map(
            count=incidents_by_country.get(country_code, 0), 
            max_count=max(incidents_by_country.values()) if incidents_by_country else 1
        )

    # Convert the GeoJSON data to a GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
    return gdf

def get_incident_info_by_country(
    countries_json: dict,
    dyadic_database: duckdb.DuckDBPyConnection, 
    iso_alpha_2: str,
    incident_type: str = Literal["attacker", "receiver"]
    ) -> pd.DataFrame:
    """
    Get the information of incidents for a specific country from the dyadic database.
    
    Args:
        countries_json (dict): The GeoJSON data for countries.
        dyadic_database (duckdb.DuckDBPyConnection): The DuckDB connection object.
        iso_alpha_2 (str): The ISO 3166-1 alpha-2 country code for which to retrieve incident arcs.
    
    Returns:
        pd.DataFrame: A DataFrame containing the arcs of incidents for the specified country.
    """
    
    # Some countries have parts of their territory scatterd across the globe, 
    # so we need to exclude them from the arcs to avoid the centroid being 
    # in the middle of the ocean.
    empire_exceptions = [
        "FR",  # France (overseas territories)
    ]
    
    
    iso_alpha_2 = iso_alpha_2.upper()
    grouping_var = (
        "initiator_alpha_2" if incident_type == "attacker" 
        else "receiver_country_alpha_2_code"
    )
    
    # Exclude the "added_to_db" and "updated_at" columns from the query 
    # to avoid serialization issues with PyDeck.
    query = f"""
        SELECT *
        EXCLUDE (added_to_db, updated_at)
        FROM dyadic_source
        WHERE {grouping_var} = '{iso_alpha_2}'

    """
    result = dyadic_database.execute(query).fetchdf()
    
    countries_gdf = gpd.GeoDataFrame.from_features(countries_json["features"])
    country_geom = countries_gdf.set_index("iso_a2_eh")["geometry"]

    if iso_alpha_2 in empire_exceptions:
        # Extract the mainland (aka the largest polygon) 
        # to prevent global bounding boxes
        country_geom = country_geom.apply(
            lambda g: max(g.geoms, key=lambda p: p.area) if g.geom_type == 'MultiPolygon' else g)

    centroid = country_geom.centroid
    coords_lookup = pd.DataFrame({"lon": centroid.x, "lat": centroid.y}, index=centroid.index)
    
    # Add "origin_lat", "origin_lon", "dest_lat", "dest_lon" columns to the 
    # dataset results for arcs based on the initiator and receiver country 
    # codes' centroids from the countries GeoJSON data
    result = result.merge(
        coords_lookup, left_on="initiator_alpha_2", right_index=True, how="left"
    ).rename(columns={"lon": "origin_lon", "lat": "origin_lat"})

    result = result.merge(
        coords_lookup, left_on="receiver_country_alpha_2_code", right_index=True, how="left"
    ).rename(columns={"lon": "dest_lon", "lat": "dest_lat"})

    
    # Drop all rows where the "receiver_country" is "Not available"
    result = result[result["receiver_country"] != "Not available"]
    
    # Drop all rows where the "initiator_alpha_2" or "receiver_country_alpha_2_code" is not a valid ISO alpha-2 code
    result = result[result["initiator_alpha_2"].str.len() == 2]
    result = result[result["receiver_country_alpha_2_code"].str.len() == 2]

    return result

def get_attacker_and_receiver_rankings(
    dyadic_database: duckdb.DuckDBPyConnection,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Get the rankings of attackers and receivers based on the number of incidents.
    
    Args:
        dyadic_database (duckdb.DuckDBPyConnection): The DuckDB connection object.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: Two DataFrames containing the attacker and receiver rankings.
    """
    
    # Get all unique incidents based on the incident_id to avoid double counting
    unique_incidents_query = """
        SELECT DISTINCT incident_id, initiator_alpha_2, receiver_country_alpha_2_code
        FROM dyadic_source
    """
    unique_incidents = dyadic_database.execute(unique_incidents_query).fetchdf()
    
    # Filter initiator_alpha_2 and receiver_country_alpha_2_code to only include valid ISO alpha-2 codes
    unique_incidents = unique_incidents[
        unique_incidents["initiator_alpha_2"].str.len() == 2
    ]
    unique_incidents = unique_incidents[
        unique_incidents["receiver_country_alpha_2_code"].str.len() == 2
    ]
    
    # Get attacker rankings and rank number based on the number of incidents
    attacker_rankings = (
        unique_incidents.groupby("initiator_alpha_2")
        .size()
        .reset_index(name="incident_count")
        .sort_values(by="incident_count", ascending=False)
    )
    attacker_rankings["rank"] = attacker_rankings["incident_count"].rank(
        method="min", ascending=False
    ).astype(int)
    # Get receiver rankings
    receiver_rankings = (
        unique_incidents.groupby("receiver_country_alpha_2_code")
        .size()
        .reset_index(name="incident_count")
        .sort_values(by="incident_count", ascending=False)
    )
    receiver_rankings["rank"] = receiver_rankings["incident_count"].rank(
        method="min", ascending=False
    ).astype(int)

    return attacker_rankings, receiver_rankings

ATTACKER_RANKING, RECEIVER_RANKING = get_attacker_and_receiver_rankings(
    dyadic_database=DYADIC_DATABASE
)

def get_color_map(count: int, max_count: int) -> list:
    """
    Get a color map based on the specified name, count, and max_count.
    This function returns a list of RGBA values corresponding to the color map.
    """
    cmap = COLORMAP
    normalized_count = count / max_count if max_count > 0 else 0
    # Apply a square root transformation to the 
    # normalized count for better color distribution,
    # as we have many countries with low incident counts and a 
    # few with very high counts.
    rgba = cmap(normalized_count ** (static.COLORBAR_SCALE_FACTOR))
    # Convert to RGBA with alpha channel
    return [int(255 * c) for c in rgba[:4]]