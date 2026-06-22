import datetime
from env_utils import detect_environment, make_secret_getter

secret = make_secret_getter(detect_environment())
INSERT_MODE    = secret("INSERT_MODE") or "ignore" # "ignore","upsert"
CREATE_SUMMARY =  secret("CREATE_SUMMARY")  or True
tmp = secret("TIMESTAMP_FILTER")

if tmp:#Melhro maneira q arranjei para o None
    try:
        start, end = tmp.split(',')
        TIMESTAMP_FILTER = (
            datetime.datetime.strptime(start.strip(), "%Y-%m-%d"),
            datetime.datetime.strptime(end.strip(), "%Y-%m-%d")
        )
    except (ValueError, AttributeError):
        TIMESTAMP_FILTER = None 
else:
    TIMESTAMP_FILTER = None

GITHUB = {
    "owner":  "pedroccpimenta",
    "repo":   "datafiles",
    "branch": "master",
    "folder": "Fronius",
}


TABLE_NORMAL   = "energia_leituras"
TABLE_SPECIFIC = "energia_leituras_specific"
TABLE_RECTIFIER = "energia_leitura_rectificadores"
TABLE_SUMMARY_DAILY   = f"{TABLE_NORMAL}_diario"
TABLE_SUMMARY_MONTHLY = f"{TABLE_NORMAL}_mensal"

# Ficheiros que interessam
COL_NORMAL = {
    "datetime":         "Data e horário",
    "consumida_direto": "Consumida diretamente",
    "consumo":          "Consumo",
    "energia_rede":     "Energia obtida da rede elétrica",
}


COL_SPECIFIC = {
    "datetime":                   "Data e horário",
    "energia_powermeter":         "Energia | PowerMeter",
    "energia_symo_um":            "Energia | Symo 15.0-3-M (1)",
    "energia_symo_dois":          "Energia | Symo 15.0-3-M (2)",
    "energia_mpp1_powermeter":    "Energia MPP1 | PowerMeter",
    "energia_mpp1_symo_um":       "Energia MPP1 | Symo 15.0-3-M (1)",
    "energia_mpp1_symo_dois":     "Energia MPP1 | Symo 15.0-3-M (2)",
    "energia_mpp2_powermeter":    "Energia MPP2 | PowerMeter",
    "energia_mpp2_symo_um":       "Energia MPP2 | Symo 15.0-3-M (1)",
    "energia_mpp2_symo_dois":     "Energia MPP2 | Symo 15.0-3-M (2)",
    "rendimento_powermeter":      "Rendimento específico | PowerMeter",
    "rendimento_symo_um":         "Rendimento específico | Symo 15.0-3-M (1)",
    "rendimento_symo_dois":       "Rendimento específico | Symo 15.0-3-M (2)",
    "consumida_direto":           "Consumida diretamente",
    "consumo":                    "Consumo",
    "energia_rede":               "Energia obtida da rede elétrica",
    "energia_salva_bateria":      "Energia salva na bateria",
    "energia_salva_rede":         "Energia salva na rede",
    "energia_obtida_bateria":     "Energia obtida da bateria",
    "energia_obtida_rede":        "Energia obtida da rede elétrica",
}

TSTART=None
COL_RECTIFIER = {
    "datetime":          "Data e horário",
    "energia_symo_um":   "Energia por retificador alternado | Symo 15.0-3-M (1)",
    "energia_symo_dois": "Energia por retificador alternado | Symo 15.0-3-M (2)",
    "energia_symo_um_kwp":   "Energia por retificador alternado por kWp | Symo 15.0-3-M (1)",
    "energia_symo_dois_kwp": "Energia por retificador alternado por kWp | Symo 15.0-3-M (2)",
    "instalacoes_total": "Instalação total",
}
tmp_email = secret("EMAIL_SEND") or "False"
tmp_addresses  = secret("EMAIL_ADDRESSES") or ""
EMAIL = {
    "send": tmp_email.lower() == "true",
    "addresses": [a.strip() for a in tmp_addresses.split(",") if a.strip()]
}

VERBOSE     = False
DESTINATION = "-*-"
