"""Composition root for desktop and MCP entry points."""
from infrastructure.repository import JsonClassRepository
from infrastructure.audio import SoundDeviceInput
from nucleo.config import cargar, RUTA_DATOS


def build_repository():
    """Explicit test-only opt-in; production remains on JSON."""
    import os
    from pathlib import Path
    database = os.environ.get("ESTUDIO_EXPERIMENTAL_SQLITE")
    if database:
        from infrastructure.sqlite_store import SQLiteClassRepository
        path = Path(database)
        if not path.is_absolute() or not path.is_file():
            raise ValueError("Experimental SQLite requires an existing absolute database path")
        return SQLiteClassRepository(path)
    return JsonClassRepository()


def build_class_service():
    from application.classes import ClassService
    from infrastructure.status import read_status
    return ClassService(build_repository(), cargar, lambda: read_status(RUTA_DATOS))


def build_motor(log=print, repository=None):
    from application.recording import RecordingEngine
    from infrastructure.recording_files import write_status, open_wave
    from infrastructure.whisper import Transcriptor
    from nucleo import horario, resumen
    from nucleo.config import nombre_asignatura, resumen_en_pc
    repository = repository if repository is not None else build_repository()
    return RecordingEngine(log, transcriptor=Transcriptor(cargar()["ajustes"], log=log),
                           repositorio=repository, audio_input=SoundDeviceInput(),
                           load_config=cargar, subject_name=nombre_asignatura,
                           current_subject=horario.asignatura_actual,
                           summary_enabled=resumen_en_pc, schedule_summary=lambda cid, log: resumen.en_segundo_plano(cid, log, repositorio=repository),
                           write_status=lambda status: write_status(RUTA_DATOS, status),
                           open_wave=lambda cid, rate: open_wave(RUTA_DATOS, cid, rate))
