"""Asistente de la primera vez: perfil, asignaturas y horario, micrófono, resúmenes.

Es una ventana web (pywebview: Edge en Windows, Qt en Linux) para que se vea
bien. La interfaz está en asistente.html y llama a la clase Api de aquí.
Se lanza con: AgenteClases.exe --asistente   (o python app.py --asistente)
"""
import json
import os
import shutil
import sys
import threading
import urllib.parse
import webbrowser

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))

from nucleo import config  # noqa: E402

# On Linux the web windows use Qt: its wheels come from pip, so the AppImage carries everything
GUI = "qt" if sys.platform.startswith("linux") else None

REPO = "ganxxhy/class-transcripter"
URL_HUB_HTML = f"https://raw.githubusercontent.com/{REPO}/main/hub/mis-clases.html"
URL_HUB_GUIA = f"https://github.com/{REPO}/blob/main/hub/PUBLICAR.md"

PROMPT_HUB = (
    "Quiero mi propio panel \"Mis clases\" de Estudio (la app que graba y resume mis clases). "
    f"Lee las instrucciones de {URL_HUB_GUIA} y publica como artefacto el HTML de {URL_HUB_HTML} "
    "tal cual, con las capacidades que indica la guía. Cuando esté, dame el enlace."
)

PROMPT_HORARIO = (
    "Te voy a pasar una captura de mi horario de clases. Devuélveme SOLO un bloque JSON con esta forma, "
    "sin explicaciones:\n"
    '{"asignaturas": [{"id": "abreviatura corta en minúsculas", "nombre": "Nombre completo"}], '
    '"horario": [{"dia": "lunes|martes|miercoles|jueves|viernes|sabado", "inicio": "HH:MM", '
    '"fin": "HH:MM", "asignatura": "id", "aula": "aula o cadena vacía"}]}\n'
    "Una entrada en horario por cada clase de la semana. Usa las horas exactas de la captura."
)


def _hardware():
    hilos = os.cpu_count() or 4
    nvidia = False
    try:
        import ctranslate2
        nvidia = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        nvidia = bool(shutil.which("nvidia-smi"))
    if nvidia:
        auto = "Con tu gráfica NVIDIA usará el modelo más preciso."
    elif hilos >= 8:
        auto = "Usará el modelo turbo y bajará a uno ligero si tu ordenador se queda atrás."
    else:
        auto = "Usará el modelo ligero, que va bien en cualquier portátil."
    texto = f"Tu ordenador: procesador de {hilos} hilos, {'con' if nvidia else 'sin'} gráfica NVIDIA. {auto}"
    return {"hilos": hilos, "nvidia": nvidia, "texto": texto}


