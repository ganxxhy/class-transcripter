"""Motor del agente: captura audio, decide la asignatura, trocea, transcribe y guarda.

Hilos:
  micrófono (callback de sounddevice) -> cola_audio
  hilo_captura: decide la asignatura actual, corta fragmentos de ~25 s en silencios -> cola_trans
  hilo_transcripcion: Whisper -> almacen; al cerrar una clase lanza el resumen
"""
import json
import os
import queue
import sys
import threading
import time
import wave
from datetime import datetime

import numpy as np

from . import almacen, horario, resumen
from .config import RUTA_DATOS, cargar, nombre_asignatura, resumen_en_pc
from .transcripcion import Transcriptor
from .interfaces import ITranscriber, IClassRepository

SR = 16000
MIN_FRAG_S = 18     # a partir de aquí se busca un silencio para cortar
MAX_FRAG_S = 30     # corte forzado
SILENCIO_S = 0.5


def _a_16k(bloque, sr_in):
    if sr_in == SR:
        return bloque
    n = int(len(bloque) * SR / sr_in)
    if n <= 0:
        return np.zeros(0, dtype=np.float32)
    x = np.linspace(0, len(bloque) - 1, n)
    return np.interp(x, np.arange(len(bloque)), bloque).astype(np.float32)


def microfonos(refrescar=False):
    """Entradas de audio de la API por defecto (en Windows, MME; en Linux, ALSA).
    Con refrescar=True vuelve a preguntar al sistema (para micros conectados después de abrir la app)."""
    import sounddevice as sd
    if refrescar:
        try:
            sd._terminate()
            sd._initialize()
        except Exception:
            pass
    try:
        por_defecto = sd.default.device[0]
        api_def = sd.query_devices(por_defecto)["hostapi"] if por_defecto is not None and por_defecto >= 0 else 0
    except Exception:
        por_defecto, api_def = None, 0
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and d["hostapi"] == api_def:
            out.append({"indice": i, "nombre": d["name"], "defecto": i == por_defecto})
    if sys.platform.startswith("linux"):  # sound servers first, raw ALSA (hw:…) after
        out.sort(key=lambda m: SERVIDORES_SONIDO.index(m["nombre"]) if m["nombre"] in SERVIDORES_SONIDO else len(SERVIDORES_SONIDO))
    return out


# On Linux, PortAudio only exposes ALSA (and JACK). PipeWire and PulseAudio are reached through
# their ALSA plugin devices, so they are preferred by name and raw ALSA is the last resort.
SERVIDORES_SONIDO = ("pipewire", "pulse")


def _microfono_linux(lista):
    """Index of the PipeWire device, else PulseAudio, else None (the system default)."""
    for nombre in SERVIDORES_SONIDO:
        m = next((m for m in lista if m["nombre"] == nombre), None)
        if m:
            return m["indice"]
    return None


def buscar_microfono(eleccion, log=print):
    """Convierte lo guardado en config (nombre del micro, o None = el del sistema) en un índice."""
    if eleccion is None or eleccion == "":
        return _microfono_linux(microfonos()) if sys.platform.startswith("linux") else None
    for m in microfonos():
        if m["nombre"] == eleccion or m["indice"] == eleccion:
            return m["indice"]
    log(f"No encuentro el micrófono «{eleccion}»; uso el predeterminado del sistema.")
    return None


