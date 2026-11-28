"""Optional OpenVINO Whisper backend for Intel integrated and discrete GPUs."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from .openvino_models import model_complete
from .openvino_runtime import activate_runtime
from .whisper import format_segments, normalize_audio

SAMPLE_RATE = 16000
SILENCE_PEAK = 0.002  # below this the chunk is silence; Whisper would only hallucinate on it


def detect_gpu():
    """Return (device id, device name) of the first OpenVINO GPU, or raise."""
    import openvino as ov
    core = ov.Core()
    gpus = [device for device in core.available_devices if device == "GPU" or device.startswith("GPU.")]
    if not gpus:
        raise RuntimeError("OpenVINO no encuentra ninguna GPU Intel compatible.")
    return gpus[0], core.get_property(gpus[0], "FULL_DEVICE_NAME")


def create_pipeline(model_directory, device):
    import openvino_genai
    return openvino_genai.WhisperPipeline(str(model_directory), device)


class OpenVinoWhisper:
    def __init__(self, directory, settings, log, pipeline_factory=create_pipeline, gpu_probe=detect_gpu):
        self.directory = Path(directory).resolve()
        name = settings.get("modelo_whisper", "auto")
        self.model_name = "large-v3" if name == "auto" else name
        self.model = self.directory / f"whisper-{self.model_name}-int8-ov"
        self.language = settings.get("idioma", "es")
        self.log = log
        self.pipeline_factory = pipeline_factory
        self.gpu_probe = gpu_probe
        self.pipeline = None
        self.config = None
        self.history = []
        self.descripcion = "sin cargar"
        self.runtime_problem = None

    def installed(self):
        self.runtime_problem = activate_runtime(self.directory)  # makes a downloaded acceleration pack importable
        return self.runtime_problem is None and importlib.util.find_spec("openvino_genai") is not None

    def ready(self):
        """True when the package and the complete model are both available."""
        return self.installed() and self.model.parent == self.directory and model_complete(self.model)

    def cargar(self):
        if not self.installed():
            raise RuntimeError(self.runtime_problem or
                               "Falta el motor opcional de OpenVINO (Ajustes → Activar aceleración Intel, o pip install openvino-genai).")
        if self.model.parent != self.directory or not model_complete(self.model):
            raise RuntimeError(
                f"No se encontró el modelo OpenVINO {self.model_name!r} completo en {self.directory}; "
                "descárgalo desde Ajustes → Activar aceleración Intel o con --descargar-modelo-openvino.")
        device, device_name = self.gpu_probe()
        pipeline = self.pipeline_factory(self.model, device)
        config = pipeline.get_generation_config()
        if self.language != "auto":
            config.language = f"<|{self.language}|>"
        config.task = "transcribe"
        config.return_timestamps = True
        # A first real call surfaces GPU compilation and driver failures at startup, not mid-class.
        pipeline.generate(np.zeros(SAMPLE_RATE, dtype=np.float32).tolist(), config)
        self.pipeline, self.config = pipeline, config
        self.descripcion = f"{self.model_name} int8 · OpenVINO ({device_name})"
        self.log(f"Modelo listo: {self.descripcion} · openvino-genai")

    def transcribir(self, audio, offset_s, contexto=""):
        if not len(audio) or float(np.max(np.abs(audio))) < SILENCE_PEAK:
            return []
        pcm = normalize_audio(audio).astype(np.float32)
        result = self.pipeline.generate(pcm.tolist(), self.config)
        segments = [SimpleNamespace(start=chunk.start_ts, end=chunk.end_ts, no_speech_prob=0.0, text=chunk.text)
                    for chunk in result.chunks]
        return format_segments(segments, len(audio) / SAMPLE_RATE, offset_s, self.history)

    def close(self):
        self.pipeline = self.config = None
