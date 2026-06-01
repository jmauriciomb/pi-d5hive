import os
import importlib
import subprocess
import sys


def detect_environment() -> str:
    """Detecta o ambiente de execução: google_colab | render | flask"""
    try:
        import google.colab  # type: ignore
        return "google_colab"
    except ImportError:
        pass
    if os.getenv("RENDER") == "true":
        return "render"
    return "flask"


def ensure_packages(packages_dict: dict) -> None:
    for import_name, pip_name in packages_dict.items():
        try:
            importlib.import_module(import_name)
            print(f"OK: {import_name}")
        except ImportError:
            print(f"A instalar: {pip_name}")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", pip_name, "--quiet"
            ])


def make_secret_getter(env: str):
    if env == "google_colab":
        from google.colab import userdata  # type: ignore
        return userdata.get
    else:
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv