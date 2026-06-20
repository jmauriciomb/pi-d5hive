import json
import socket
import datetime
import numpy as np
import pandas as pd
import clts_pcp as clts  # type: ignore

hostname = socket.gethostname()

# InsertResult
# Dado que tenho ter os inserts , esta estrutura evita repetir codigo
class InsertResult:
    def __init__(self):
        self.inserted = self.skipped = self.errors = 0

    def __iadd__(self, other: "InsertResult"):
        self.inserted += other.inserted
        self.skipped  += other.skipped
        self.errors   += other.errors
        return self

    def __repr__(self):
        return f"inserted={self.inserted} | skipped={self.skipped} | errors={self.errors}"


# Helpers: tamanho das tabelas

def _get_crate_size(cur, table_name: str, config) -> None:
    try:
        cur.execute("SELECT sum(size) FROM sys.shards WHERE table_name = %s", (table_name,))
        row  = cur.fetchone()
        size = row[0] if row and row[0] is not None else 0
        print(f"  CrateDB '{table_name}': {size/1024:.4f} KB")
        clts.elapt[f"  CrateDB '{table_name}': {size/1024:.4f} KB"] = clts.deltat(config.TSTART)
    except Exception as e:
        print(f"  Não foi possível obter tamanho CrateDB '{table_name}': {e}")


def _get_tidb_size(cur, table_name: str, config) -> None:
    try:
        cur.execute("""
            SELECT (data_length + index_length)
            FROM information_schema.TABLES
            WHERE table_schema = DATABASE() AND table_name = %s
        """, (table_name,))
        row  = cur.fetchone()
        size = row[0] if row and row[0] is not None else 0
        print(f"  TiDB '{table_name}': {size/1024:.4f} KB")
        clts.elapt[f"  TiDB '{table_name}': {size/1024:.4f} KB"] = clts.deltat(config.TSTART)
    except Exception as e:
        print(f"  Erro ao obter tamanho TiDB '{table_name}': {e}")


def _get_mongo_size(collection, name: str, config) -> None:
    try:
        stats      = collection.database.command("collStats", name)
        size_bytes = stats.get("storageSize", 0)
        print(f"  MongoDB '{name}': {size_bytes/1024:.4f} KB")
        clts.elapt[f"  MongoDB '{name}': {size_bytes/1024:.4f} KB"] = clts.deltat(config.TSTART)
    except Exception as e:
        print(f"  Não foi possível obter tamanho MongoDB '{name}': {e}")


# Helpers: construção da lista de tabelas GTFS

# mapping: config attribute -> (dict key, primary key)
_GTFS_TABLE_DEFS = [
    ("TABLE_STOPS",           "stops",           "stop_id"),
    ("TABLE_ROUTES",          "routes",          "route_id"),
    ("TABLE_TRIPS",           "trips",           "trip_id"),
    ("TABLE_STOP_TIMES",      "stop_times",      ["trip_id", "stop_sequence"]),
    ("TABLE_SHAPES",          "shapes",          ["shape_id", "shape_pt_sequence"]),
    ("TABLE_CALENDAR",        "calendar",        "service_id"),
    ("TABLE_CALENDAR_DATES",  "calendar_dates",  ["service_id", "date"]),
    ("TABLE_AGENCY",          "agency",          "agency_id"),
    ("TABLE_FARE_ATTRIBUTES", "fare_attributes", "fare_id"),
    ("TABLE_FARE_RULES",      "fare_rules",      ["fare_id", "origin_id", "destination_id"]),
    ("TABLE_FEED_INFO",       "feed_info",       "feed_publisher_name"),
]

def _build_gtfs_table_list(tables: dict[str, pd.DataFrame], config) -> list[tuple]:
    """
    Devolve lista de (nome_tabela, dataframe, chave_primária)
    no mesmo formato que a pipeline original.
    Inclui apenas as tabelas presentes em config e carregadas.
    """
    result = []
    for attr, key, pk in _GTFS_TABLE_DEFS:
        if hasattr(config, attr) and key in tables:
            result.append((getattr(config, attr), tables[key], pk))
    return result


