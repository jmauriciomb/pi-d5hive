import socket
import clts_pcp as clts
from flask import Config
import pandas as pd
from typing import Optional

from pandas.plotting import table
import config
from config import (
    INSERT_MODE, CREATE_SUMMARY,
    TABLE_NORMAL, TABLE_SPECIFIC, TABLE_RECTIFIER,
    TABLE_SUMMARY_DAILY, TABLE_SUMMARY_MONTHLY,
    COL_SPECIFIC, COL_RECTIFIER, 
)

hostname = socket.gethostname()
#Lazyness
S = COL_SPECIFIC   
R = COL_RECTIFIER  


#TEMOS DE CRIAR uma destas para cada tipo de db

def get_crate_size(cur, table_name: str) -> int:
    try:
        cur.execute(
            "SELECT sum(size) FROM sys.shards WHERE table_name = ?",
            (table_name,)
        )
        row = cur.fetchone()
        size = row[0] if row and row[0] is not None else 0
        print(f"  CrateDB '{table_name}': {size/1024:.4f} KB")
        clts.elapt[f"  CrateDB '{table_name}': {size/1024:.4f} KB"]=clts.deltat(config.TSTART)
        return size
    except Exception as e:
        print(f"  Não foi possível obter tamanho CrateDB '{table_name}': {e}")
        return 0
def get_tidb_size(cur, table_name: str) -> int:
    try:
        # No TiDB/MySQL consultamos o information_schema
        cur.execute("""
            SELECT (data_length + index_length) 
            FROM information_schema.TABLES 
            WHERE table_schema = DATABASE() AND table_name = %s
        """, (table_name,))
        row = cur.fetchone()
        # Se usar DictCursor, aceder por nome, senão por índice
        size = row[0] if row and row[0] is not None else 0
        print(f"  TiDB '{table_name}': {size/1024:.4f} KB")
        clts.elapt[f"  TiDB '{table_name}': {size/1024:.4f} KB"]=clts.deltat(config.TSTART)
        return size
    except Exception as e:
        print(f"  Erro ao obter tamanho TiDB '{table_name}': {e}")
        return 0

def get_mongo_size(collection, name: str) -> int:
    try:
        stats      = collection.database.command("collStats", name)
        size_bytes = stats.get("storageSize", 0)
        print(f"  MongoDB '{name}': {size_bytes/1024:.4f} KB")
        clts.elapt[f"  MongoDB '{name}': {size_bytes/1024:.4f} KB"]=clts.deltat(config.TSTART)
        return size_bytes
    except Exception as e:
        print(f"  Não foi possível obter tamanho MongoDB '{name}': {e}")
        return 0


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
        return (f"inserted={self.inserted} | skipped={self.skipped} "
                f"| errors={self.errors}")

# CrateDB

