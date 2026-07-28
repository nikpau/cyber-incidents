import json
from enum import StrEnum
from pathlib import Path

import geopandas as gpd

from data_helpers.antimeridian import fix_antimeridian_tearing

OXANIUM_FONT_URL = (
    "https://fonts.googleapis.com/css2?family=Oxanium:wght@200..800&display=swap"
)


# GLOBALS
COUNTRIES_FILE = Path(__file__).parent / "data" / "map_data" / "countries.geo.json"
DYADIC_SOURCE_CSV = Path(__file__).parent / "data" / "eurepoc_dyadic_dataset_0_1.csv"

# Colorbar square root scale factor for colorbar ticks.
# Due to the fact that the incident counts are distributed relatively
# unevenly, we apply a square root scale to the colorbar ticks to make the
# colorbar more visually informative.
COLORBAR_SCALE_FACTOR = 1 / 2

class IncidentType(StrEnum):
    ATTACKER = "attacker"
    RECEIVER = "receiver"
    
class DyadicCols(StrEnum):
    """
    All Columns in the dyadic dataset as single 
    source of truth for column names.
    """
    DYAD_ID = "dyad_id"
    INITIATOR_COUNTRY = "initiator_country"
    INITIATOR_ALPHA_2 = "initiator_alpha_2"
    RECEIVER_COUNTRY = "receiver_country"
    RECEIVER_COUNTRY_ALPHA_2_CODE = "receiver_country_alpha_2_code"
    INCIDENT_ID = "incident_id"
    NAME = "name"
    DESCRIPTION = "description"
    START_DATE = "start_date"
    END_DATE = "end_date"
    SOURCE_DISCLOSURE = "source_disclosure"
    OPERATION_TYPE = "operation_type"
    IMPACT_INDICATOR_SCORE = "impact_indicator_score"
    IMPACT_INDICATOR_LABEL = "impact_indicator_label"
    UNWEIGHTED_INTENSITY = "unweighted_intensity"
    WEIGHTED_INTENSITY = "weighted_intensity"
    NUMBER_ATTRIBUTIONS = "number_attributions"
    NUMBER_POLITICAL_RESPONSES = "number_political_responses"
    NUMBER_LEGAL_RESPONSES = "number_legal_responses"
    CASUALTIES = "casualties"
    ATTRIBUTION_ID = "attribution_id"
    INITIATOR_NAME = "initiator_name"
    INITIATOR_CATEGORY = "initiator_category"
    INITIATOR_SUBCATEGORY = "initiator_subcategory"
    RECEIVER_ID = "receiver_id"
    RECEIVER_NAME = "receiver_name"
    RECEIVER_CATEGORY = "receiver_category"
    RECEIVER_SUBCATEGORY = "receiver_subcategory"
    RECEIVER_REGIONS = "receiver_regions"
    OFFLINE_CONFLICT_ISSUE = "offline_conflict_issue"
    OFFLINE_CONFLICT_NAME = "offline_conflict_name"
    OFFLINE_CONFLICT_INTENSITY = "offline_conflict_intensity"
    OFFLINE_CONFLICT_INTENSITY_SUBCODE = "offline_conflict_intensity_subcode"
    CYBER_CONFLICT_ISSUE = "cyber_conflict_issue"
    PHYSICAL_EFFECTS_SPATIAL = "physical_effects_spatial"
    PHYSICAL_EFFECTS_TEMPORAL = "physical_effects_temporal"
    TARGET_MULTIPLIER = "target_multiplier"
    FUNCTIONAL_IMPACT = "functional_impact"
    INTELLIGENCE_IMPACT = "intelligence_impact"
    ECONOMIC_IMPACT = "economic_impact"
    ECONOMIC_IMPACT_VALUE = "economic_impact_value"
    ECONOMIC_IMPACT_CURRENCY = "economic_impact_currency"
    AFFECTED_ENTITIES = "affected_entities"
    AFFECTED_ENTITIES_VALUE = "affected_entities_value"
    AFFECTED_EU_COUNTRIES = "affected_eu_countries"
    AFFECTED_EU_COUNTRIES_VALUE = "affected_eu_countries_value"
    AFFECTED_THIRD_COUNTRIES = "affected_third_countries"
    AFFECTED_THIRD_COUNTRIES_VALUE = "affected_third_countries_value"
    DATA_THEFT = "Data theft"
    DATA_THEFT_AND_DOXING = "Data theft & Doxing"
    DISRUPTION = "Disruption"
    HIJACKING_WITH_MISUSE = "Hijacking with Misuse"
    HIJACKING_WITHOUT_MISUSE = "Hijacking without Misuse"
    NOT_AVAILABLE = "Not available"
    RANSOMWARE = "Ransomware"
    ADDED_TO_DB = "added_to_db"
    UPDATED_AT = "updated_at"
    
class GeoJsonKeys(StrEnum):
    """
    Common keys used in GeoJSON files for countries and other geographic data.
    """
    FEATURES = "features"
    GEOMETRY = "geometry"
    PROPERTIES = "properties"
    TYPE = "type"
    COORDINATES = "coordinates"
    
    # Special keys for the countries GeoJSON
    ISO_A2_EH = "iso_a2_eh"
    NAME = "name"
    ADMIN = "admin"
    SOVEREIGNT = "sovereignt"
    FORMAL_EN = "formal_en"
    
class AppCacheKeys(StrEnum):
    """
    Keys used in the APP_CACHE dictionary for storing precomputed data.
    """
    DEFAULT = "DEFAULT"
    BASE_GEOJSON_DICT = "base_geojson_dict"
    NAME = "name"
    SVG = "svg"
    MAX_INCIDENT_COUNT = "max_incident_count"
    INSPECTOR_CARD_CONTENT = "inspector_card_content"
    ARC_DATA = "arc_data"
    
class ArcInfoCols(StrEnum):
    """
    Columns used in the arc data for visualizing attack flows on the map.
    """
    ORIGIN_LAT = "origin_lat"
    ORIGIN_LON = "origin_lon"
    DEST_LAT = "dest_lat"
    DEST_LON = "dest_lon"
    NAME = "name"

with open(COUNTRIES_FILE, "r") as f:
    COUNTRIES_JSON = json.loads(fix_antimeridian_tearing(gpd.read_file(f)).to_json())

if Path("app_cache.json").exists():
    with open("app_cache.json", "r") as f:
        APP_CACHE = json.load(f)
else:
    APP_CACHE = {}
