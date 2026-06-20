import math
import shutil
import zipfile
import requests
import pandas as pd
import json
import os
import clts_pcp as clts  # type: ignore


# helpers
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))

# format time
def fmt_time(t):
    h, m, s = t.split(":")
    return f"{int(h):02d}:{m}"

# classify each service_id into a day type
def _build_service_type_calendar(calendar: pd.DataFrame) -> pd.DataFrame:
    """Metro-style: calendar.txt with boolean day columns."""
    def classify(row):
        if any(row[d] == 1 for d in ["monday","tuesday","wednesday","thursday","friday"]):
            return "weekday"
        elif row["saturday"] == 1:
            return "saturday"
        elif row["sunday"] == 1:
            return "sunday_holidays"
        else:
            return "other"
    st = calendar[["service_id"]].copy()
    st["day_type"] = calendar.apply(classify, axis=1)
    return st

def _build_service_type_calendar_dates(calendar_dates: pd.DataFrame) -> pd.DataFrame:
    """STCP-style: calendar_dates.txt with plain-text service_id."""
    def classify(sid: str) -> str:
        s = sid.upper()
        if "UTEIS" in s or "ÚTEIS" in s:
            return "weekday"
        elif "SABADO" in s or "SÁBADO" in s:
            return "saturday"
        elif "DOMINGO" in s or "FERIADO" in s:
            return "sunday_holidays"
        else:
            return "other"
    st = calendar_dates[["service_id"]].drop_duplicates().copy()
    st["day_type"] = st["service_id"].apply(classify)
    return st

def build_schedule(df):
    sched = {}
    for _, row in df.iterrows():
        line     = row["route_short_name"]
        day      = row["day_type"]
        headsign = row["trip_headsign"]
        if line not in sched:
            sched[line] = {}
        if day not in sched[line]:
            sched[line][day] = {}
        sched[line][day][headsign] = row["times"]
    return sched


def save_geojson(geojson: dict, filename: str, config) -> None:
    """Guarda um GeoJSON em config.OUTPUT_PATH com o prefixo do operador."""
    out_path = os.path.join(config.OUTPUT_PATH, f"{config.GTFS_PREFIX}{filename}")
    os.makedirs(config.OUTPUT_PATH, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=None)
    print(f"{filename} guardado em: {out_path}")

# mapping: config attribute -> (dict key, filename)
_TABLE_FILE_MAP = [
    ("TABLE_STOPS",           "stops",           "stops.txt"),
    ("TABLE_ROUTES",          "routes",          "routes.txt"),
    ("TABLE_TRIPS",           "trips",           "trips.txt"),
    ("TABLE_STOP_TIMES",      "stop_times",      "stop_times.txt"),
    ("TABLE_SHAPES",          "shapes",          "shapes.txt"),
    ("TABLE_CALENDAR",        "calendar",        "calendar.txt"),
    ("TABLE_CALENDAR_DATES",  "calendar_dates",  "calendar_dates.txt"),
    ("TABLE_AGENCY",          "agency",          "agency.txt"),
    ("TABLE_FARE_ATTRIBUTES", "fare_attributes", "fare_attributes.txt"),
    ("TABLE_FARE_RULES",      "fare_rules",      "fare_rules.txt"),
    ("TABLE_FEED_INFO",       "feed_info",       "feed_info.txt"),
]


# download e extração

def download_and_extract(datapath: str, config) -> str:
    """
    Descarrega o ZIP GTFS e extrai para gtfs_data/.
    Devolve o caminho para a pasta com os ficheiros .txt.
    """
    import os
    zip_path  = os.path.join(datapath, f"{config.GTFS_PREFIX}gtfs.zip")
    gtfs_path = os.path.join(datapath, "gtfs_data")

    if os.path.exists(gtfs_path):
        shutil.rmtree(gtfs_path)
    os.makedirs(gtfs_path)

    response = requests.get(config.GTFS_URL, stream=True)
    response.raise_for_status()

    ct = response.headers.get("Content-Type", "")
    if "zip" not in ct and "octet-stream" not in ct:
        print(f"Unexpected Content-Type: {ct}")

    with open(zip_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"ZIP guardado em: {zip_path}")
    clts.elapt[f"Download GTFS {config.GTFS_PREFIX}"] = clts.deltat(config.TSTART)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(gtfs_path)

    import os as _os
    first = _os.listdir(gtfs_path)[0]
    if _os.path.isdir(_os.path.join(gtfs_path, first)):
        gtfs_folder = _os.path.join(gtfs_path, first)
    else:
        gtfs_folder = gtfs_path

    print(f"ZIP extraído para: {gtfs_folder}")
    clts.elapt["Extração GTFS concluída"] = clts.deltat(config.TSTART)

    return gtfs_folder


# carregamento dos CSVs

def load_gtfs_tables(gtfs_folder: str, config) -> dict[str, pd.DataFrame]:
    """Carrega os ficheiros GTFS presentes em config e devolve um dict name -> DataFrame."""
    import os
    tables = {}
    for attr, key, filename in _TABLE_FILE_MAP:
        if not hasattr(config, attr):
            continue
        path = os.path.join(gtfs_folder, filename)
        if not os.path.exists(path):
            print(f"  Ficheiro não encontrado (ignorado): {filename}")
            continue
        tables[key] = pd.read_csv(path)
        
        # fix: agency_id vem vazio (NaN)
        if key == "agency" and "agency_id" in tables[key].columns:
            tables[key]["agency_id"] = (
                tables[key]["agency_id"].fillna(config.GTFS_PREFIX).astype(str)
            )
            
        if config.VERBOSE:
            print(f"  {key}: {len(tables[key])} linhas")

    print("\nDataset sizes:")
    for name, df in tables.items():
        print(f"  {name}: {len(df)}")

    clts.elapt["Tabelas GTFS carregadas"] = clts.deltat(config.TSTART)
    return tables


