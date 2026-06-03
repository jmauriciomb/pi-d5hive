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
GTFS_PREFIX = "stcp_"
GTFS_URL    = "https://opendata.porto.digital/dataset/5275c986-592c-43f5-8f87-aabbd4e4f3a4/resource/fdb8afe1-ee48-4b10-97a7-9ca8e52e099c/download/gtfs_feed.zip"

OUTPUT_PATH = "output"

# nome das tabelas
TABLE_STOPS          = f"{GTFS_PREFIX}stops"
TABLE_ROUTES         = f"{GTFS_PREFIX}routes"
TABLE_TRIPS          = f"{GTFS_PREFIX}trips"
TABLE_STOP_TIMES     = f"{GTFS_PREFIX}stop_times"
TABLE_SHAPES         = f"{GTFS_PREFIX}shapes"
TABLE_CALENDAR_DATES = f"{GTFS_PREFIX}calendar_dates"
TABLE_AGENCY         = f"{GTFS_PREFIX}agency"
TABLE_FEED_INFO      = f"{GTFS_PREFIX}feed_info"
TABLE_STOPS_GEOJSON  = f"{GTFS_PREFIX}stops_geojson"
TABLE_ROUTES_GEOJSON = f"{GTFS_PREFIX}routes_geojson"

# email
tmp_send      = secret("EMAIL_SEND")      or "False"
tmp_addresses = secret("EMAIL_ADDRESSES") or ""
EMAIL = {
    "send":      tmp_send.lower() == "true",
    "addresses": [a.strip() for a in tmp_addresses.split(",") if a.strip()],
}