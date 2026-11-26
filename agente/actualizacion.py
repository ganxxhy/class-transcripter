"""Busca versiones nuevas en GitHub Releases, avisa y actualiza.

- buscar(): consulta la última versión publicada (sin cuenta, la API pública de GitHub).
- AgenteClases.exe --buscar-actualizacion: si hay una versión más nueva (y no la has
  descartado), abre una ventana con las novedades y los botones Actualizar / Ahora no /
  Saltar esta versión. Si no hay nada nuevo, no abre nada.
- AgenteClases.exe --novedades: después de actualizar, enseña qué ha cambiado (una vez).
Actualizar = descargar el instalador de la versión nueva y ejecutarlo en modo silencioso:
cierra el agente, instala encima conservando clases y ajustes, y lo vuelve a abrir.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request

from nucleo import config
from version import VERSION

REPO = "ganxxhy/class-transcripter"
API = f"https://api.github.com/repos/{REPO}/releases"
AQUI = os.path.dirname(os.path.abspath(__file__))


def _tupla(v):
    """'v1.2.10' -> (1, 2, 10). Lo que no sea número cuenta como 0."""
    partes = re.findall(r"\d+", str(v).split("-")[0])
    return tuple(int(p) for p in (partes + ["0", "0", "0"])[:3])


def es_mas_nueva(remota, local=VERSION):
    if str(local).endswith("-dev"):
        return False  # desde el código fuente no se actualiza
    return _tupla(remota) > _tupla(local)


def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "AgenteClases"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _resumen(release):
    asset = next((a for a in release.get("assets", []) if a["name"].lower().endswith("-instalador.exe")), None)
    return {
        "version": release.get("tag_name", "").lstrip("v"),
        "titulo": release.get("name") or release.get("tag_name", ""),
        "notas": release.get("body") or "",
        "fecha": (release.get("published_at") or "")[:10],
        "url": release.get("html_url", ""),
        "instalador": asset["browser_download_url"] if asset else "",
        "tamano": asset["size"] if asset else 0,
    }


def buscar():
    """Última versión publicada, o None si no hay ninguna (o no hay internet)."""
    try:
        return _resumen(_get(API + "/latest"))
    except Exception:
        return None


def notas_de(version):
    try:
        return _resumen(_get(f"{API}/tags/v{version}"))
    except Exception:
        return None


RAW = f"https://raw.githubusercontent.com/{REPO}"
GUIA_PANEL = "hub/PUBLICAR.md"
HTML_PANEL = "hub/mis-clases.html"


def _notas_panel(notas):
    """Las líneas de la sección '### Panel' de las notas, si la hay."""
    out, dentro = [], False
    for linea in notas.replace("\r", "").split("\n"):
        if re.match(r"^#{2,3}\s", linea):
            dentro = linea.strip().lower().lstrip("#").strip() == "panel"
            continue
        if linea.strip() == "---":
            break
        if dentro and linea.strip():
            out.append(linea.strip().lstrip("-* ").strip())
    return out


def revisar_panel(info=None):
    """Apunta en datos/panel.json la versión del panel "Mis clases" de la última release.
    El panel lo lee (por el conector o leyendo la carpeta) y, si la suya es más vieja,
    ofrece actualizarlo con un clic. Sin internet no toca nada."""
    info = info or buscar()
    if not info or not info.get("version"):
        return None
    tag = "v" + info["version"]
    try:
        req = urllib.request.Request(f"{RAW}/{tag}/{HTML_PANEL}", headers={"User-Agent": "AgenteClases"})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", "replace")
        m = re.search(r'VERSION_PANEL\s*=\s*"([^"]+)"', html)
        if not m:
            return None
        panel = {
            "version": m.group(1),
            "release": info["version"],
            "html": f"{RAW}/{tag}/{HTML_PANEL}",
            "guia": f"{RAW}/{tag}/{GUIA_PANEL}",
            "notas": _notas_panel(info.get("notas", "")),
        }
        os.makedirs(config.RUTA_DATOS, exist_ok=True)
        ruta = os.path.join(config.RUTA_DATOS, "panel.json")
        with open(ruta + ".tmp", "w", encoding="utf-8") as f:
            json.dump(panel, f, ensure_ascii=False, indent=1)
        os.replace(ruta + ".tmp", ruta)
        return panel
    except Exception:
        return None


def _ajuste(clave, valor=None):
    cfg = config.cargar()
    if valor is None:
        return cfg["ajustes"].get(clave)
    cfg["ajustes"][clave] = valor
    config.guardar(cfg)


class Api:
    def __init__(self, info, modo):
        self._info = info
        self._modo = modo  # "aviso" | "novedades"
        self._ventana = None  # privada: pywebview recorre los atributos públicos
        self._estado = {"estado": "parado", "hecho": 0, "total": info.get("tamano", 0), "error": ""}

    def datos(self):
        return {"modo": self._modo, "actual": VERSION, **self._info}

    def ahora_no(self):
        self._cerrar()

    def saltar(self):
        _ajuste("version_saltada", self._info["version"])
        self._cerrar()

    def abrir_web(self):
        import webbrowser
        if self._info.get("url", "").startswith("https://"):
            webbrowser.open(self._info["url"])

    def actualizar(self):
        if self._estado["estado"] == "descargando":
            return self._estado
        self._estado.update(estado="descargando", hecho=0, error="")
        threading.Thread(target=self._descargar_e_instalar, daemon=True).start()
        return self._estado

    def progreso(self):
        return self._estado

    def _descargar_e_instalar(self):
        e = self._estado
        try:
            url = self._info.get("instalador")
            if not url:
                raise RuntimeError("Esta versión no tiene instalador.")
            destino = os.path.join(tempfile.gettempdir(), f"AgenteClases-{self._info['version']}-instalador.exe")
            req = urllib.request.Request(url, headers={"User-Agent": "AgenteClases"})
            with urllib.request.urlopen(req, timeout=60) as r, open(destino + ".part", "wb") as f:
                e["total"] = int(r.headers.get("Content-Length") or e["total"] or 0)
                while True:
                    bloque = r.read(256 * 1024)
                    if not bloque:
                        break
                    f.write(bloque)
                    e["hecho"] += len(bloque)
            os.replace(destino + ".part", destino)
            e["estado"] = "instalando"
            # El instalador cierra el agente, actualiza y lo vuelve a abrir solo
            subprocess.Popen([destino, "/SILENT", "/SP-", "/NOCANCEL", "/NORESTART"],
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
            threading.Timer(1.0, self._cerrar).start()
        except Exception as ex:
            e["estado"] = "error"
            e["error"] = str(ex)[:300]

    def cerrar(self):
        self._cerrar()

    def _cerrar(self):
        if self._ventana:
            self._ventana.destroy()


def _ventana(info, modo):
    import webview
    api = Api(info, modo)
    with open(os.path.join(AQUI, "asistente", "actualizacion.html"), encoding="utf-8") as f:
        html = f.read()
    api._ventana = webview.create_window("Estudio", html=html, js_api=api, width=640, height=600,
                                         min_size=(520, 480), background_color="#CFE6FF")
    webview.start()


def comprobar_y_avisar(forzar=False):
    """--buscar-actualizacion: abre la ventana solo si hay algo nuevo que no se haya saltado."""
    info = buscar()
    revisar_panel(info)
    if not info or not es_mas_nueva(info["version"]):
        return
    if not forzar and _ajuste("version_saltada") == info["version"]:
        return
    _ventana(info, "aviso")


def novedades_si_toca():
    """--novedades: tras actualizar, enseña una vez qué ha cambiado en esta versión."""
    vista = _ajuste("ultima_version_vista")
    if VERSION.endswith("-dev") or vista == VERSION:
        return
    _ajuste("ultima_version_vista", VERSION)
    if not vista:
        return  # primera instalación: no hay "novedades" que contar
    info = notas_de(VERSION)
    if info and info.get("notas"):
        _ventana(info, "novedades")


if __name__ == "__main__":
    print(json.dumps(buscar(), ensure_ascii=False, indent=1))
    sys.exit(0)
