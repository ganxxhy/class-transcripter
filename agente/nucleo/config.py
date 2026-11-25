"""Carga y guarda config.json (horario, asignaturas y ajustes)."""
import json
import os
import threading

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_CONFIG = os.path.join(RAIZ, "config.json")
RUTA_DATOS = os.path.join(RAIZ, "datos")

_lock = threading.Lock()

AJUSTES_POR_DEFECTO = {
    "margen_inicio_min": 5,
    "margen_descanso_min": 15,
    "margen_fin_min": 10,
    "modelo_whisper": "auto",
    "dispositivo": "auto",
    "microfono": None,
    "idioma": "es",
    "modelo_resumen": "claude-opus-5-5",
    "anthropic_api_key": "",
    "guardar_audio": False,
    "url_hub": "",
}


def cargar():
    with _lock:
        with open(RUTA_CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
    cfg.setdefault("asignaturas", [])
    cfg.setdefault("horario", [])
    aj = dict(AJUSTES_POR_DEFECTO)
    aj.update(cfg.get("ajustes") or {})
    cfg["ajustes"] = aj
    return cfg


def guardar(cfg):
    with _lock:
        tmp = RUTA_CONFIG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, RUTA_CONFIG)


def api_key(cfg):
    return (cfg["ajustes"].get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()


def nombre_asignatura(cfg, aid):
    for a in cfg["asignaturas"]:
        if a["id"] == aid:
            return a["nombre"]
    return aid or "Sin asignatura"