# Construção dos GeoJSONs
def build_stops_geojson(stops: pd.DataFrame, stop_times: pd.DataFrame,
                        trips: pd.DataFrame, routes: pd.DataFrame,
                        service_type: pd.DataFrame, config) -> dict:
    """ 
        FeatureCollection de Points: uma feature por paragem.
        service_type: DataFrame com colunas [service_id, day_type] — construido pelo operador.
    """

    # full join: stop_times - trips - routes - day_type
    # goal: one row per (stop, line, day_type, arrival_time)
    st_full = (
        stop_times[["trip_id", "stop_id", "arrival_time"]]
        .merge(trips[["trip_id", "route_id", "service_id", "trip_headsign"]], on="trip_id")
        .merge(routes[["route_id", "route_short_name"]], on="route_id")
        .merge(service_type[["service_id", "day_type"]], on="service_id")
    )

    print(f"st_full: {len(st_full):,} rows")
    print(f"unique day_types: {st_full['day_type'].unique()}")
    
    # per (stop, line, day_type, direction): sorted deduplicated list of arrival times
    # fmt_time normalises "6:13:00" -> "06:13"; set() removes duplicate minutes within same direction, just for safety
    # expected look: (example)
    # stop_id  route_short_name  day_type  trip_headsign      times
    # 5697     B                 weekday   Póvoa de Varzim    ["06:14", "06:34", ...]
    # 5697     B                 weekday   Estádio do Dragão  ["06:20", "06:40", ...]
    schedule_raw = (
        st_full.groupby(["stop_id", "route_short_name", "day_type", "trip_headsign"])["arrival_time"]
        .apply(lambda x: sorted(set(fmt_time(t) for t in x.dropna())))
        .reset_index()
        .rename(columns={"arrival_time": "times"})
    )
    
    schedule_per_stop = (
        schedule_raw.groupby("stop_id", group_keys=False)
        .apply(build_schedule)
        .reset_index()
        .rename(columns={0: "schedule"})
    )

    # attach schedule to stop metadata
    stops_geo = stops.merge(schedule_per_stop, on="stop_id", how="left")

    # build GeoJSON
    # geometry: Point [lon, lat]
    # properties: stop metadata + schedule dict
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["stop_lon"], row["stop_lat"]]},
                "properties": {
                    "stop_id":   row["stop_id"],
                    "stop_name": row.get("stop_name", ""),
                    "stop_lat":  row["stop_lat"],
                    "stop_lon":  row["stop_lon"],
                    "schedule":  row["schedule"] if isinstance(row["schedule"], dict) else {}
                }
            }
            for _, row in stops_geo.iterrows()
        ]
    }
    
    save_geojson(geojson, "stops.geojson", config)

    print(f"stops_geojson -> {len(geojson['features'])} features")
    clts.elapt["Built stops_geojson"] = clts.deltat(config.TSTART)
    return geojson


def build_routes_geojson(shapes: pd.DataFrame, trips: pd.DataFrame,
                         routes: pd.DataFrame, config) -> dict:
    """FeatureCollection de LineStrings: uma feature por rota."""

    route_shapes = (
        trips[["route_id", "shape_id"]].drop_duplicates()
        .sort_values("shape_id")
        .groupby("route_id", as_index=False).first()
        .merge(routes[["route_id", "route_short_name"]], on="route_id")
    )
    shapes_sorted = shapes.sort_values(["shape_id", "shape_pt_sequence"])

    features = []
    for _, rs in route_shapes.iterrows():
        pts = shapes_sorted[shapes_sorted["shape_id"] == rs["shape_id"]]
        if pts.empty:
            continue
        coords = [[r["shape_pt_lon"], r["shape_pt_lat"]] for _, r in pts.iterrows()]
        length_km = sum(
            haversine_km(coords[i][1], coords[i][0],
                         coords[i + 1][1], coords[i + 1][0])
            for i in range(len(coords) - 1)
        )
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "route_id":         rs["route_id"],
                "route_short_name": rs["route_short_name"],
                "shape_id":         rs["shape_id"],
                "length_km":        round(length_km, 3),
            },
        })

    geojson = {"type": "FeatureCollection", "features": features}
    
    save_geojson(geojson, "routes.geojson", config)
    
    print(f"routes_geojson -> {len(features)} features")
    clts.elapt["Built routes_geojson"] = clts.deltat(config.TSTART)
    return geojson


# Entry point chamado pelo pipeline.py
def parse_all(datapath: str, config) -> tuple[dict, dict, dict[str, pd.DataFrame]]:
    """
    Descarrega, extrai e processa os dados GTFS.
    Devolve (stops_geojson, routes_geojson, gtfs_tables).
    """
    gtfs_folder = download_and_extract(datapath, config)
    tables      = load_gtfs_tables(gtfs_folder, config)

    # build service_type: use calendar.txt if available, else calendar_dates.txt
    if "calendar" in tables:
        service_type = _build_service_type_calendar(tables["calendar"])
    elif "calendar_dates" in tables:
        service_type = _build_service_type_calendar_dates(tables["calendar_dates"])
    else:
        raise ValueError("No calendar data found: neither calendar.txt nor calendar_dates.txt loaded.")

    stops_geojson  = build_stops_geojson(
        tables["stops"], tables["stop_times"],
        tables["trips"], tables["routes"],
        service_type, config
    )
    routes_geojson = build_routes_geojson(
        tables["shapes"], tables["trips"], tables["routes"], config
    )

    return stops_geojson, routes_geojson, tables
