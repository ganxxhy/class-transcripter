"""Select an available transcription backend and recover from Vulkan failures."""
from pathlib import Path
from threading import Lock
from time import perf_counter

from .vulkan_whisper import SAMPLE_RATE, VulkanWhisper
from .whisper import Transcriptor, cuda_available


class LocalTranscriber:
    def __init__(self, settings, data_directory, log=print):
        self.settings = settings
        self.log = log
        self.vulkan = VulkanWhisper(Path(data_directory) / "vulkan", settings, log)
        self.active = None
        self.lock = Lock()

    @property
    def descripcion(self):
        active = self.active
        return active.descripcion if active is not None else "sin cargar"

    def cargar(self):
        with self.lock:
            self._load()

    def _faster_whisper(self, device):
        return Transcriptor({**self.settings, "dispositivo": device}, self.log)

    def _load(self):
        if self.active is not None:
            return
        device = self.settings.get("dispositivo", "auto")
        if device != "vulkan" and (device != "auto" or not self.vulkan.installed()):
            backend = self._faster_whisper(device)
            backend.cargar()
            self.active = backend
            return
        if device == "auto" and cuda_available():
            cuda = self._faster_whisper("cuda")
            try:
                cuda.cargar()
            except Exception:
                self.log("CUDA no disponible tras la prueba; se intentará Vulkan.")
            else:
                self.active = cuda
                return
        try:
            self.vulkan.cargar()
        except Exception as error:
            self.log(f"No se pudo usar Vulkan: {error}. Se usará CPU.")
            cpu = self._faster_whisper("cpu")
            cpu.cargar()
            self.active = cpu
        else:
            self.active = self.vulkan

    def transcribir(self, audio, offset_s, contexto=""):
        with self.lock:
            self._load()
            start = perf_counter()
            try:
                segments = self.active.transcribir(audio, offset_s, contexto)
            except Exception as error:
                if self.active is not self.vulkan:
                    raise
                self.vulkan.close()
                self.log(f"Falló Vulkan durante la transcripción: {error}. Se reintentará en CPU.")
                self.active = self._faster_whisper("cpu")
                segments = self.active.transcribir(audio, offset_s, contexto)
            elapsed = max(perf_counter() - start, 1e-9)
            if len(audio):
                speed = len(audio) / SAMPLE_RATE / elapsed
                self.log(f"Velocidad de transcripción: {speed:.2f}× · {self.active.descripcion}")
            return segments

    def puede_aligerar(self):
        with self.lock:
            return self.active is not None and self.active is not self.vulkan and self.active.puede_aligerar()

    def aligerar(self):
        with self.lock:
            if self.active is not None and self.active is not self.vulkan:
                self.active.aligerar()
