import hashlib
import requests
import pandas as pd
from io import BytesIO
from urllib.parse import quote
from typing import Optional
import clts_pcp as clts  # type: ignore


from config import (
    COL_NORMAL, COL_SPECIFIC, COL_RECTIFIER,
    GITHUB,TIMESTAMP_FILTER,VERBOSE
)
import config


#Isto sao tudo helpers
def parse_dt(x):
    try:
        ts = pd.to_datetime(
            str(x).strip(),
            dayfirst=True,
            errors="coerce"
        )
        if pd.isna(ts):
            return pd.NaT

        try:
            return (ts
                .tz_localize("Europe/Lisbon", ambiguous="infer", nonexistent="shift_forward") # type: ignore
                .tz_convert("UTC")
            )
        except Exception:
            for ambiguous in [True, False]:
                try:
                    return (ts
                        .tz_localize("Europe/Lisbon", ambiguous=ambiguous, nonexistent="shift_forward")
                        .tz_convert("UTC")
                    )
                except Exception:
                    continue
            return pd.NaT

    except Exception:
        return pd.NaT

def safe_float(val) -> Optional[float]:
    try:
        if pd.isna(val):
            return None
        return float(str(val).replace(",", ".").strip())
    except Exception:
        return None


def make_row_hash(row) -> str:
    exclude = {"_source_file"}

    vals = []

    for k in sorted(row.index):
        if k in exclude:
            continue
        v = row[k]
        if isinstance(v, pd.Timestamp):
            vals.append(v.isoformat())
        else:
            vals.append(str(v))
    raw = "|".join(vals)
    return hashlib.md5(raw.encode()).hexdigest()

def apply_ts_filter(df: pd.DataFrame, ts_filter) -> pd.DataFrame:
    if not ts_filter:
        return df

    dt_s, dt_e = ts_filter
    mask = pd.Series(True, index=df.index)

    if dt_s:
        dt_s = pd.to_datetime(dt_s,utc=True)
        mask &= df["_tstamp"] >= dt_s

    if dt_e:
        dt_e = pd.to_datetime(dt_e,utc=True)
        mask &= df["_tstamp"] <= dt_e

    filtered = df[mask].copy()

    print(  f"  Filtro timestamps: {dt_s if dt_s else 'None'} "
            f": {dt_e if dt_e else 'None'} | "
            f"{len(filtered)}/{len(df)} linhas")
    clts.elapt[f"  Filtro timestamps: {dt_s if dt_s else 'None'} "
            f": {dt_e if dt_e else 'None'} | "
            f"{len(filtered)}/{len(df)} linhas"]=clts.deltat(config.TSTART)

    return filtered



def get_file_type(cols: set) -> str:
    if COL_RECTIFIER["energia_symo_um_kwp"] in cols and COL_RECTIFIER["energia_symo_dois"] in cols:
        return "rectifiers"
    if COL_SPECIFIC["energia_symo_um"] in cols and COL_SPECIFIC["rendimento_powermeter"] in cols:
        return "specific"
    if {COL_NORMAL["datetime"], COL_NORMAL["consumida_direto"],
            COL_NORMAL["consumo"], COL_NORMAL["energia_rede"]}.issubset(cols):
        return "normal"
    return "unknown"

def _parse_normal(df_raw: pd.DataFrame, filepath: str) -> pd.DataFrame:
    C = COL_NORMAL
    df_raw["_tstamp"]           = df_raw[C["datetime"]].apply(parse_dt)
    df_raw["_consumida_direto"] = df_raw[C["consumida_direto"]].apply(safe_float)
    df_raw["_consumo"]          = df_raw[C["consumo"]].apply(safe_float)
    df_raw["_energia_rede"]     = df_raw[C["energia_rede"]].apply(safe_float)
    df_raw["_source_file"]      = filepath
    df_valid = df_raw[df_raw["_tstamp"].notna()].copy()
    if df_valid.empty:
        return df_valid
    df_valid["mes"]      = df_valid["_tstamp"].dt.strftime("%Y-%m")
    df_valid["_row_hash"] = df_valid.apply(make_row_hash, axis=1)
    return df_valid


def _parse_specific(df_raw: pd.DataFrame, filepath: str) -> pd.DataFrame:
    C  = COL_SPECIFIC
    df_raw = df_raw.iloc[1:].copy()
    df_raw["_tstamp"] = pd.to_datetime(
        df_raw[C["datetime"]].str.strip(), format="%d.%m.%Y", errors="coerce"
    )
    for col in df_raw.columns:
        if col not in [C["datetime"], "_tstamp", "_source_file"]:
            df_raw[col] = df_raw[col].apply(safe_float)
    df_raw["_source_file"] = filepath
    df_valid = df_raw[df_raw["_tstamp"].notna()].copy()
    if df_valid.empty:
        return df_valid
    df_valid["mes"]       = df_valid["_tstamp"].dt.strftime("%Y-%m")
    df_valid["_row_hash"] = df_valid.apply(make_row_hash, axis=1)
    return df_valid


