import json
from enum import Enum
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

class IncidentType(str, Enum):
    ATTACKER = "attacker"
    RECEIVER = "receiver"

with open(COUNTRIES_FILE, "r") as f:
    COUNTRIES_JSON = json.loads(fix_antimeridian_tearing(gpd.read_file(f)).to_json())

if Path("app_cache.json").exists():
    with open("app_cache.json", "r") as f:
        APP_CACHE = json.load(f)
else:
    APP_CACHE = {}
