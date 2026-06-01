import json
import socket
import clts_pcp as clts  # type: ignore

from data_parser import parse_all
from db_writer   import write_to_db, InsertResult
from notifier    import send_notification


hostname = socket.gethostname()
hostname_short = hostname[:4]


def run_pipeline(env: str, get_secret, user: str, context: str, config) -> InsertResult:
    clts.setcontext(context)
    clts.elapt.clear()
    clts.elapt["Setup OK"] = clts.deltat(config.TSTART)

    # 1. Download, extração e construção dos GeoJSONs
    import os
    datapath = os.environ.get("D5_DATAPATH", ".") if env != "google_colab" else "/content"

    stops_geojson, routes_geojson, tables = parse_all(datapath, config)
    if config.VERBOSE:
        clts.elapt[
            f"Parse concluído: "
            f"stops={len(tables['stops'])} | routes={len(tables['routes'])} | "
            f"trips={len(tables['trips'])} | stop_times={len(tables['stop_times'])} | "
            f"shapes={len(tables['shapes'])}"
        ] = clts.deltat(config.TSTART)

    # 2. Escrita nas bases de dados
    dblist = json.loads(get_secret(f"{user}_dblist_json"))
    if config.VERBOSE:
        print("dblist:", dblist)

    grand_total = InsertResult()

    for db_name in dblist:
        clts.elapt[f"Ligando a '{db_name}'…"] = clts.deltat(config.TSTART)
        try:
            dbcreds = json.loads(get_secret(f"{user}_{db_name}_json"))
            result  = write_to_db(
                dbcreds, tables,
                stops_geojson, routes_geojson,
                env, hostname_short, config,
            )
            grand_total += result
            clts.elapt[f"'{db_name}' ✅ - {result}"] = clts.deltat(config.TSTART)
            print(f"  [{db_name}] ✅ {result}")
        except Exception as e:
            grand_total.errors += 1
            clts.elapt[f"'{db_name}' ❌ - {e}"] = clts.deltat(config.TSTART)
            print(f"  [{db_name}] ❌ Erro: {e}")

    clts.elapt[f"Resumo: {grand_total}"] = clts.deltat(config.TSTART)
    clts.elapt["Antes do email"] = clts.deltat(config.TSTART)

    operator = config.GTFS_PREFIX.rstrip("_").upper()
    print(f"DEBUG email: env={env} | user='{user}' | addresses={config.EMAIL['addresses']}")
    # 3. Emails
    if config.EMAIL["send"] and config.EMAIL["addresses"]:
        log_text = clts.listtimes()
        subject  = f"{operator} GTFS | {context}"
        text     = log_text + "\nEsta é uma mensagem automática."
        html     = (
            "<html><body style='font-family:Montserrat;'>"
            + log_text
            + "<br><hr color=orange>Automated notification from "
            + context
            + "</body></html>"
        )
        try:
            send_notification(env, user, get_secret, subject, text, html, config.EMAIL["addresses"])
            clts.elapt["Email enviado ✅"] = clts.deltat(config.TSTART)
        except Exception as e:
            print(f"  Erro email: {e}")
            clts.elapt[f"Erro email: {e}"] = clts.deltat(config.TSTART)

    return grand_total
