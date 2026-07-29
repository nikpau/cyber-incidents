"""Domain definitions, dataset schemas, and typing protocols."""

from enum import StrEnum
from typing import Any, TypedDict

# ==============================================================================
# Global UI / Visualization Constants
# ==============================================================================

# Scale factor for colorbar ticks (square root transform for uneven incident distributions)
COLORBAR_SCALE_FACTOR: float = 0.5


# ==============================================================================
# Domain Enums & Column Definitions
# ==============================================================================

class IncidentType(StrEnum):
    ATTACKER = "attacker"
    RECEIVER = "receiver"


class DyadicCols(StrEnum):
    """Single source of truth for column names in the dyadic dataset."""
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
    """Common key strings used in geographical GeoJSON features."""
    FEATURES = "features"
    GEOMETRY = "geometry"
    PROPERTIES = "properties"
    TYPE = "type"
    COORDINATES = "coordinates"

    # Properties specific to country feature objects
    ISO_A2_EH = "iso_a2_eh"
    NAME = "name"
    ADMIN = "admin"
    SOVEREIGNT = "sovereignt"
    FORMAL_EN = "formal_en"


class ArcInfoCols(StrEnum):
    """Keys used in attack vector visualization entries."""
    ORIGIN_LAT = "origin_lat"
    ORIGIN_LON = "origin_lon"
    DEST_LAT = "dest_lat"
    DEST_LON = "dest_lon"
    NAME = "name"


# ==============================================================================
# Application Cache Specifications
# ==============================================================================

class AppCacheKeys(StrEnum):
    """Internal key string constants used across APP_CACHE mappings."""
    DEFAULT = "DEFAULT"
    BASE_GEOJSON_DICT = "base_geojson_dict"
    NAME = "name"
    SVG = "svg"
    MAX_INCIDENT_COUNT = "max_incident_count"
    INSPECTOR_CARD_CONTENT = "inspector_card_content"
    ARC_DATA = "arc_data"


class AppCacheDefaultEntry(TypedDict):
    """Typed shape for the DEFAULT cache entry used by the global map view."""
    base_geojson_dict: dict[str, Any]
    inspector_card_content: str
    name: str
    svg: str
    max_incident_count: int


class AppCacheCountryEntry(TypedDict):
    """Typed shape for per-country cache entries populated for each perspective."""
    name: str
    svg: str
    arc_data: list[dict[str, Any]]
    inspector_card_content: Any


AppCacheEntry = AppCacheDefaultEntry | AppCacheCountryEntry
AppCachePerspective = dict[str, AppCacheEntry]
AppCache = dict[IncidentType, AppCachePerspective]