def _parse_rectifier(df_raw: pd.DataFrame, filepath: str) -> pd.DataFrame:
    C  = COL_RECTIFIER
    df_raw = df_raw.iloc[1:].copy()
    df_raw["_tstamp"] = pd.to_datetime(
        df_raw[C["datetime"]].str.strip(), format="%d.%m.%Y", errors="coerce"
    )
    for col in df_raw.columns:
        if col not in [C["datetime"], "_tstamp", "_source_file"]:
            df_raw[col] = df_raw[col].apply(safe_float)
    df_raw["_source_file"] = filepath
    df_valid = df_raw[df_raw["_tstamp"].notna()].copy()
    if df_valid.empty:
        return df_valid
    df_valid["mes"]       = df_valid["_tstamp"].dt.strftime("%Y-%m")
    df_valid["_row_hash"] = df_valid.apply(make_row_hash, axis=1)
    return df_valid



def list_github_xlsx(headers: dict) -> list[str]:#serve como debug
    g = GITHUB
    
    folder_url = (
        f"https://api.github.com/repos/{g['owner']}/{g['repo']}"
        f"/contents/{quote(g['folder'])}?ref={g['branch']}"
    )
    resp = requests.get(folder_url, headers=headers)
    
    resp.raise_for_status()
    
    return [
        f["path"] for f in resp.json()
        if f["type"] == "file" and f["name"].lower().endswith(".xlsx")
    ]


def download_and_parse_all( headers: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:# Descarrega e faz o parse de todos os xlsx do GitHub.Cada DataFrame já está deduplicado e ordenado por _tstamp.
    g = GITHUB
    xlsx_files = list_github_xlsx(headers)
    
    print(f"\n{len(xlsx_files)} ficheiro(s) encontrado(s) em '{g['folder']}'")
    clts.elapt[f"\n{len(xlsx_files)} ficheiro(s) encontrado(s) em '{g['folder']}'"]=clts.deltat(config.TSTART)
    frames, frames_specific, frames_rectifier = [], [], []

    for filepath in xlsx_files:
        api_url = (
            f"https://api.github.com/repos/{g['owner']}/{g['repo']}"
            f"/contents/{quote(filepath)}?ref={g['branch']}"
        )
        
        try:
            r = requests.get(api_url, headers=headers)
            r.raise_for_status()
        except Exception as e:
            print(f"  ❌ Erro download '{filepath}': {e}")
            continue

        try:
            
            df_raw = pd.read_excel(BytesIO(r.content), sheet_name=0, header=0, dtype=str)
            df_raw.columns = (
                df_raw.columns.astype(str).str.strip().str.replace("\n", " ", regex=False)
            )
            df_raw = df_raw[df_raw.iloc[:, 0].notna()]

            file_type = get_file_type(set(df_raw.columns))
            if VERBOSE:
                print(f"'{filepath}': {file_type}")
                clts.elapt[f"'{filepath}': {file_type}"]=clts.deltat(config.TSTART) 

            if file_type == "normal":
                df = _parse_normal(df_raw, filepath)
                if not df.empty:
                    frames.append(df)

            elif file_type == "specific":
                df = _parse_specific(df_raw, filepath)
                if not df.empty:
                    frames_specific.append(df)

            elif file_type == "rectifiers":
                df = _parse_rectifier(df_raw, filepath)
                if not df.empty:
                    frames_rectifier.append(df)

            else:
                print(f"Ficheiro ignorado '{filepath}'")
                clts.elapt[f"Ficheiro ignorado '{filepath}'"]=clts.deltat(config.TSTART)

        except Exception as e:
            print(f"❌ Erro  '{filepath}': {e}")
            clts.elapt[f"❌ Erro  '{filepath}': {e}"]=clts.deltat(config.TSTART)

    # é aqui ond se aplica o filtro
    def _consolidate(frames_list, apply_filter=False) -> pd.DataFrame:
        if not frames_list:
            return pd.DataFrame()
        df = (
            pd.concat(frames_list, ignore_index=True)
            .sort_values("_tstamp")
            .reset_index(drop=True)
        )
        df = df.drop_duplicates(subset=["_row_hash"]).reset_index(drop=True)
        print(f"  Intervalo: {df['_tstamp'].min()} : {df['_tstamp'].max()}  ({len(df)} linhas)")
        #clts.elapt[f"  Intervalo: {df['_tstamp'].min()} : {df['_tstamp'].max()}  ({len(df)} linhas)"]=clts.deltat(config.TSTART)
        if apply_filter:
            df = apply_ts_filter(df, TIMESTAMP_FILTER)
        return df

    df_normal    = _consolidate(frames,apply_filter=True)
    df_specific  = _consolidate(frames_specific)
    df_rectifier = _consolidate(frames_rectifier)

    print(f"\n  Linhas a inserir - normal: {len(df_normal)} | specific: {len(df_specific)} | rectifier: {len(df_rectifier)}")
    clts.elapt[f"\n  Linhas a inserir - normal: {len(df_normal)} | specific: {len(df_specific)} | rectifier: {len(df_rectifier)}"]=clts.deltat(config.TSTART)
    return df_normal, df_specific, df_rectifier
