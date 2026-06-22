import json
import socket
import config

import clts_pcp as clts  # type: ignore

from config import (
    INSERT_MODE, TIMESTAMP_FILTER,
    GITHUB, EMAIL, VERBOSE, DESTINATION,
)
from data_parser import download_and_parse_all
from db_writer   import write_to_db, InsertResult
from notifier    import send_notification


hostname = socket.gethostname()


def _github_headers(get_secret, user: str) -> dict:
    creds = json.loads(get_secret(f"{user}_github_json"))
    return {
        "Authorization": f"token {creds['key']}",
        "Accept":  "application/vnd.github.v3.raw",
    }
def run_pipeline( env: str,get_secret, user: str, context: str) -> InsertResult:

    clts.setcontext(context)
    clts.elapt["Setup OK"] = clts.deltat(config.TSTART)
    headers_github = _github_headers(get_secret, user)
   

    df_normal, df_specific, df_rectifier = download_and_parse_all(headers_github)

    clts.elapt[f"Parse concluído: normal={len(df_normal)} | "
               f"specific={len(df_specific)} | "
               f"rectifier={len(df_rectifier)}"] = clts.deltat(config.TSTART)

    dblist = json.loads(get_secret(f"{user}_dblist_json"))# sao as bds .atualmente so crate e mongo
    if VERBOSE:
        print("dblist:", dblist)

    grand_total = InsertResult()

    for db_name in dblist:
        clts.elapt[f"Ligando a '{db_name}'…"] = clts.deltat(config.TSTART)
        try:
            dbcreds = json.loads(get_secret(f"{user}_{db_name}_json"))
            result  = write_to_db(dbcreds, df_normal, df_specific, df_rectifier)
            grand_total += result
            clts.elapt[f"'{db_name}' ✅ - {result}"] = clts.deltat(config.TSTART)
            print(f"  [{db_name}] ✅ {result}")
        except Exception as e:
            grand_total.errors += 1
            clts.elapt[f"'{db_name}' ❌ - {e}"] = clts.deltat(config.TSTART)
            print(f"  [{db_name}] ❌ Erro: {e}")

    clts.elapt[f"Resumo: {grand_total}"] = clts.deltat(config.TSTART)
    clts.elapt["Antes do email"] = clts.deltat(config.TSTART)

    #EMails
    if EMAIL["send"] and EMAIL["addresses"]:
        log_text = clts.listtimes()
        subject  = f"Fronius {context}"
        text     = log_text + "\nEsta é uma mensagem automática."
        html     = (
            "<html><body style='font-family:Montserrat;'>"
            + log_text
            + "<br><hr color=orange>Automated notification from "
            + context
            + "</body></html>"
        )
        try:
            send_notification(env, get_secret, subject, text, html, EMAIL["addresses"])
            clts.elapt["Email enviado ✅"] = clts.deltat(config.TSTART)
        except Exception as e:
            print(f"  Erro email: {e}")
            clts.elapt[f"Erro email: {e}"] = clts.deltat(config.TSTART)

    return grand_total