class Motor:
    def __init__(self, log=print, *, transcriptor: ITranscriber | None = None,
                 repositorio: IClassRepository = almacen):
        self.log = log
        self.cfg = cargar()
        self.transcriptor = transcriptor if transcriptor is not None else Transcriptor(self.cfg["ajustes"], log=log)
        self.repositorio = repositorio
        self.lock = threading.Lock()
        self.activo = False
        self.modo = None             # "auto" | "manual"
        self.asig_manual = None
        self.clase_id = None         # clase que se está grabando
        self.clase_asig = None
        self.clase_muestras = 0
        self.nivel = 0.0
        self.estado_texto = "Parado"
        self.ultimas_lineas = []
        self.cola_audio = queue.Queue()
        self.cola_trans = queue.Queue()
        self._hilo_trans = None
        self._hilo_cap = None
        self._stream = None
        self._wav = None
        self.cargando_modelo = False
        self.microfono_actual = ""

    # ---------- modelo ----------
    def precargar(self):
        def run():
            self.cargando_modelo = True
            try:
                self.transcriptor.cargar()
            except Exception as e:
                self.log(f"Error cargando el modelo de voz: {e}")
            finally:
                self.cargando_modelo = False
        threading.Thread(target=run, daemon=True).start()

    # ---------- control ----------
    def iniciar(self, modo, asignatura=None):
        import sounddevice as sd
        if self.activo:
            return
        if self.transcribiendo():
            raise RuntimeError("Todavía estoy terminando de transcribir la sesión anterior. Espera un momento.")
        self.cfg = cargar()
        self.modo, self.asig_manual = modo, asignatura
        self._abrir_stream(self.cfg["ajustes"].get("microfono"))
        self.activo = True
        self._hilo_trans = threading.Thread(target=self._bucle_transcripcion, daemon=True)
        self._hilo_trans.start()
        self._hilo_cap = threading.Thread(target=self._bucle_captura, daemon=True)
        self._hilo_cap.start()
        self.log(f"Modo {'automático' if modo == 'auto' else 'manual'}")

    def _abrir_stream(self, eleccion):
        import sounddevice as sd
        dev = buscar_microfono(eleccion, self.log)
        info = sd.query_devices(dev, "input")
        sr = int(info["default_samplerate"])

        def cb(indata, frames, t, status):
            self.cola_audio.put((sr, indata[:, 0].copy()))

        st = sd.InputStream(device=dev, channels=1, samplerate=sr, dtype="float32",
                            blocksize=int(sr * 0.25), callback=cb)
        st.start()
        self._stream = st
        self.microfono_actual = info["name"] + ("" if dev is not None else " (predeterminado)")
        self.log(f"Escuchando con: {self.microfono_actual}")

    def _cerrar_stream(self):
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
        finally:
            self._stream = None

    def cambiar_microfono(self, eleccion):
        """Cambia la entrada de audio. Si está grabando, sigue en la misma clase sin cortar."""
        if not self.activo:
            return
        anterior = self._stream
        self._stream = None
        try:
            self._abrir_stream(eleccion)
        except Exception:
            self._stream = anterior  # el nuevo no va: seguimos con el de antes
            raise
        try:
            anterior.stop()
            anterior.close()
        except Exception:
            pass

    def parar(self):
        if not self.activo:
            return
        self.activo = False
        self._cerrar_stream()
        if self._hilo_cap:
            self._hilo_cap.join(timeout=5)
        self.cola_trans.put(("fin",))
        self.estado_texto = "Terminando de transcribir…"

    def cambiar_asignatura(self, asignatura):
        """En modo manual: cierra la clase actual y empieza otra."""
        with self.lock:
            self.modo, self.asig_manual = "manual", asignatura

    def guardar_estado(self):
        """Deja el estado en datos/estado_agente.json para que el hub lo lea."""
        try:
            os.makedirs(RUTA_DATOS, exist_ok=True)
            tmp = os.path.join(RUTA_DATOS, "estado_agente.json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"activo": self.activo, "estado": self.estado_texto, "clase_id": self.clase_id,
                           "modo": self.modo, "pendientes": self.pendientes(),
                           "actualizado": datetime.now().isoformat(timespec="seconds")}, f, ensure_ascii=False)
            os.replace(tmp, os.path.join(RUTA_DATOS, "estado_agente.json"))
        except Exception:
            pass

    def pendientes(self):
        return self.cola_trans.qsize()

    def transcribiendo(self):
        return self._hilo_trans is not None and self._hilo_trans.is_alive()

    # ---------- captura ----------
    def _objetivo(self):
        """(asignatura, aula, texto_estado) que toca ahora mismo."""
        with self.lock:
            if self.modo == "manual":
                n = nombre_asignatura(self.cfg, self.asig_manual)
                return self.asig_manual, "", f"Grabando · {n} (manual)"
        fr, prox = horario.asignatura_actual(self.cfg, datetime.now())
        if fr:
            n = nombre_asignatura(self.cfg, fr["asignatura"])
            return fr["asignatura"], fr.get("aula", ""), f"Grabando · {n} (automático, hasta {fr['fin_ef']:%H:%M})"
        if prox:
            n = nombre_asignatura(self.cfg, prox["asignatura"])
            return None, "", f"En espera · próxima clase {n} a las {prox['inicio']}"
        return None, "", "En espera · no quedan clases hoy en tu horario"

    def _abrir_clase(self, asig, aula):
        nombre = nombre_asignatura(self.cfg, asig)
        self.clase_id = self.repositorio.crear_clase(asig, nombre, self.modo, aula=aula)
        self.clase_asig = asig
        self.clase_muestras = 0
        self.ultimas_lineas = []
        self.log(f"Nueva clase: {nombre}")
        if self.cfg["ajustes"].get("guardar_audio"):
            os.makedirs(os.path.join(RUTA_DATOS, "audio"), exist_ok=True)
            self._wav = wave.open(os.path.join(RUTA_DATOS, "audio", self.clase_id + ".wav"), "wb")
            self._wav.setnchannels(1)
            self._wav.setsampwidth(2)
            self._wav.setframerate(SR)

    def _cerrar_clase(self, buf):
        if self.clase_id is None:
            return
        if len(buf):
            self.cola_trans.put(("frag", self.clase_id, buf, self.clase_muestras / SR - len(buf) / SR))
        self.cola_trans.put(("cerrar", self.clase_id))
        if self._wav:
            self._wav.close()
            self._wav = None
        self.clase_id = None
        self.clase_asig = None

    def _bucle_captura(self):
        buf = np.zeros(0, dtype=np.float32)
        ultimo_chequeo = 0
        objetivo = (None, "", "")
        while self.activo or not self.cola_audio.empty():
            try:
                bloque = self.cola_audio.get(timeout=0.5)
            except queue.Empty:
                bloque = None
            ahora = time.time()
            if ahora - ultimo_chequeo > 2 or bloque is None:
                ultimo_chequeo = ahora
                objetivo = self._objetivo()
                self.estado_texto = objetivo[2]
                self.guardar_estado()
                if objetivo[0] != self.clase_asig:
                    self._cerrar_clase(buf)
                    buf = np.zeros(0, dtype=np.float32)
                    if objetivo[0]:
                        self._abrir_clase(objetivo[0], objetivo[1])
            if bloque is None:
                continue
            sr_in, bloque = bloque
            b = _a_16k(bloque, sr_in)
            self.nivel = float(min(1.0, np.sqrt(np.mean(b ** 2)) * 12)) if len(b) else 0.0
            if self.clase_id is None:
                continue  # fuera de horario: no se guarda nada
            if self._wav:
                self._wav.writeframes((np.clip(b, -1, 1) * 32767).astype(np.int16).tobytes())
            buf = np.concatenate([buf, b])
            self.clase_muestras += len(b)
            dur = len(buf) / SR
            if dur >= MIN_FRAG_S:
                cola = buf[-int(SILENCIO_S * SR):]
                silencio = np.sqrt(np.mean(cola ** 2)) < 0.01
                if silencio or dur >= MAX_FRAG_S:
                    offset = self.clase_muestras / SR - dur
                    self.cola_trans.put(("frag", self.clase_id, buf, offset))
                    buf = np.zeros(0, dtype=np.float32)
        self._cerrar_clase(buf)
        self.nivel = 0.0

    # ---------- transcripción ----------
    def _bucle_transcripcion(self):
        contexto = {}
        while True:
            item = self.cola_trans.get()
            if item[0] == "fin":
                break
            if item[0] == "cerrar":
                cid = item[1]
                self.repositorio.cerrar(cid)
                if resumen_en_pc(cargar()):
                    resumen.en_segundo_plano(cid, self.log, repositorio=self.repositorio)  # si no hay clave, lo resume el hub
                self.guardar_estado()
                continue
            _, cid, audio, offset = item
            try:
                segs = self.transcriptor.transcribir(audio, offset)
            except Exception as e:
                self.log(f"Error transcribiendo: {e}")
                continue
            # Si se acumulan más de ~4 min de audio sin transcribir, el modelo es demasiado lento aquí
            if self.activo and self.pendientes() > 8 and self.transcriptor.puede_aligerar():
                try:
                    self.transcriptor.aligerar()
                except Exception as e:
                    self.log(f"No se pudo cambiar de modelo: {e}")
            if segs:
                self.repositorio.anadir_segmentos(cid, segs)
                contexto[cid] = (contexto.get(cid, "") + " " + " ".join(s["texto"] for s in segs))[-400:]
                self.ultimas_lineas = (self.ultimas_lineas + [s["texto"] for s in segs])[-40:]
        if not self.activo:
            self.estado_texto = "Parado"
            self.guardar_estado()
            self.log("Transcripción terminada.")
