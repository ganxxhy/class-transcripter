"""Download and verify the GGML models used by the optional Vulkan worker."""
from pathlib import Path
import urllib.request

from .downloads import fetch_verified

WHISPER_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{}"
VAD_URL = "https://huggingface.co/ggml-org/whisper-vad/resolve/main/{}"

TURBO = "ggml-large-v3-turbo.bin"
VAD = "ggml-silero-v6.2.0.bin"

# (filename, url, size in bytes, sha256), taken from the Hugging Face LFS metadata.
VULKAN_MODELS = (
    (TURBO, WHISPER_URL.format(TURBO), 1624555275,
     "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69"),
    (VAD, VAD_URL.format(VAD), 885098,
     "2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987"),
)


def download_vulkan_models(directory, settings=None, log=print,
                           opener=urllib.request.urlopen, chunk_size=1 << 20):
    """Fetch missing models into directory; files of the expected size are kept."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    chosen = (settings or {}).get("modelo_whisper", "auto")
    for name, url, size, digest in VULKAN_MODELS:
        if name == TURBO and chosen not in ("auto", "large-v3-turbo"):
            log(f"Con modelo_whisper={chosen!r} hay que colocar ggml-{chosen}.bin en {directory} a mano (ver README).")
            continue
        final = directory / name
        if final.is_file() and final.stat().st_size == size:
            log(f"Ya está: {name}")
            continue
        log(f"Descargando {name}…")
        fetch_verified(name, url, size, digest, directory, log, opener, chunk_size)
        log(f"Listo: {name}")