class Api:
    def __init__(self):
        # Ojo: pywebview expone a la página todo atributo público de esta clase, recorriéndolo
        # entero. La ventana tiene que ser privada (_ventana): si no, al recorrerla se queda colgado.
        self._stream = None
        self._nivel = 0.0
        self._ventana = None
        self._terminado = None  # "agente" | None

    # ----- datos -----
    def estado_inicial(self):
        cfg = config.cargar()
        aj = cfg["ajustes"]
        return {
            "perfil": cfg.get("perfil") or {},
            "asignaturas": cfg["asignaturas"],
            "horario": cfg["horario"],
            "ajustes": {
                "microfono": aj.get("microfono"),
                "modelo_whisper": aj.get("modelo_whisper", "auto"),
                "proveedor": aj.get("proveedor", "claude"),
                "tiene_clave": bool(config.api_key(cfg)),
                "url_hub": aj.get("url_hub", ""),
            },
            "colores": config.COLORES,
            "hardware": _hardware(),
            "prompt_horario": PROMPT_HORARIO,
            # Prueba automática (GitHub Actions): la página se cierra sola en cuanto arranca
            "so": sys.platform,
            "prueba": bool(os.environ.get("AGENTE_CLASES_PRUEBA")),
        }

    def guardar(self, datos):
        cfg = config.cargar()
        cfg["perfil"] = {"nombre": (datos.get("nombre") or "").strip(),
                         "estudios": (datos.get("estudios") or "").strip()}
        cfg["asignaturas"] = datos.get("asignaturas") or []
        cfg["horario"] = datos.get("horario") or []
        aj = cfg["ajustes"]
        aj["microfono"] = datos.get("microfono") or None
        aj["modelo_whisper"] = datos.get("modelo_whisper") or "auto"
        prov = datos.get("proveedor")
        clave = (datos.get("clave") or "").strip()
        if prov in ("claude", "gemini"):
            aj["proveedor"] = prov
            if clave:
                aj["gemini_api_key" if prov == "gemini" else "anthropic_api_key"] = clave
        if datos.get("url_hub"):
            aj["url_hub"] = datos["url_hub"].strip()
        aj["permiso_grabar"] = bool(datos.get("permiso"))
        config.guardar(cfg)
        return {"ok": True}

    # ----- micrófono -----
    def listar_micros(self, refrescar=False):
        try:
            from nucleo.motor import microfonos
            return microfonos(refrescar)
        except Exception as e:
            return {"error": str(e)}

    def iniciar_medidor(self, nombre=None):
        self.parar_medidor()
        try:
            import numpy as np
            import sounddevice as sd
            from nucleo.motor import buscar_microfono
            indice = buscar_microfono(nombre or None, log=lambda *_: None)

            def cb(datos, _frames, _t, _st):
                rms = float(np.sqrt(np.mean(np.square(datos.astype(np.float32)))) + 1e-9)
                db = 20 * np.log10(rms)  # -60 dB silencio, -10 dB fuerte
                self._nivel = max(0.0, min(1.0, (db + 60) / 50))

            try:
                self._stream = sd.InputStream(device=indice, channels=1, samplerate=16000, dtype="float32",
                                              blocksize=1600, callback=cb)
            except Exception:  # el micro no admite 16 kHz: su frecuencia propia
                self._stream = sd.InputStream(device=indice, channels=1, dtype="float32", callback=cb)
            self._stream.start()
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def nivel(self):
        return self._nivel

    def parar_medidor(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        self._stream = None
        self._nivel = 0.0

    # ----- enlaces -----
    def abrir_claude_horario(self):
        webbrowser.open("https://claude.ai/new?q=" + urllib.parse.quote(PROMPT_HORARIO))

    def abrir_claude_panel(self):
        webbrowser.open("https://claude.ai/new?q=" + urllib.parse.quote(PROMPT_HUB))

    def abrir(self, url):
        if isinstance(url, str) and url.startswith("https://"):
            webbrowser.open(url)

    def terminar(self, siguiente=None):
        self.parar_medidor()
        self._terminado = siguiente or "agente"
        if sys.platform.startswith("linux") and siguiente != "prueba":
            # What the Windows installer does: launcher + autostart, and connect Claude's desktop app
            try:
                import linux_desktop
                import registrar_mcp
                linux_desktop.install()
                registrar_mcp.registrar(log=lambda *_: None)
            except Exception:
                pass
        if siguiente == "prueba":
            os.makedirs(config.RAIZ, exist_ok=True)
            with open(os.path.join(config.RAIZ, "prueba-asistente.ok"), "w", encoding="utf-8") as f:
                f.write("ok")
        if self._ventana:
            threading.Timer(0.1, self._ventana.destroy).start()


def html():
    with open(os.path.join(AQUI, "asistente.html"), encoding="utf-8") as f:
        return f.read()


def ejecutar():
    """Abre el asistente y bloquea hasta que se cierra. Devuelve qué abrir después."""
    import webview

    api = Api()
    api._ventana = webview.create_window("Estudio", html=html(), js_api=api, width=1000, height=700,
                                        min_size=(900, 640), background_color="#CFE6FF")
    webview.start(gui=GUI)
    api.parar_medidor()
    return api._terminado


if __name__ == "__main__":
    print(json.dumps({"siguiente": ejecutar()}))
