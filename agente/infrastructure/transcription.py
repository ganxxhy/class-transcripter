"""Select an available transcription backend and recover from optional GPU backend failures."""
from pathlib import Path
from threading import Lock
from time import perf_counter

from .openvino_whisper import OpenVinoWhisper
from .vulkan_whisper import SAMPLE_RATE, VulkanWhisper
from .whisper import Transcriptor, cuda_available


class LocalTranscriber:
    def __init__(self, settings, data_directory, log=print):
        self.settings = settings
        self.log = log
        self.vulkan = VulkanWhisper(Path(data_directory) / "vulkan", settings, log)
        self.openvino = OpenVinoWhisper(Path(data_directory) / "openvino", settings, log)
        self.active = None
        self.lock = Lock()

    @property
    def modelo(self):
        """Return the loaded backend, or None; keeps the legacy UI check working."""
        return self.active

    @property
    def descripcion(self):
        active = self.active
        return active.descripcion if active is not None else "sin cargar"

    def cargar(self):
        with self.lock:
            self._load()

    def _faster_whisper(self, device):
        return Transcriptor({**self.settings, "dispositivo": device}, self.log)

    def _accelerators(self, device):
        """Optional GPU backends to try, best first; empty means plain faster-whisper."""
        if device == "openvino":
            return [("OpenVINO", self.openvino)]
        if device == "vulkan":
            return [("Vulkan", self.vulkan)]
        if device == "auto":
            return [(name, backend) for name, backend in (("OpenVINO", self.openvino), ("Vulkan", self.vulkan))
                    if backend.installed()]
        return []

    def _accelerator_name(self, backend):
        for name, candidate in (("OpenVINO", self.openvino), ("Vulkan", self.vulkan)):
            if backend is candidate:
                return name
        return None

    def _load(self):
        if self.active is not None:
            return
        device = self.settings.get("dispositivo", "auto")
        candidates = self._accelerators(device)
        if not candidates:
            backend = self._faster_whisper(device)
            backend.cargar()
            self.active = backend
            return
        if device == "auto" and cuda_available():
            cuda = self._faster_whisper("cuda")
            try:
                cuda.cargar()
            except Exception:
                self.log("CUDA no disponible tras la prueba; se intentará una GPU Intel o AMD.")
            else:
                self.active = cuda
                return
        for index, (name, backend) in enumerate(candidates):
            try:
                backend.cargar()
            except Exception as error:
                last = index == len(candidates) - 1
                self.log(f"No se pudo usar {name}: {str(error).rstrip('.')}." + (" Se usará CPU." if last else " Se probará otra opción."))
            else:
                self.active = backend
                return
        cpu = self._faster_whisper("cpu")
        cpu.cargar()
        self.active = cpu

    def transcribir(self, audio, offset_s, contexto=""):
        with self.lock:
            self._load()
            start = perf_counter()
            try:
                segments = self.active.transcribir(audio, offset_s, contexto)
            except Exception as error:
                name = self._accelerator_name(self.active)
                if name is None:
                    raise
                self.active.close()
                self.log(f"Falló {name} durante la transcripción: {error}. Se reintentará en CPU.")
                self.active = None  # if the CPU model fails to load, the next call selects a backend again
                cpu = self._faster_whisper("cpu")
                cpu.cargar()
                self.active = cpu
                start = perf_counter()  # the speed must not include loading the CPU model
                segments = cpu.transcribir(audio, offset_s, contexto)
            elapsed = max(perf_counter() - start, 1e-9)
            if len(audio) and segments:  # silent chunks skip decoding and would inflate the multiplier
                speed = len(audio) / SAMPLE_RATE / elapsed
                self.log(f"Velocidad de transcripción: {speed:.2f}× · {self.active.descripcion}")
            return segments

    def puede_aligerar(self):
        with self.lock:
            return (self.active is not None and self._accelerator_name(self.active) is None
                    and self.active.puede_aligerar())

    def aligerar(self):
        with self.lock:
            if self.active is not None and self._accelerator_name(self.active) is None:
                self.active.aligerar()