def _ensure_crate_tables(cur) -> None:
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NORMAL} (
            row_hash          TEXT PRIMARY KEY,
            tstamp            TIMESTAMP WITH TIME ZONE,
            mes               CHAR(7) NOT NULL,
            consumida_direto  DOUBLE,
            consumo           DOUBLE,
            energia_rede      DOUBLE,
            hostsource        TEXT,
            ficheiro          TEXT
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_SPECIFIC} (
            row_hash                 TEXT PRIMARY KEY,
            tstamp                   TIMESTAMP WITH TIME ZONE,
            mes                      CHAR(7) NOT NULL,
            energia_powermeter       DOUBLE,
            energia_symo_um          DOUBLE,
            energia_symo_dois        DOUBLE,
            energia_mpp1_powermeter  DOUBLE,
            energia_mpp1_symo_um     DOUBLE,
            energia_mpp1_symo_dois   DOUBLE,
            energia_mpp2_powermeter  DOUBLE,
            energia_mpp2_symo_um     DOUBLE,
            energia_mpp2_symo_dois   DOUBLE,
            rendimento_powermeter    DOUBLE,
            rendimento_symo_1        DOUBLE,
            rendimento_symo_2        DOUBLE,
            consumida_diretamente    DOUBLE,
            consumo                  DOUBLE,
            energia_obtida_bateria   DOUBLE,
            energia_obtida_rede      DOUBLE,
            energia_salva_bateria    DOUBLE,
            energia_salva_rede       DOUBLE,
            hostsource               TEXT,
            ficheiro                 TEXT
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_RECTIFIER} (
            row_hash                       TEXT PRIMARY KEY,
            tstamp                         TIMESTAMP WITH TIME ZONE,
            mes                            CHAR(7) NOT NULL,
            energia_retificador_symo_1     DOUBLE,
            energia_retificador_symo_2     DOUBLE,
            energia_retificador_symo_1_kwp DOUBLE,
            energia_retificador_symo_2_kwp DOUBLE,
            instalacao_total               DOUBLE,
            hostsource                     TEXT,
            ficheiro                       TEXT
        )
    """)


def _insert_crate_normal(cur, df: pd.DataFrame) -> InsertResult:
    res = InsertResult()
    size_before = get_crate_size(cur, TABLE_NORMAL) 
    for _, row in df.iterrows():
        try:
            cur.execute(f"""
                INSERT INTO {TABLE_NORMAL}
                    (row_hash, tstamp, mes, consumida_direto, consumo,
                     energia_rede, hostsource, ficheiro)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (row_hash) DO NOTHING
            """, (
                row["_row_hash"],
                row["_tstamp"].strftime("%Y-%m-%dT%H:%M:%S"),
                row["mes"],
                row["_consumida_direto"], row["_consumo"],
                row["_energia_rede"], hostname, row["_source_file"],
            ))
            if cur.rowcount == 1:
                res.inserted += 1
            else:
                res.skipped += 1
        except Exception as e:
            if "duplicate" in str(e).lower():
                res.skipped += 1
            else:
                res.errors += 1
                raise
    size_after = get_crate_size(cur, TABLE_NORMAL)
    delta = size_after - size_before
    print(f"  [{TABLE_NORMAL}] variacao de tamanho: {delta/1024:+.4f} KB")
    clts.elapt[f"  [{TABLE_NORMAL}] variacao de tamanho: {delta/1024:+.4f} KB"] = clts.deltat(config.TSTART)
    return res
  

def _insert_crate_specific(cur, df: pd.DataFrame) -> InsertResult:
    res = InsertResult()
    size_before = get_crate_size(cur, TABLE_SPECIFIC)
    for _, row in df.iterrows():
        try:
            cur.execute(f"""
                INSERT INTO {TABLE_SPECIFIC} (
                    row_hash, tstamp, mes,
                    energia_powermeter, energia_symo_um, energia_symo_dois,
                    energia_mpp1_powermeter, energia_mpp1_symo_um, energia_mpp1_symo_dois,
                    energia_mpp2_powermeter, energia_mpp2_symo_um, energia_mpp2_symo_dois,
                    rendimento_powermeter, rendimento_symo_1, rendimento_symo_2,
                    consumida_diretamente, consumo,
                    energia_obtida_bateria, energia_obtida_rede,
                    energia_salva_bateria, energia_salva_rede,
                    hostsource, ficheiro
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (row_hash) DO NOTHING
            """, (
                row["_row_hash"],
                row["_tstamp"].strftime("%Y-%m-%dT%H:%M:%S"),
                row["mes"],
                row.get(S["energia_powermeter"]),
                row.get(S["energia_symo_um"]),
                row.get(S["energia_symo_dois"]),
                row.get(S["energia_mpp1_powermeter"]),
                row.get(S["energia_mpp1_symo_um"]),
                row.get(S["energia_mpp1_symo_dois"]),
                row.get(S["energia_mpp2_powermeter"]),
                row.get(S["energia_mpp2_symo_um"]),
                row.get(S["energia_mpp2_symo_dois"]),
                row.get(S["rendimento_powermeter"]),
                row.get(S["rendimento_symo_um"]),
                row.get(S["rendimento_symo_dois"]),
                row.get(S["consumida_direto"]),
                row.get(S["consumo"]),
                row.get(S["energia_obtida_bateria"]),
                row.get(S["energia_obtida_rede"]),
                row.get(S["energia_salva_bateria"]),
                row.get(S["energia_salva_rede"]),
                hostname, row["_source_file"],
            ))
            if cur.rowcount == 1:
                res.inserted += 1
            else:
                res.skipped += 1
        except Exception as e:
            res.errors += 1
            print(f"  Erro specific CrateDB: {e}")
    size_after = get_crate_size(cur, TABLE_SPECIFIC)
    delta = size_after - size_before
    print(f"  [{TABLE_SPECIFIC}] variacao de tamanho: {delta/1024:+.4f} KB")
    clts.elapt[f"  [{TABLE_SPECIFIC}] variacao de tamanho: {delta/1024:+.4f} KB"] = clts.deltat(config.TSTART)
    return res


def _insert_crate_rectifier(cur, df: pd.DataFrame) -> InsertResult:
    res = InsertResult()
    size_before = get_crate_size(cur, TABLE_RECTIFIER)
    for _, row in df.iterrows():
        try:
            cur.execute(f"""
                INSERT INTO {TABLE_RECTIFIER} (
                    row_hash, tstamp, mes,
                    energia_retificador_symo_1, energia_retificador_symo_2,
                    energia_retificador_symo_1_kwp, energia_retificador_symo_2_kwp,
                    instalacao_total, hostsource, ficheiro
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (row_hash) DO NOTHING
            """, (
                row["_row_hash"],
                row["_tstamp"].strftime("%Y-%m-%dT%H:%M:%S"),
                row["mes"],
                row.get(R["energia_symo_um"]),
                row.get(R["energia_symo_dois"]),
                row.get(R["energia_symo_um_kwp"]),
                row.get(R["energia_symo_dois_kwp"]),
                row.get(R["instalacoes_total"]),
                hostname, row["_source_file"],
            ))
            if cur.rowcount == 1:
                res.inserted += 1
            else:
                res.skipped += 1
        except Exception as e:
            res.errors += 1
            print(f"  Erro rectifier CrateDB: {e}")
    size_after = get_crate_size(cur, TABLE_RECTIFIER)
    delta = size_after - size_before
    print(f"  [{TABLE_RECTIFIER}] variacao de tamanho: {delta/1024:+.4f} KB")
    clts.elapt[f"  [{TABLE_RECTIFIER}] variacao de tamanho: {delta/1024:+.4f} KB"] = clts.deltat(config.TSTART)
    return res


def _crate_create_summaries(cur, conn) -> None:
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_SUMMARY_MONTHLY} (
            mes              TEXT PRIMARY KEY,
            consumida_direto DOUBLE,
            consumo          DOUBLE,
            energia_rede     DOUBLE,
            dias_considerados INT
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_SUMMARY_DAILY} (
            dia              TIMESTAMP PRIMARY KEY,
            consumida_direto DOUBLE,
            consumo          DOUBLE,
            energia_rede     DOUBLE
        )
    """)
    cur.execute(f"""
        INSERT INTO {TABLE_SUMMARY_MONTHLY} (mes, consumida_direto, consumo, energia_rede, dias_considerados)
        SELECT mes,
               SUM(consumida_direto), SUM(consumo), SUM(energia_rede),
               COUNT(DISTINCT DATE_TRUNC('day', tstamp))
        FROM {TABLE_NORMAL}
        GROUP BY 1
        ON CONFLICT (mes) DO UPDATE SET
            consumida_direto  = EXCLUDED.consumida_direto,
            consumo           = EXCLUDED.consumo,
            energia_rede      = EXCLUDED.energia_rede,
            dias_considerados = EXCLUDED.dias_considerados
    """)
    cur.execute(f"""
        INSERT INTO {TABLE_SUMMARY_DAILY}
        SELECT DATE_TRUNC('day', tstamp) AS dia,
               SUM(consumida_direto), SUM(consumo), SUM(energia_rede)
        FROM {TABLE_NORMAL}
        GROUP BY dia
        ON CONFLICT (dia) DO UPDATE SET
            consumida_direto = excluded.consumida_direto,
            consumo          = excluded.consumo,
            energia_rede     = excluded.energia_rede
    """)
    conn.commit()


def write_crate( dbcreds: dict, df_normal: pd.DataFrame, df_specific: pd.DataFrame, df_rectifier: pd.DataFrame) -> InsertResult:
    from crate import client as crate_client  # type: ignore

    print("  Ligando ao CrateDB…")
    conn = crate_client.connect(
        dbcreds["dest_host"],
        username=dbcreds["username"],
        password=dbcreds["password"],
        verify_ssl_cert=True,
    )
    cur = conn.cursor()
    print("✅ Ligado ao CrateDB")
    clts.elapt["✅ Ligado ao CrateDB"]=clts.deltat(config.TSTART)
    _ensure_crate_tables(cur)

    total = InsertResult()

    if not df_normal.empty:
        r = _insert_crate_normal(cur, df_normal)
        print(f"  normal    -> {r}")
        total += r

    if not df_specific.empty:
        r = _insert_crate_specific(cur, df_specific)
        print(f"  specific  -> {r}")
        total += r

    if not df_rectifier.empty:
        r = _insert_crate_rectifier(cur, df_rectifier)
        print(f"  rectifier -> {r}")
        total += r

    conn.commit()

    if CREATE_SUMMARY:
        _crate_create_summaries(cur, conn)
        

    return total
#Tidb

def _ensure_tidb_tables(cur) -> None:
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NORMAL} (
            row_hash          VARCHAR(64) PRIMARY KEY,
            tstamp            DATETIME(6) NOT NULL,
            mes               CHAR(7) NOT NULL,
            consumida_direto  DOUBLE,
            consumo           DOUBLE,
            energia_rede      DOUBLE,
            hostsource        VARCHAR(255),
            ficheiro          VARCHAR(255),
            INDEX idx_tstamp (tstamp)
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_SPECIFIC} (
            row_hash                  VARCHAR(64)  PRIMARY KEY,
            tstamp                   DATETIME(6) NOT NULL,
            mes                      CHAR(7) NOT NULL,
            energia_powermeter       DOUBLE,
            energia_symo_um          DOUBLE,
            energia_symo_dois        DOUBLE,
            energia_mpp1_powermeter  DOUBLE,
            energia_mpp1_symo_um     DOUBLE,
            energia_mpp1_symo_dois   DOUBLE,
            energia_mpp2_powermeter  DOUBLE,
            energia_mpp2_symo_um     DOUBLE,
            energia_mpp2_symo_dois   DOUBLE,
            rendimento_powermeter    DOUBLE,
            rendimento_symo_1        DOUBLE,
            rendimento_symo_2        DOUBLE,
            consumida_diretamente    DOUBLE,
            consumo                  DOUBLE,
            energia_obtida_bateria   DOUBLE,
            energia_obtida_rede      DOUBLE,
            energia_salva_bateria    DOUBLE,
            energia_salva_rede       DOUBLE,
            hostsource               VARCHAR(255),
            ficheiro                 VARCHAR(255)
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_RECTIFIER} (
            row_hash                       VARCHAR(64) PRIMARY KEY,
            tstamp                          DATETIME(6) NOT NULL,
            mes                            CHAR(7) NOT NULL,
            energia_retificador_symo_1     DOUBLE,
            energia_retificador_symo_2     DOUBLE,
            energia_retificador_symo_1_kwp DOUBLE,
            energia_retificador_symo_2_kwp DOUBLE,
            instalacao_total               DOUBLE,
            hostsource                      VARCHAR(255),
            ficheiro                        VARCHAR(255)
        )
    """)

def _insert_tidb_normal(cur, df: pd.DataFrame) -> InsertResult:
    res = InsertResult()
    size_before = get_tidb_size(cur, TABLE_NORMAL)
    for _, row in df.iterrows():
        try:
            cur.execute(f"""
                INSERT INTO {TABLE_NORMAL}
                    (row_hash, tstamp, mes, consumida_direto, consumo,
                     energia_rede, hostsource, ficheiro)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE row_hash = row_hash
            """, (
                row["_row_hash"],
                row["_tstamp"].strftime("%Y-%m-%dT%H:%M:%S"),
                row["mes"],
                row["_consumida_direto"], row["_consumo"],
                row["_energia_rede"], hostname, row["_source_file"],
            ))
            if cur.rowcount == 1:
                res.inserted += 1
            else:
                res.skipped += 1
        except Exception as e:
            if "duplicate" in str(e).lower():
                res.skipped += 1
            else:
                res.errors += 1
                raise
    size_after = get_tidb_size(cur, TABLE_NORMAL)
    delta = size_after - size_before
    print(f"  [{TABLE_NORMAL}] variacao de tamanho: {delta/1024:+.4f} KB")
    clts.elapt[f"  [{TABLE_NORMAL}] variacao de tamanho: {delta/1024:+.4f} KB"] = clts.deltat(config.TSTART)
    return res

def _insert_tidb_specific(cur, df: pd.DataFrame) -> InsertResult:
    res = InsertResult()
    size_before = get_tidb_size(cur, TABLE_SPECIFIC)

    for _, row in df.iterrows():
        try:
            cur.execute(f"""
                INSERT INTO {TABLE_SPECIFIC} (
                    row_hash, tstamp, mes,
                    energia_powermeter, energia_symo_um, energia_symo_dois,
                    energia_mpp1_powermeter, energia_mpp1_symo_um, energia_mpp1_symo_dois,
                    energia_mpp2_powermeter, energia_mpp2_symo_um, energia_mpp2_symo_dois,
                    rendimento_powermeter, rendimento_symo_1, rendimento_symo_2,
                    consumida_diretamente, consumo,
                    energia_obtida_bateria, energia_obtida_rede,
                    energia_salva_bateria, energia_salva_rede,
                    hostsource, ficheiro

                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE row_hash = row_hash  """, (
                row["_row_hash"],
                row["_tstamp"].strftime("%Y-%m-%dT%H:%M:%S"),
                row["mes"],
                row.get(S["energia_powermeter"]),
                row.get(S["energia_symo_um"]),
                row.get(S["energia_symo_dois"]),
                row.get(S["energia_mpp1_powermeter"]),
                row.get(S["energia_mpp1_symo_um"]),
                row.get(S["energia_mpp1_symo_dois"]),
                row.get(S["energia_mpp2_powermeter"]),
                row.get(S["energia_mpp2_symo_um"]),
                row.get(S["energia_mpp2_symo_dois"]),
                row.get(S["rendimento_powermeter"]),
                row.get(S["rendimento_symo_um"]),
                row.get(S["rendimento_symo_dois"]),
                row.get(S["consumida_direto"]),
                row.get(S["consumo"]),
                row.get(S["energia_obtida_bateria"]),
                row.get(S["energia_obtida_rede"]),
                row.get(S["energia_salva_bateria"]),
                row.get(S["energia_salva_rede"]),
                hostname, row["_source_file"],
            ))
            if cur.rowcount == 1:
                res.inserted += 1
            else:
                res.skipped += 1
        except Exception as e:
            res.errors += 1
            print(f"  Erro specific CrateDB: {e}")
    size_after = get_tidb_size(cur, TABLE_NORMAL)
    delta = size_after - size_before
    print(f"  [{TABLE_SPECIFIC}] variacao de tamanho: {delta/1024:+.4f} KB")
    clts.elapt[f"  [{TABLE_SPECIFIC}] variacao de tamanho: {delta/1024:+.4f} KB"] = clts.deltat(config.TSTART)
    return res


def _insert_tidb_rectifier(cur, df: pd.DataFrame) -> InsertResult:
    res = InsertResult()
    size_before = get_tidb_size(cur, TABLE_SPECIFIC)
    for _, row in df.iterrows():
        try:
            cur.execute(f"""
                INSERT INTO {TABLE_RECTIFIER} (
                    row_hash, tstamp, mes,
                    energia_retificador_symo_1, energia_retificador_symo_2,
                    energia_retificador_symo_1_kwp, energia_retificador_symo_2_kwp,
                    instalacao_total, hostsource, ficheiro
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE row_hash = row_hash
            """, (
                row["_row_hash"],
                row["_tstamp"].strftime("%Y-%m-%dT%H:%M:%S"),
                row["mes"],
                row.get(R["energia_symo_um"]),
                row.get(R["energia_symo_dois"]),
                row.get(R["energia_symo_um_kwp"]),
                row.get(R["energia_symo_dois_kwp"]),
                row.get(R["instalacoes_total"]),
                hostname, row["_source_file"],
            ))
            if cur.rowcount == 1:
                res.inserted += 1
            else:
                res.skipped += 1
        except Exception as e:
            res.errors += 1
            print(f"  Erro rectifier Tidb: {e}")
    size_after = get_tidb_size(cur, TABLE_RECTIFIER)
    delta = size_after - size_before
    print(f"  [{TABLE_RECTIFIER}] variacao de tamanho: {delta/1024:+.4f} KB")
    clts.elapt[f"  [{TABLE_RECTIFIER}] variacao de tamanho: {delta/1024:+.4f} KB"] = clts.deltat(config.TSTART)
    return res

# MongoDB
def _ensure_mongo_collections(mdb) -> None:
    existing = mdb.list_collection_names()
    ts_opts  = {"granularity": "minutes"}
    for name in (TABLE_NORMAL, TABLE_SPECIFIC, TABLE_RECTIFIER):
        if name not in existing:
            mdb.create_collection(
                name,
                timeseries={"timeField": "tstamp", "metaField": "hostsource", **ts_opts},
            )
            print(f"  Coleção time-series '{name}' criada ✅")


def _make_mongo_doc_normal(row) -> dict:
    return {
        "tstamp":     row["_tstamp"],
        "hostsource": {"row_hash": row["_row_hash"], "hostname": hostname,
                       "ficheiro": row["_source_file"]},
        "consumida_direto": row["_consumida_direto"],
        "consumo":          row["_consumo"],
        "energia_rede":     row["_energia_rede"],
        "mes":              row["mes"],
    }


def _make_mongo_doc_specific(row) -> dict:
    return {
        "tstamp":     row["_tstamp"],
        "hostsource": {"row_hash": row["_row_hash"], "hostname": hostname,
                       "ficheiro": row["_source_file"]},
        "mes":                     row["mes"],
        "energia_powermeter":      row.get(S["energia_powermeter"]),
        "energia_symo_um":         row.get(S["energia_symo_um"]),
        "energia_symo_dois":       row.get(S["energia_symo_dois"]),
        "energia_mpp1_powermeter": row.get(S["energia_mpp1_powermeter"]),
        "energia_mpp1_symo_um":    row.get(S["energia_mpp1_symo_um"]),
        "energia_mpp1_symo_dois":  row.get(S["energia_mpp1_symo_dois"]),
        "energia_mpp2_powermeter": row.get(S["energia_mpp2_powermeter"]),
        "energia_mpp2_symo_um":    row.get(S["energia_mpp2_symo_um"]),
        "energia_mpp2_symo_dois":  row.get(S["energia_mpp2_symo_dois"]),
        "rendimento_powermeter":   row.get(S["rendimento_powermeter"]),
        "rendimento_symo_1":       row.get(S["rendimento_symo_um"]),
        "rendimento_symo_2":       row.get(S["rendimento_symo_dois"]),
        "consumida_diretamente":   row.get(S["consumida_direto"]),
        "consumo":                 row.get(S["consumo"]),
        "energia_obtida_bateria":  row.get(S["energia_obtida_bateria"]),
        "energia_obtida_rede":     row.get(S["energia_obtida_rede"]),
        "energia_salva_bateria":   row.get(S["energia_salva_bateria"]),
        "energia_salva_rede":      row.get(S["energia_salva_rede"]),
    }


def _make_mongo_doc_rectifier(row) -> dict:
    return {
        "tstamp":     row["_tstamp"],
        "hostsource": {"row_hash": row["_row_hash"], "hostname": hostname,
                       "ficheiro": row["_source_file"]},
        "mes":                            row["mes"],
        "energia_retificador_symo_1":     row.get(R["energia_symo_um"]),
        "energia_retificador_symo_2":     row.get(R["energia_symo_dois"]),
        "energia_retificador_symo_1_kwp": row.get(R["energia_symo_um_kwp"]),
        "energia_retificador_symo_2_kwp": row.get(R["energia_symo_dois_kwp"]),
        "instalacao_total":               row.get(R["instalacoes_total"]),
    }



def _mongo_insert_df(collection, df: pd.DataFrame, make_doc_fn, table_name: str) -> InsertResult:
    res = InsertResult()
    size_before = get_mongo_size(collection, table_name)

    for _, row in df.iterrows():
        rid = row["_row_hash"]
        doc = make_doc_fn(row)
        try:
            if collection.count_documents({"hostsource.row_hash": rid}, limit=1) == 0:
                collection.insert_one(doc)
                res.inserted += 1
            else:
                res.skipped += 1
        except Exception as e:
            res.errors += 1
            print(f"  Erro MongoDB insert: {e}")

    size_after = get_mongo_size(collection, table_name)
    delta = size_after - size_before
    print(f"  [{table_name}] variacao de tamanho: {delta/1024:+.4f} KB")
    clts.elapt[f"  [{table_name}] variacao de tamanho: {delta/1024:+.4f} KB"] = clts.deltat(config.TSTART)
    return res


def _mongo_create_summaries(mdb) -> None:
    from pymongo import UpdateOne  # type: ignore

    for name in (TABLE_SUMMARY_MONTHLY, TABLE_SUMMARY_DAILY):
        if name not in mdb.list_collection_names():
            mdb.create_collection(name)

    coll_monthly = mdb[TABLE_SUMMARY_MONTHLY]
    coll_daily   = mdb[TABLE_SUMMARY_DAILY]
    coll_monthly.create_index("mes", unique=True)
    coll_daily.create_index("dia",   unique=True)

    collection = mdb[TABLE_NORMAL]

    monthly_data = list(collection.aggregate([
        {"$group": {
            "_id": "$mes",
            "consumida_direto": {"$sum": "$consumida_direto"},
            "consumo":          {"$sum": "$consumo"},
            "energia_rede":     {"$sum": "$energia_rede"},
            "dias_unicos":      {"$addToSet": {"$dateTrunc": {"date": "$tstamp", "unit": "day"}}},
        }},
        {"$project": {
            "_id": 0, "mes": "$_id",
            "consumida_direto": 1, "consumo": 1, "energia_rede": 1,
            "dias_considerados": {"$size": "$dias_unicos"},
        }},
    ]))

    daily_data = list(collection.aggregate([
        {"$group": {
            "_id": {"$dateTrunc": {"date": "$tstamp", "unit": "day"}},
            "consumida_direto": {"$sum": "$consumida_direto"},
            "consumo":          {"$sum": "$consumo"},
            "energia_rede":     {"$sum": "$energia_rede"},
        }},
        {"$project": {"_id": 0, "dia": "$_id",
                      "consumida_direto": 1, "consumo": 1, "energia_rede": 1}},
    ]))

    if monthly_data:
        coll_monthly.bulk_write(
            [UpdateOne({"mes": d["mes"]}, {"$set": d}, upsert=True) for d in monthly_data],
            ordered=False,
        )
    if daily_data:
        coll_daily.bulk_write(
            [UpdateOne({"dia": d["dia"]}, {"$set": d}, upsert=True) for d in daily_data],
            ordered=False,
        )
    print(f"  Sumário mensal: {len(monthly_data)} meses | diário: {len(daily_data)} dias ✅")
def _tidb_create_summaries(cur):
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_SUMMARY_DAILY} (
            dia DATE PRIMARY KEY,
            consumida_direto DOUBLE,
            consumo DOUBLE,
            energia_rede DOUBLE
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_SUMMARY_MONTHLY} (
            mes VARCHAR(7) PRIMARY KEY,
            consumida_direto DOUBLE,
            consumo DOUBLE,
            energia_rede DOUBLE,
            dias_considerados INT
        )
    """)

    # DAILY
    cur.execute(f"""
        INSERT INTO {TABLE_SUMMARY_DAILY} (dia, consumida_direto, consumo, energia_rede)
        SELECT 
            DATE(tstamp) AS dia,
            SUM(consumida_direto),
            SUM(consumo),
            SUM(energia_rede)
        FROM {TABLE_NORMAL}
        GROUP BY DATE(tstamp)
        ON DUPLICATE KEY UPDATE
            consumida_direto = VALUES(consumida_direto),
            consumo = VALUES(consumo),
            energia_rede = VALUES(energia_rede)
    """)

    # MONTHLY
    cur.execute(f"""
        INSERT INTO {TABLE_SUMMARY_MONTHLY} 
            (mes, consumida_direto, consumo, energia_rede, dias_considerados)
        SELECT 
            mes,
            SUM(consumida_direto),
            SUM(consumo),
            SUM(energia_rede),
            COUNT(DISTINCT DATE(tstamp))
        FROM {TABLE_NORMAL}
        GROUP BY mes
        ON DUPLICATE KEY UPDATE
            consumida_direto = VALUES(consumida_direto),
            consumo = VALUES(consumo),
            energia_rede = VALUES(energia_rede),
            dias_considerados = VALUES(dias_considerados)
    """)
def write_tidb(dbcreds: dict, df_normal: pd.DataFrame, df_specific: pd.DataFrame, df_rectifier: pd.DataFrame) -> InsertResult:
    import pymysql
    print("  Ligando ao TiDB...")
    conn = pymysql.connect(
        host=dbcreds["dest_host"],
        user=dbcreds["username"],
        password=dbcreds["password"],
        database=dbcreds.get("database", "test"),
        port=dbcreds.get("port", 4000), 
        ssl={"ssl_mode": "VERIFY_IDENTITY"}
    )
    try:
        cur = conn.cursor()
        print("Ligado ao TiDB")
        clts.elapt["Ligado ao TiDB"]=clts.deltat(config.TSTART)
        _ensure_tidb_tables(cur)
        total = InsertResult()
        if not df_normal.empty:
            r = _insert_tidb_normal(cur, df_normal)
            print(f"  normal    -> {r}")
            total += r
        if not df_specific.empty:
            r = _insert_tidb_specific(cur, df_specific)
            print(f"  specific  -> {r}")
            total += r
        if not df_rectifier.empty:
            r = _insert_tidb_rectifier(cur, df_rectifier)
            print(f"  rectifier -> {r}")
            total += r
        conn.commit()
        if CREATE_SUMMARY:
            _tidb_create_summaries(cur)
    finally:
        conn.close()     
    return total    
    
    
def write_mongo(dbcreds: dict, df_normal: pd.DataFrame, df_specific: pd.DataFrame,df_rectifier: pd.DataFrame) -> InsertResult:
    """Escreve os três DataFrames numa instância MongoDB. Devolve InsertResult total."""
    from pymongo import MongoClient  # type: ignore
    import ssl as _ssl

    print("  Ligando ao MongoDB…")
    mongo_uri = (
        f"mongodb+srv://{dbcreds['username']}:{dbcreds['password']}"
        f"@{dbcreds['dest_host']}/{dbcreds['database']}"
        f"?retryWrites=true&w=majority"
    )
   
    
    ssl_ctx = _ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode    = _ssl.CERT_NONE
    ssl_ctx.minimum_version = _ssl.TLSVersion.TLSv1_2

    mclient = MongoClient(
        mongo_uri, tls=True, tlsAllowInvalidCertificates=True,
        tlsCAFile=None, serverSelectionTimeoutMS=20000,
    )
    mdb = mclient[dbcreds["database"]]
    print("  ✅ Ligado ao MongoDB")
    clts.elapt["  ✅ Ligado ao MongoDB"]=clts.deltat(config.TSTART)
    

    _ensure_mongo_collections(mdb)

    total = InsertResult()
    mode=INSERT_MODE
    

    if not df_normal.empty:
        r = _mongo_insert_df(mdb[TABLE_NORMAL], df_normal, _make_mongo_doc_normal,TABLE_NORMAL)
        print(f"  normal  ->{r}")
        total += r

    if not df_specific.empty:
        r = _mongo_insert_df(mdb[TABLE_SPECIFIC], df_specific, _make_mongo_doc_specific,TABLE_SPECIFIC)
        print(f"  specific  -> {r}")
        total += r

    if not df_rectifier.empty:
        r = _mongo_insert_df(mdb[TABLE_RECTIFIER], df_rectifier, _make_mongo_doc_rectifier,TABLE_RECTIFIER)
        print(f"  rectifier -> {r}")
        total += r

    if CREATE_SUMMARY:
        _mongo_create_summaries(mdb)

    return total

# Dispatcher

def write_to_db( dbcreds: dict, df_normal: pd.DataFrame, df_specific: pd.DataFrame, df_rectifier: pd.DataFrame,) -> InsertResult:
    dbms = dbcreds.get("dbms", "")
    if dbms == "crate":
        return write_crate(dbcreds, df_normal, df_specific, df_rectifier)
    elif dbms == "mongodb":
        return write_mongo(dbcreds, df_normal, df_specific, df_rectifier)
    elif dbms=="tidb":
        return write_tidb(dbcreds, df_normal, df_specific, df_rectifier)
    else:
        raise ValueError(f"DBMS não suportado: '{dbms}'")
