"""Download the pre-converted OpenVINO Whisper model used by the optional OpenVINO backend."""
from pathlib import Path

REPO = "OpenVINO/whisper-large-v3-int8-ov"
REVISION = "5603442ef51120fc1d5bb6c8749d01592b14acb5"  # pinned so downloads are reproducible
MODEL_DIRECTORY = "whisper-large-v3-int8-ov"
REQUIRED_MODEL_FILES = ("config.json", "generation_config.json",
                        "openvino_encoder_model.xml", "openvino_encoder_model.bin",
                        "openvino_decoder_model.xml", "openvino_decoder_model.bin",
                        "openvino_tokenizer.xml", "openvino_tokenizer.bin",
                        "openvino_detokenizer.xml", "openvino_detokenizer.bin")


def model_complete(path):
    """True when every file the pipeline needs is present; an interrupted download leaves some missing."""
    path = Path(path)
    return all((path / name).is_file() and (path / name).stat().st_size > 0 for name in REQUIRED_MODEL_FILES)


def _snapshot_download(**kwargs):
    from huggingface_hub import snapshot_download
    return snapshot_download(**kwargs)


def download_openvino_model(directory, settings=None, log=print, downloader=_snapshot_download):
    """Fetch the model into directory unless it is already complete."""
    directory = Path(directory)
    chosen = (settings or {}).get("modelo_whisper", "auto")
    if chosen not in ("auto", "large-v3"):
        log(f"Con modelo_whisper={chosen!r} hay que colocar whisper-{chosen}-int8-ov en {directory} a mano (ver README).")
        return
    target = directory / MODEL_DIRECTORY
    if model_complete(target):
        log(f"Ya está: {MODEL_DIRECTORY}")
        return
    directory.mkdir(parents=True, exist_ok=True)
    log(f"Descargando {MODEL_DIRECTORY} (unos 1,6 GB)…")
    downloader(repo_id=REPO, revision=REVISION, local_dir=str(target))
    log(f"Listo: {MODEL_DIRECTORY}")
