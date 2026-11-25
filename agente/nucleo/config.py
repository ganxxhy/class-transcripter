"""Carga y guarda config.json (perfil, horario, asignaturas y ajustes).

Dónde se guardan los datos:
- App instalada (.exe): en Documentos\\AgenteClases del usuario, porque la carpeta del
  programa (Archivos de programa) no se puede escribir. El hub "Mis clases" la busca ahí.
- Desde el código fuente: junto al código, como siempre.
- La variable de entorno AGENTE_CLASES_DATOS manda sobre las dos.
"""
import json
import os
import sys
import threading

CONGELADA = bool(getattr(sys, "frozen", False))
# Carpeta del programa (donde están el .exe o app.py y los recursos)
if CONGELADA:
    PROGRAMA = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    PROGRAMA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _documentos():
    """Carpeta Documentos real (puede estar en OneDrive)."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return buf.value
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Documents")


if os.environ.get("AGENTE_CLASES_DATOS"):
    RAIZ = os.environ["AGENTE_CLASES_DATOS"]
elif CONGELADA:
    RAIZ = os.path.join(_documentos(), "AgenteClases")
else:
    RAIZ = PROGRAMA

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
    # Resúmenes en el PC (opcional): "claude" o "gemini", cada uno con su clave
    "proveedor": "claude",
    "modelo_resumen": "claude-opus-5-5",
    "anthropic_api_key": "",
    "modelo_gemini": "gemini-flash-latest",
    "gemini_api_key": "",
    "guardar_audio": False,
    "url_hub": "",
}

COLORES = ["#2f5bd3", "#c25a1f", "#0f8a6a", "#8a3fb8", "#b07e00", "#c2366b", "#0e7c8c", "#5a6b1f",
           "#3d4fa8", "#a8432e"]


def existe():
    return os.path.exists(RUTA_CONFIG)


def vacia():
    return {"perfil": {"nombre": "", "estudios": ""}, "asignaturas": [], "horario": [],
            "ajustes": dict(AJUSTES_POR_DEFECTO)}


def cargar():
    with _lock:
        try:
            with open(RUTA_CONFIG, encoding="utf-8") as f:
                cfg = json.load(f)
        except FileNotFoundError:
            cfg = {}
    cfg.setdefault("perfil", {"nombre": "", "estudios": ""})
    cfg.setdefault("asignaturas", [])
    cfg.setdefault("horario", [])
    aj = dict(AJUSTES_POR_DEFECTO)
    aj.update(cfg.get("ajustes") or {})
    cfg["ajustes"] = aj
    return cfg


def guardar(cfg):
    with _lock:
        os.makedirs(RAIZ, exist_ok=True)
        tmp = RUTA_CONFIG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, RUTA_CONFIG)


def api_key(cfg):
    """Clave del proveedor elegido para resumir en el PC ("" si no hay)."""
    aj = cfg["ajustes"]
    if aj.get("proveedor") == "gemini":
        return (aj.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or "").strip()
    return (aj.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()


def nombre_asignatura(cfg, aid):
    for a in cfg["asignaturas"]:
        if a["id"] == aid:
            return a["nombre"]
    return aid or "Sin asignatura"