# MongoDB
def write_mongo(dbcreds: dict, tables: dict[str, pd.DataFrame],
                stops_geojson: dict, routes_geojson: dict,
                config) -> InsertResult:
    from pymongo import MongoClient
    import ssl as _ssl

    print("  Ligando ao MongoDB...")
    mongo_uri = (
        f"mongodb+srv://{dbcreds['username']}:{dbcreds['password']}"
        f"@{dbcreds['dest_host']}/{dbcreds['database']}"
        f"?retryWrites=true&w=majority"
    )

    ssl_ctx = _ssl.create_default_context()
    ssl_ctx.check_hostname  = False
    ssl_ctx.verify_mode     = _ssl.CERT_NONE
    ssl_ctx.minimum_version = _ssl.TLSVersion.TLSv1_2

    client = MongoClient(
        mongo_uri, tls=True, tlsAllowInvalidCertificates=True,
        tlsCAFile=None, serverSelectionTimeoutMS=20000,
    )
    db = client[dbcreds["database"]]
    print("  ✅ Ligado ao MongoDB")
    clts.elapt["✅ Ligado ao MongoDB"] = clts.deltat(config.TSTART)

    total      = InsertResult()
    tstamp     = clts.getts()
    gtfs_list  = _build_gtfs_table_list(tables, config)

    # Tabelas GTFS
    for (colname, df, key) in gtfs_list:
        collection = db[colname]
        print(f"\n  Processing {colname}...")

        keys = key if isinstance(key, list) else [key]

        if len(keys) == 1:
            existing_ids = {doc.get(keys[0]) for doc in collection.find({}, {keys[0]: 1})}
        else:
            existing_ids = {
                tuple(doc.get(k) for k in keys)
                for doc in collection.find({}, {k: 1 for k in keys})
            }

        docs, skipped = [], 0
        # build batch
        for _, row in df.iterrows():
            row_key = row[keys[0]] if len(keys) == 1 else tuple(row[k] for k in keys)
            if row_key not in existing_ids:
                doc = row.to_dict()
                doc["hostsource"] = hostname
                doc["tstamp"]     = tstamp
                docs.append(doc)
            else:
                skipped += 1
        # insert all at once
        if docs:
            collection.insert_many(docs)

        res       = InsertResult()
        res.inserted = len(docs)
        res.skipped  = skipped
        total    += res
        _get_mongo_size(collection, colname, config)
        clts.elapt[f"  [mongodb] {colname}: inserted {len(docs)}, skipped {skipped}"] = clts.deltat(config.TSTART)

    # Tabelas GeoJSON
    geojson_datasets = {
        config.TABLE_STOPS_GEOJSON:  stops_geojson,
        config.TABLE_ROUTES_GEOJSON: routes_geojson,
    }
    for uri, gj in geojson_datasets.items():
        collection = db[uri]
        collection.replace_one(
            {"uri": uri},
            {"uri": uri, "geojson": gj, "hostsource": hostname, "tstamp": tstamp},
            upsert=True,
        )
        clts.elapt[f"  [mongodb] GeoJSON saved: {uri}"] = clts.deltat(config.TSTART)
        print(f"GeoJSON guardado: {uri}")

    return total



# CrateDB

