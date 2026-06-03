import datetime
from gtfs.shared.env_utils import detect_environment, make_secret_getter

secret = make_secret_getter(detect_environment())

# params gerais
INSERT_MODE    = secret("INSERT_MODE")    or "ignore"   # "ignore" | "upsert"
CREATE_SUMMARY = secret("CREATE_SUMMARY") or True
VERBOSE        = False
DESTINATION    = "-*-"
TSTART         = None

# gtfs
GTFS_PREFIX = "metro_"
GTFS_URL    = "https://opendata.porto.digital/dataset/15f22603-a216-492a-ab1c-40b1d8aa2f08/resource/5e2b445d-b85b-4afb-9116-90b24327151c/download/horarios_gtfs_mdp_07_04_2026.zip"

OUTPUT_PATH = "output"

# nome das tabelas
TABLE_STOPS           = f"{GTFS_PREFIX}stops"
TABLE_ROUTES          = f"{GTFS_PREFIX}routes"
TABLE_TRIPS           = f"{GTFS_PREFIX}trips"
TABLE_STOP_TIMES      = f"{GTFS_PREFIX}stop_times"
TABLE_SHAPES          = f"{GTFS_PREFIX}shapes"
TABLE_CALENDAR        = f"{GTFS_PREFIX}calendar"
TABLE_CALENDAR_DATES  = f"{GTFS_PREFIX}calendar_dates"
TABLE_AGENCY          = f"{GTFS_PREFIX}agency"
TABLE_FARE_ATTRIBUTES = f"{GTFS_PREFIX}fare_attributes"
TABLE_FARE_RULES      = f"{GTFS_PREFIX}fare_rules"
TABLE_STOPS_GEOJSON   = f"{GTFS_PREFIX}stops_geojson"
TABLE_ROUTES_GEOJSON  = f"{GTFS_PREFIX}routes_geojson"

# email
tmp_send      = secret("EMAIL_SEND")      or "False"
tmp_addresses = secret("EMAIL_ADDRESSES") or ""
EMAIL = {
    "send":      tmp_send.lower() == "true",
    "addresses": [a.strip() for a in tmp_addresses.split(",") if a.strip()],
}