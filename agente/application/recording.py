"""Motor del agente: captura audio, decide la asignatura, trocea, transcribe y guarda.

Hilos:
  micrófono (callback de sounddevice) -> cola_audio
  hilo_captura: decide la asignatura actual, corta fragmentos de ~25 s en silencios -> cola_trans
  hilo_transcripcion: Whisper -> almacen; al cerrar una clase lanza el resumen
"""
import queue
import sys
import threading
import time
from datetime import datetime

import numpy as np

from domain.ports import AudioInput, ITranscriber, IClassRepository

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


class RecordingEngine:
    def __init__(self, log, *, transcriptor: ITranscriber, repositorio: IClassRepository,
                 audio_input: AudioInput, load_config, subject_name, current_subject,
                 summary_enabled, schedule_summary, write_status, open_wave):
        self.log = log
        self.load_config = load_config
        self.audio_input = audio_input
        self.cfg = self.load_config()
        self.transcriptor = transcriptor
        self.repositorio = repositorio
        self.subject_name = subject_name
        self.current_subject = current_subject
        self.summary_enabled = summary_enabled
        self.schedule_summary = schedule_summary
        self.write_status = write_status
        self.open_wave = open_wave
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
        self._capture_stopped = threading.Event()
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
        if self.activo:
            return
        if self.transcribiendo():
            raise RuntimeError("Todavía estoy terminando de transcribir la sesión anterior. Espera un momento.")
        self.cfg = self.load_config()
        self.modo, self.asig_manual = modo, asignatura
        self._capture_stopped.clear()
        self._abrir_stream(self.cfg["ajustes"].get("microfono"))
        self.activo = True
        self._hilo_trans = threading.Thread(target=self._bucle_transcripcion, daemon=True)
        self._hilo_trans.start()
        self._hilo_cap = threading.Thread(target=self._capture_worker, daemon=True)
        self._hilo_cap.start()
        self.log(f"Modo {'automático' if modo == 'auto' else 'manual'}")

    def _abrir_stream(self, eleccion):
        self._stream, self.microfono_actual = self.audio_input.open(
            eleccion, lambda rate, data: self.cola_audio.put((rate, data)), self.log)
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
        self.estado_texto = "Terminando de transcribir…"
        try:
            self._cerrar_stream()
        finally:
            self._capture_stopped.set()

    def cambiar_asignatura(self, asignatura):
        """En modo manual: cierra la clase actual y empieza otra."""
        with self.lock:
            self.modo, self.asig_manual = "manual", asignatura

    def guardar_estado(self):
        try:
            self.write_status({"activo": self.activo, "estado": self.estado_texto,
                               "clase_id": self.clase_id, "modo": self.modo,
                               "pendientes": self.pendientes(),
                               "actualizado": datetime.now().isoformat(timespec="seconds")})
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
                n = self.subject_name(self.cfg, self.asig_manual)
                return self.asig_manual, "", f"Grabando · {n} (manual)"
        fr, prox = self.current_subject(self.cfg, datetime.now())
        if fr:
            n = self.subject_name(self.cfg, fr["asignatura"])
            return fr["asignatura"], fr.get("aula", ""), f"Grabando · {n} (automático, hasta {fr['fin_ef']:%H:%M})"
        if prox:
            n = self.subject_name(self.cfg, prox["asignatura"])
            return None, "", f"En espera · próxima clase {n} a las {prox['inicio']}"
        return None, "", "En espera · no quedan clases hoy en tu horario"

    def _abrir_clase(self, asig, aula):
        nombre = self.subject_name(self.cfg, asig)
        self.clase_id = self.repositorio.crear_clase(asig, nombre, self.modo, aula=aula)
        self.clase_asig = asig
        self.clase_muestras = 0
        self.ultimas_lineas = []
        self.log(f"Nueva clase: {nombre}")
        if self.cfg["ajustes"].get("guardar_audio"):
            self._wav = self.open_wave(self.clase_id, SR)

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

    def _capture_worker(self):
        try:
            self._bucle_captura()
        except Exception as error:
            self.log(f"Error de captura: {error}")
            self.activo = False
            try:
                self._cerrar_stream()
            except Exception as close_error:
                self.log(f"Error cerrando audio: {close_error}")
            self._capture_stopped.set()
            if self.clase_id is not None:
                self.cola_trans.put(("cerrar", self.clase_id))
        finally:
            self.cola_trans.put(("fin",))

    def _bucle_captura(self):
        buf = np.zeros(0, dtype=np.float32)
        ultimo_chequeo = 0
        objetivo = (None, "", "")
        while not self._capture_stopped.is_set() or not self.cola_audio.empty():
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
        failed_classes = set()
        while True:
            item = self.cola_trans.get()
            if item[0] == "fin":
                break
            if item[0] == "cerrar":
                cid = item[1]
                try:
                    self.repositorio.cerrar(cid)
                    if cid in failed_classes:
                        self.repositorio.actualizar(cid, estado_resumen="error", error_resumen="Transcripción incompleta: error de almacenamiento o transcripción.")
                    elif self.summary_enabled(self.load_config()):
                        self.schedule_summary(cid, self.log, repositorio=self.repositorio)
                except Exception as error:
                    self.log(f"Error cerrando clase {cid}: {error}")
                failed_classes.discard(cid)
                self.guardar_estado()
                continue
            _, cid, audio, offset = item
            try:
                segs = self.transcriptor.transcribir(audio, offset)
            except Exception as e:
                failed_classes.add(cid)
                self.log(f"Error transcribiendo: {e}")
                continue
            # Si se acumulan más de ~4 min de audio sin transcribir, el modelo es demasiado lento aquí
            if self.activo and self.pendientes() > 8 and self.transcriptor.puede_aligerar():
                try:
                    self.transcriptor.aligerar()
                except Exception as e:
                    self.log(f"No se pudo cambiar de modelo: {e}")
            if segs:
                try:
                    self.repositorio.anadir_segmentos(cid, segs)
                except Exception as error:
                    failed_classes.add(cid)
                    self.log(f"Error guardando transcripción {cid}: {error}")
                    continue
                self.ultimas_lineas = (self.ultimas_lineas + [s["texto"] for s in segs])[-40:]
        if not self.activo:
            self.estado_texto = "Parado"
            self.guardar_estado()
            self.log("Transcripción terminada.")
