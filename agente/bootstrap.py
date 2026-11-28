"""Composition root for desktop and MCP entry points."""
from infrastructure.audio import SoundDeviceInput
from nucleo.config import cargar, RUTA_DATOS


def build_repository():
    """Open mandatory SQLite storage, migrating legacy data on first use."""
    from infrastructure.storage_activation import ensure_sqlite
    from infrastructure.sqlite_store import SQLiteClassRepository
    return SQLiteClassRepository(ensure_sqlite(RUTA_DATOS))


def build_class_service():
    from application.classes import ClassService
    from infrastructure.status import read_status
    return ClassService(build_repository(), cargar, lambda: read_status(RUTA_DATOS))


def prefetch_speech_model(settings=None, log=print):
    """Download the faster-whisper model that CPU fallback relies on."""
    from infrastructure.whisper import Transcriptor
    settings = dict(cargar()["ajustes"] if settings is None else settings)
    if settings.get("dispositivo") in ("vulkan", "openvino"):
        settings["dispositivo"] = "auto"
    Transcriptor(settings, log).cargar()


def build_transcriber(settings=None, log=print):
    from infrastructure.transcription import LocalTranscriber
    if settings is None:
        settings = cargar()["ajustes"]
    return LocalTranscriber(settings, RUTA_DATOS, log)


def download_vulkan_models(log=print):
    from pathlib import Path
    from infrastructure.vulkan_models import download_vulkan_models as download
    download(Path(RUTA_DATOS) / "vulkan", cargar()["ajustes"], log)


def download_openvino_model(log=print):
    from pathlib import Path
    from infrastructure.openvino_models import download_openvino_model as download
    download(Path(RUTA_DATOS) / "openvino", cargar()["ajustes"], log)


def build_motor(log=print, repository=None):
    from application.recording import RecordingEngine
    from infrastructure.recording_files import write_status, open_wave
    from nucleo import horario, resumen
    from nucleo.config import nombre_asignatura, resumen_en_pc
    repository = repository if repository is not None else build_repository()
    return RecordingEngine(log, transcriptor=build_transcriber(log=log),
                           repositorio=repository, audio_input=SoundDeviceInput(),
                           load_config=cargar, subject_name=nombre_asignatura,
                           current_subject=horario.asignatura_actual,
                           summary_enabled=resumen_en_pc, schedule_summary=lambda cid, log: resumen.en_segundo_plano(cid, log, repositorio=repository),
                           write_status=lambda status: write_status(RUTA_DATOS, status),
                           open_wave=lambda cid, rate: open_wave(RUTA_DATOS, cid, rate))
