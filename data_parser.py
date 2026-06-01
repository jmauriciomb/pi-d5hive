import math
import json
import shutil
import zipfile
import requests
import pandas as pd
import clts_pcp as clts  # type: ignore

import config
from config import GTFS_URL, GTFS_PREFIX, VERBOSE

# helpers

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# download e extração

def download_and_extract(datapath: str) -> str:
    """
    Descarrega o ZIP GTFS e extrai para gtfs_data/.
    Devolve o caminho para a pasta com os ficheiros .txt.
    """
    import os
    zip_path  = os.path.join(datapath, "metro_porto.zip")
    gtfs_path = os.path.join(datapath, "gtfs_data")

    if os.path.exists(gtfs_path):
        shutil.rmtree(gtfs_path)
    os.makedirs(gtfs_path)

    response = requests.get(GTFS_URL, stream=True)
    response.raise_for_status()

    ct = response.headers.get("Content-Type", "")
    if "zip" not in ct and "octet-stream" not in ct:
        print(f"Unexpected Content-Type: {ct}")

    with open(zip_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"ZIP guardado em: {zip_path}")
    clts.elapt["Download GTFS Metro do Porto"] = clts.deltat(config.TSTART)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(gtfs_path)

    # detect flat vs subfolder extraction
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

def load_gtfs_tables(gtfs_folder: str) -> dict[str, pd.DataFrame]:
    """Carrega todos os ficheiros GTFS e devolve um dict name -> DataFrame."""
    import os
    files = {
        "stops":           "stops.txt",
        "routes":          "routes.txt",
        "trips":           "trips.txt",
        "stop_times":      "stop_times.txt",
        "shapes":          "shapes.txt",
        "calendar":        "calendar.txt",
        "calendar_dates":  "calendar_dates.txt",
        "agency":          "agency.txt",
        "fare_attributes": "fare_attributes.txt",
        "fare_rules":      "fare_rules.txt",
    }

    tables = {}
    for name, filename in files.items():
        path = os.path.join(gtfs_folder, filename)
        tables[name] = pd.read_csv(path)
        if VERBOSE:
            print(f"  {name}: {len(tables[name])} linhas")

    print("\nDataset sizes:")
    for name, df in tables.items():
        print(f"  {name}: {len(df)}")

    clts.elapt["Tabelas GTFS carregadas"] = clts.deltat(config.TSTART)
    return tables



# Construção dos GeoJSONs

def build_stops_geojson(stops: pd.DataFrame, stop_times: pd.DataFrame,
                        trips: pd.DataFrame, routes: pd.DataFrame) -> dict:
    """FeatureCollection de Points: uma feature por paragem."""

    st_trips  = stop_times[["trip_id", "stop_id"]].merge(
                    trips[["trip_id", "route_id"]], on="trip_id")
    st_routes = st_trips.merge(
                    routes[["route_id", "route_short_name"]], on="route_id")
    
    # Agrega as linhas únicas por paragem, ordenadas alfabeticamente
    lines_per_stop = (
        st_routes.groupby("stop_id")["route_short_name"]
        .apply(lambda x: sorted(x.unique().tolist()))
        .reset_index()
        .rename(columns={"route_short_name": "lines"})
    )
    # Junta as linhas ao DataFrame de paragens
    stops_geo = stops.merge(lines_per_stop, on="stop_id", how="left")

    # Constrói o GeoJSON: cada linha do DataFrame torna-se uma Feature
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
                         routes: pd.DataFrame) -> dict:
    """FeatureCollection de LineStrings: uma feature por rota."""

    # one representative shape per route
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

def parse_all(datapath: str) -> tuple[dict, dict, dict[str, pd.DataFrame]]:
    """
    Descarrega, extrai e processa os dados GTFS.
    Devolve (stops_geojson, routes_geojson, gtfs_tables).
    """
    gtfs_folder = download_and_extract(datapath)
    tables      = load_gtfs_tables(gtfs_folder)

    stops_geojson  = build_stops_geojson(
        tables["stops"], tables["stop_times"],
        tables["trips"], tables["routes"]
    )
    routes_geojson = build_routes_geojson(
        tables["shapes"], tables["trips"], tables["routes"]
    )

    return stops_geojson, routes_geojson, tables