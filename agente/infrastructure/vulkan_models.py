"""Download and verify the GGML models used by the optional Vulkan worker."""
import hashlib
import os
from pathlib import Path
import urllib.request

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


def _fetch(name, url, size, digest, directory, log, opener, chunk_size):
    final = directory / name
    part = directory / f"{name}.part"
    request = urllib.request.Request(url, headers={"User-Agent": "Estudio"})
    sha = hashlib.sha256()
    received = 0
    next_report = 10
    try:
        with opener(request, timeout=60) as response, open(part, "wb") as out:
            while True:
                block = response.read(chunk_size)
                if not block:
                    break
                out.write(block)
                sha.update(block)
                received += len(block)
                while size and received * 100 // size >= next_report <= 100:
                    log(f"Descargando {name}: {next_report} %")
                    next_report += 10
        if received != size or sha.hexdigest() != digest:
            raise RuntimeError(f"Descarga corrupta: {name}")
        os.replace(part, final)
    finally:
        part.unlink(missing_ok=True)


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
        _fetch(name, url, size, digest, directory, log, opener, chunk_size)
        log(f"Listo: {name}")
