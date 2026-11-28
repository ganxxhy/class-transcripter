"""Transcripción local con faster-whisper (no envía el audio a ningún sitio)."""
import glob
import os
import re
import sys
import numpy as np

# Frases que Whisper se inventa en silencios (muy típicas en español)
ALUCINACIONES = [
    r"amara\.org", r"subt[ií]tulos (realizados|por)", r"suscr[ií]bete", r"gracias por ver",
    r"^\W*m[uú]sica\W*$", r"^\W*aplausos\W*$", r"^\W*gracias\.?\W*$", r"www\.", r"\.com\b",
]
_ALUC = re.compile("|".join(ALUCINACIONES), re.IGNORECASE)
def _norm(t):
    return re.sub(r"[^\wáéíóúñü ]", "", t.lower()).strip()


def _limpiar(texto):
    """"¿Puedo? ¿Puedo? ¿Puedo?" o "no, no, no, no" (3 o más veces seguidas) -> una sola vez."""
    tok = texto.split()
    for n in range(1, 16):
        out, i = [], 0
        while i < len(tok):
            base = [_norm(x) for x in tok[i:i + n]]
            k = 1
            while len(base) == n and [_norm(x) for x in tok[i + k * n:i + (k + 1) * n]] == base:
                k += 1
            if k >= 3:
                out.extend(tok[i:i + n])
                i += k * n
            else:
                out.append(tok[i])
                i += 1
        tok = out
    return " ".join(tok)


def _cpu_potente():
    return (os.cpu_count() or 4) >= 8


def _preparar_dlls_cuda():
    """Las bibliotecas CUDA instaladas por pip (nvidia-cublas/cudnn) no se encuentran solas (Windows y Linux)."""
    if sys.platform.startswith("linux"):
        # Linux: preload the pip-installed CUDA libraries so ctranslate2 finds them
        import ctypes
        for base in sys.path:
            for lib in sorted(glob.glob(os.path.join(base, "nvidia", "*", "lib", "lib*.so*"))):
                try:
                    ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass
        return
    if sys.platform != "win32":
        return
    for base in sys.path:
        for d in glob.glob(os.path.join(base, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(d)
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
            except Exception:
                pass


def cuda_available():
    """Check CTranslate2 after making bundled CUDA libraries discoverable."""
    _preparar_dlls_cuda()
    return _cuda_device_present()


def _cuda_device_present():
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


class Transcriptor:
    def __init__(self, ajustes, log=print):
        self.ajustes = ajustes
        self.log = log
        self.modelo = None
        self.descripcion = "sin cargar"
        self.nombre_modelo = None
        self.device = None
        self._ultimos = []  # textos recientes, para quitar bucles de repetición

    def puede_aligerar(self):
        return self.device == "cpu" and self.nombre_modelo not in ("small", "base", "tiny") \
            and self.ajustes.get("modelo_whisper", "auto") == "auto"

    def aligerar(self):
        """Pasa al modelo pequeño si el ordenador no da abasto con el grande."""
        from faster_whisper import WhisperModel
        self.log("El ordenador no da abasto con el modelo grande; paso al modelo 'small'.")
        self.modelo = WhisperModel("small", device="cpu", compute_type="int8")
        self.nombre_modelo = "small"
        self.descripcion = "small · CPU"

    def cargar(self):
        from faster_whisper import WhisperModel

        _preparar_dlls_cuda()
        disp = self.ajustes.get("dispositivo", "auto")
        nombre = self.ajustes.get("modelo_whisper", "auto")
        intentos = []
        if disp == "auto" and not _cuda_device_present():
            disp = "cpu"
        if disp in ("auto", "cuda"):
            intentos.append(("cuda", "float16", "large-v3-turbo" if nombre == "auto" else nombre))
        if disp in ("auto", "cpu"):
            if nombre == "auto":
                # Portátiles con 8 hilos o más: turbo (mucho más fiel). Si no da abasto, el motor baja a "small".
                if _cpu_potente():
                    intentos.append(("cpu", "int8", "large-v3-turbo"))
                intentos.append(("cpu", "int8", "small"))
            else:
                intentos.append(("cpu", "int8", nombre))
        ultimo_error = None
        for device, ctype, modelo in intentos:
            try:
                self.log(f"Cargando modelo de voz '{modelo}' en {device.upper()}… (la primera vez se descarga)")
                m = WhisperModel(modelo, device=device, compute_type=ctype)
                # Prueba real: en GPU los fallos de cuDNN salen al transcribir, no al cargar
                list(m.transcribe(np.zeros(16000, dtype=np.float32), language="es")[0])
                self.modelo = m
                self.nombre_modelo, self.device = modelo, device
                self.descripcion = f"{modelo} · {device.upper()}"
                self.log(f"Modelo listo: {self.descripcion}")
                return
            except Exception as e:  # probamos la siguiente opción
                ultimo_error = e
                self.log(f"No se pudo usar {device.upper()}: {e}")
        raise RuntimeError(f"No se pudo cargar ningún modelo de voz: {ultimo_error}")

    def transcribir(self, audio, offset_s, contexto=""):
        """audio: float32 mono 16 kHz. Devuelve segmentos con tiempos relativos a la clase.
        (contexto se ignora: pasarle el texto anterior hacía que Whisper lo repitiera en bucle.)"""
        if self.modelo is None:
            self.cargar()
        audio = normalize_audio(audio)
        params = dict(
            language=self.ajustes.get("idioma", "es"),
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 700, "speech_pad_ms": 300},
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.2,  # descarta texto que se repite a sí mismo
            log_prob_threshold=-1.0,
            repetition_penalty=1.1,
        )
        try:
            segs, _info = self.modelo.transcribe(audio, word_timestamps=True, hallucination_silence_threshold=2.0, **params)
            segs = list(segs)
        except TypeError:  # faster-whisper antiguo
            segs, _info = self.modelo.transcribe(audio, **params)
            segs = list(segs)
        return format_segments(segs, len(audio) / 16000, offset_s, self._ultimos)


def normalize_audio(audio):
    """Boost quiet recordings for either Whisper backend."""
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if 0.002 < peak < 0.5:
        return (audio * min(8.0, 0.7 / peak)).astype(np.float32)
    return audio


def format_segments(segments, duration, offset, recent):
    """Filter decoder output and preserve the stored class-relative timestamps."""
    output = []
    for segment in segments:
        text = _limpiar(segment.text.strip())
        if not text or _ALUC.search(text) or segment.no_speech_prob > 0.8:
            continue
        if getattr(segment, "compression_ratio", 0) > 2.4 or getattr(segment, "avg_logprob", 0) < -1.2:
            continue
        normalized = _norm(text)
        if len(normalized) > 12 and normalized in recent:
            continue
        recent.append(normalized)
        del recent[:-6]
        start = max(0.0, segment.start)
        end = min(segment.end, duration)
        output.append({
            "ini": round(offset + start, 1),
            "fin": round(offset + max(start, end), 1),
            "texto": text,
        })
    return output
