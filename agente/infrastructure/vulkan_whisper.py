"""Persistent, optional whisper.cpp worker for Intel and AMD Vulkan GPUs."""
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
from threading import Thread
from types import SimpleNamespace

import numpy as np

from .whisper import format_segments, normalize_audio


SAMPLE_RATE = 16000
STARTUP_TIMEOUT = 120
INFERENCE_TIMEOUT = 90


def read_line(stream):
    line = stream.readline(4096)
    if not line.endswith(b"\n"):
        raise RuntimeError("Vulkan worker exited or returned an incomplete response")
    line = line[:-1].decode("utf-8")
    if line.startswith("ERROR "):
        raise RuntimeError(line[6:])
    return line


def read_segments(stream):
    kind, count = read_line(stream).split()
    count = int(count)
    if kind != "SEGMENTS" or not 0 <= count <= 4096:
        raise RuntimeError("Invalid Vulkan response header")
    segments = []
    for _ in range(count):
        start, end, silence, size = read_line(stream).split()
        size = int(size)
        if not 0 <= size <= 65536:
            raise RuntimeError("Invalid Vulkan segment size")
        content = stream.read(size)
        if len(content) != size:
            raise RuntimeError("Incomplete Vulkan segment")
        segments.append(SimpleNamespace(
            start=int(start) / 100, end=int(end) / 100,
            no_speech_prob=float(silence), text=content.decode("utf-8", errors="replace"),
        ))
    return segments


class VulkanWhisper:
    def __init__(self, directory, settings, log):
        directory = Path(directory).resolve()
        worker_name = "studio-whisper-vulkan.exe" if sys.platform == "win32" else "studio-whisper-vulkan"
        self.worker = directory / worker_name
        self.model_name = settings.get("modelo_whisper", "auto")
        if self.model_name == "auto":
            self.model_name = "large-v3-turbo"
        self.model = directory / f"ggml-{self.model_name}.bin"
        self.vad_model = directory / "ggml-silero-v6.2.0.bin"
        self.language = settings.get("idioma", "es")
        self.log = log
        self.process = None
        self.history = []
        self.descripcion = "sin cargar"

    def installed(self):
        return self.worker.is_file()

    def cargar(self):
        if not self.installed():
            raise RuntimeError(f"No se encontró el motor opcional de Vulkan en {self.worker.parent}; hay que compilarlo (README, sección Vulkan).")
        if self.model.parent != self.worker.parent or not self.model.is_file():
            raise RuntimeError(f"No se encontró el modelo Vulkan {self.model_name!r} en {self.model.parent}; descárgalo con --descargar-modelo-vulkan.")
        if not self.vad_model.is_file():
            raise RuntimeError(f"No se encontró el modelo de detección de voz para Vulkan en {self.vad_model.parent}; descárgalo con --descargar-modelo-vulkan.")
        if any(c in str(self.model) + str(self.vad_model) + self.language for c in "\r\n"):
            raise RuntimeError("Ruta del modelo o idioma no válido para Vulkan.")
        # PyInstaller can redirect library lookup to the app bundle on Linux.
        env = os.environ.copy()
        if getattr(sys, "frozen", False) and sys.platform.startswith("linux"):
            original = env.pop("LD_LIBRARY_PATH_ORIG", None)
            if original is None:
                env.pop("LD_LIBRARY_PATH", None)
            else:
                env["LD_LIBRARY_PATH"] = original
        self.process = subprocess.Popen(
            [str(self.worker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            reply = self._exchange(
                f"{self.model}\n{self.vad_model}\n{self.language}\n".encode(), read_line, STARTUP_TIMEOUT,
            )
            if not reply.startswith("READY 2 ") or not reply[8:]:
                raise RuntimeError("Versión incompatible del motor Vulkan.")
            self._infer(np.zeros(SAMPLE_RATE, dtype=np.float32), probe=True)
        except Exception:
            self.close()
            raise
        self.descripcion = f"{self.model_name} · Vulkan ({reply[8:]})"
        self.log(f"Modelo listo: {self.descripcion} · whisper.cpp")

    def _exchange(self, payload, read_response, timeout):
        process = self.process
        response = Queue(maxsize=1)

        def exchange():
            try:
                try:
                    process.stdin.write(payload)
                    process.stdin.flush()
                except BrokenPipeError:
                    # The worker may have sent a diagnostic before closing stdin.
                    pass
                response.put(read_response(process.stdout))
            except Exception as error:
                response.put(error)

        thread = Thread(target=exchange, daemon=True)
        thread.start()
        try:
            result = response.get(timeout=timeout)
        except Empty:
            self.close()
            raise RuntimeError(f"El motor Vulkan no respondió en {timeout} s.") from None
        if isinstance(result, Exception):
            raise result
        return result

    def _infer(self, audio, *, probe=False):
        pcm = np.asarray(audio, dtype="<f4")
        header = f"PROBE {len(pcm)}" if probe else str(len(pcm))
        return self._exchange(
            f"{header}\n".encode("ascii") + pcm.tobytes(), read_segments, INFERENCE_TIMEOUT,
        )

    def transcribir(self, audio, offset_s, contexto=""):
        if not len(audio):
            return []
        segments = self._infer(normalize_audio(audio))
        return format_segments(segments, len(audio) / SAMPLE_RATE, offset_s, self.history)

    def close(self):
        process, self.process = self.process, None
        if process is not None:
            process.kill()
            process.wait()
            for stream in (process.stdin, process.stdout):
                try:
                    stream.close()
                except OSError:  # BrokenPipeError when buffered input is still pending
                    pass
