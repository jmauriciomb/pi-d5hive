import math
import shutil
import zipfile
import requests
import pandas as pd
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
                        config) -> dict:
    """FeatureCollection de Points: uma feature por paragem."""

    st_trips  = stop_times[["trip_id", "stop_id"]].merge(
                    trips[["trip_id", "route_id"]], on="trip_id")
    st_routes = st_trips.merge(
                    routes[["route_id", "route_short_name"]], on="route_id")

    lines_per_stop = (
        st_routes.groupby("stop_id")["route_short_name"]
        .apply(lambda x: sorted(x.unique().tolist()))
        .reset_index()
        .rename(columns={"route_short_name": "lines"})
    )
    stops_geo = stops.merge(lines_per_stop, on="stop_id", how="left")

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row["stop_lon"], row["stop_lat"]],
                },
                "properties": {
                    "stop_id":   row["stop_id"],
                    "stop_name": row.get("stop_name", ""),
                    "stop_lat":  row["stop_lat"],
                    "stop_lon":  row["stop_lon"],
                    "lines":     row.get("lines", []),
                },
            }
            for _, row in stops_geo.iterrows()
        ],
    }

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

    stops_geojson  = build_stops_geojson(
        tables["stops"], tables["stop_times"],
        tables["trips"], tables["routes"], config
    )
    routes_geojson = build_routes_geojson(
        tables["shapes"], tables["trips"], tables["routes"], config
    )

    return stops_geojson, routes_geojson, tables