def write_crate(dbcreds: dict, tables: dict[str, pd.DataFrame],
                stops_geojson: dict, routes_geojson: dict,
                config) -> InsertResult:
    from crate import client as crate_client
    from psycopg2.extras import execute_values
    import psycopg2

    print("  Ligando ao CrateDB...")
    conn = psycopg2.connect(
        host=dbcreds["dest_host"], port=dbcreds["port"],
        database=dbcreds["database"], user=dbcreds["username"],
        password=dbcreds["password"],
    )
    cursor = conn.cursor()
    cursor.execute("SET search_path TO doc")
    print("  ✅ Ligado ao CrateDB")
    clts.elapt["✅ Ligado ao CrateDB"] = clts.deltat(config.TSTART)

    total      = InsertResult()
    BATCH_SIZE = 2000
    gtfs_list  = _build_gtfs_table_list(tables, config)

    # Tabelas GTFS
    for (tablename, df, key) in gtfs_list:
        print(f"\n  Processing {tablename}...")
        new_rows = df.copy()
        new_rows["hostsource"] = hostname
        new_rows["tstamp"]     = datetime.datetime.now()
        new_rows = new_rows.where(pd.notnull(new_rows), None)
        
        pk_cols = key if isinstance(key, list) else [key]
        
        col_defs = []
        for col, dtype in new_rows.dtypes.items():
            if "int"     in str(dtype): col_defs.append(f'"{col}" INTEGER')
            elif "float" in str(dtype): col_defs.append(f'"{col}" DOUBLE PRECISION')
            elif col == "tstamp":       col_defs.append(f'"{col}" TIMESTAMP')
            else:                       col_defs.append(f'"{col}" TEXT')
        pk_quoted = ", ".join([f'"{k}"' for k in pk_cols])
        col_defs.append(f'PRIMARY KEY ({pk_quoted})')

        create_sql = f'CREATE TABLE IF NOT EXISTS "{tablename}" ({", ".join(col_defs)})'
        cursor.execute(create_sql)
        conn.commit()

        cols     = list(new_rows.columns)
        values   = list(new_rows.itertuples(index=False, name=None))
        inserted = 0

        for i in range(0, len(values), BATCH_SIZE):
            batch = values[i:i + BATCH_SIZE]
            inserted_records = execute_values(
                cursor,
                f"INSERT INTO {tablename} ({', '.join(cols)}) VALUES %s ON CONFLICT DO NOTHING RETURNING 1",
                batch, fetch=True, page_size=BATCH_SIZE,
            )
            conn.commit()
            inserted += len(inserted_records) if inserted_records else 0
            print(f"    {tablename}: {i + len(batch)}/{len(values)}")

        skipped      = len(new_rows) - inserted
        res          = InsertResult()
        res.inserted = inserted
        res.skipped  = skipped
        total       += res
        _get_crate_size(cursor, tablename, config)
        clts.elapt[f"  [crate] {tablename}: inserted {inserted}, skipped {skipped}"] = clts.deltat(config.TSTART)

    # Tabelas GeoJSON
    geojson_datasets = {
        config.TABLE_STOPS_GEOJSON:  stops_geojson,
        config.TABLE_ROUTES_GEOJSON: routes_geojson,
    }
    for uri, gj in geojson_datasets.items():
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS "{uri}" (
                uri     TEXT PRIMARY KEY,
                geojson OBJECT(IGNORED)
            )
        """)
        conn.commit()
        cursor.execute(
            f'INSERT INTO "{uri}" (uri, geojson) VALUES (%s, %s) '
            f'ON CONFLICT (uri) DO UPDATE SET geojson = excluded.geojson',
            (uri, json.dumps(gj, ensure_ascii=False)),
        )
        conn.commit()
        clts.elapt[f"  [crate] GeoJSON saved: {uri}"] = clts.deltat(config.TSTART)
        print(f"GeoJSON guardado: {uri}")

    cursor.close()
    conn.close()
    return total



# TiDB

def write_tidb(dbcreds: dict, tables: dict[str, pd.DataFrame],
               stops_geojson: dict, routes_geojson: dict,
               env: str, hostname_short: str, config) -> InsertResult:
    import pymysql

    ssl_ca = "/etc/ssl/certs/ca-certificates.crt" if env in ("google_colab", "render") else "/etc/ssl/cert.pem"

    print("  Ligando ao TiDB...")
    conn = pymysql.connect(
        host=dbcreds["dest_host"], port=dbcreds["port"],
        user=dbcreds["username"], password=dbcreds["password"],
        database=dbcreds["database"],
        ssl_verify_cert=True, ssl_verify_identity=True, ssl_ca=ssl_ca,
    )
    cursor = conn.cursor()
    print("  ✅ Ligado ao TiDB")
    clts.elapt["✅ Ligado ao TiDB"] = clts.deltat(config.TSTART)

    total     = InsertResult()
    BATCH     = 2000
    gtfs_list = _build_gtfs_table_list(tables, config)

    # Tabelas GTFS
    for (tablename, df, key) in gtfs_list:        
        print(f"\n  Processing {tablename}...")
        new_rows = df.copy()
        new_rows["hostsource"] = hostname
        new_rows["tstamp"]     = datetime.datetime.now()
         # MySQL não aceita NaN, só NULL
        new_rows = new_rows.where(pd.notnull(new_rows), None)

        pk_cols  = key if isinstance(key, list) else [key]
        # cria a tabela se não existir, inferindo colunas do DataFrame
        col_defs = []
        for col, dtype in new_rows.dtypes.items():
            if "int"   in str(dtype): col_defs.append(f"`{col}` BIGINT")
            elif "float" in str(dtype): col_defs.append(f"`{col}` DOUBLE")
            elif col == "tstamp":       col_defs.append(f"`{col}` DATETIME")
            elif col in pk_cols:        col_defs.append(f"`{col}` VARCHAR(255)")
            else:                       col_defs.append(f"`{col}` TEXT")
        col_defs.append(f"PRIMARY KEY ({', '.join([f'`{k}`' for k in pk_cols])})")

        create_sql = f"CREATE TABLE IF NOT EXISTS `{tablename}` ({', '.join(col_defs)})"
        cursor.execute(create_sql)
        conn.commit()

        # insert com ON DUPLICATE KEY UPDATE : requer chave primária
        # usa INSERT IGNORE para ignorar duplicados sem chave definida
        cols = list(new_rows.columns)
        placeholders = ", ".join(["%s"] * len(cols))
        col_names = ", ".join([f"`{c}`" for c in cols])
        insert_sql = f"INSERT IGNORE INTO `{tablename}` ({col_names}) VALUES ({placeholders})"

        values = [
            tuple(None if (v is not None and isinstance(v, float) and np.isnan(v)) else v for v in row)
            for _, row in new_rows.iterrows()
        ]

        inserted = 0
        for i in range(0, len(values), BATCH):
            batch = values[i:i + BATCH]
            cursor.executemany(insert_sql, batch)
            conn.commit()
            inserted += cursor.rowcount
            print(f"    {tablename}: {i + len(batch)}/{len(values)}")

        skipped      = len(new_rows) - inserted
        res          = InsertResult()
        res.inserted = inserted
        res.skipped  = skipped
        total       += res
        _get_tidb_size(cursor, tablename, config)
        clts.elapt[f"  [tidb] {tablename}: inserted {inserted}, skipped {skipped}"] = clts.deltat(config.TSTART)

    # Tabelas GeoJSON
    # skipped for TiDB (row size limit, stored in MongoDB only)
    
    #geojson_datasets = {
    #   config.TABLE_STOPS_GEOJSON:  stops_geojson,
    #   config.TABLE_ROUTES_GEOJSON: routes_geojson,
    #}
    #for uri, gj in geojson_datasets.items():
    #   cursor.execute(f"""
    #        CREATE TABLE IF NOT EXISTS `{uri}` (
    #            uri     VARCHAR(200) NOT NULL,
    #           geojson JSON NOT NULL,
    #           PRIMARY KEY (uri)
    #       )
    #   """)
    #   conn.commit()
    #   cursor.execute(
    #       f"INSERT INTO `{uri}` (uri, geojson) VALUES (%s, %s) "
    #       f"ON DUPLICATE KEY UPDATE geojson = VALUES(geojson)",
    #       (uri, json.dumps(gj, ensure_ascii=False)),
    #   )
    #   conn.commit()
    #   clts.elapt[f"  [tidb] GeoJSON saved: {uri}"] = clts.deltat(config.TSTART)
    #   print(f"GeoJSON guardado: {uri}")

    cursor.close()
    conn.close()
    return total


# Dispatcher
def write_to_db(dbcreds: dict, tables: dict[str, pd.DataFrame],
                stops_geojson: dict, routes_geojson: dict,
                env: str, hostname_short: str, config) -> InsertResult:
    dbms = dbcreds.get("dbms", "")
    if dbms == "mongodb":
        return write_mongo(dbcreds, tables, stops_geojson, routes_geojson, config)
    elif dbms == "crate":
        return write_crate(dbcreds, tables, stops_geojson, routes_geojson, config)
    elif dbms == "tidb":
        return write_tidb(dbcreds, tables, stops_geojson, routes_geojson, env, hostname_short, config)
    else:
        raise ValueError(f"DBMS não suportado: '{dbms}'")
