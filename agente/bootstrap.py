"""Composition root for desktop and MCP entry points."""
from infrastructure.repository import JsonClassRepository
from infrastructure.audio import SoundDeviceInput
from nucleo.config import cargar, RUTA_DATOS


def build_class_service():
    from application.classes import ClassService
    from infrastructure.status import read_status
    return ClassService(JsonClassRepository(), cargar, lambda: read_status(RUTA_DATOS))


def build_motor(log=print):
    from application.recording import RecordingEngine
    from infrastructure.recording_files import write_status, open_wave
    from infrastructure.whisper import Transcriptor
    from nucleo import horario, resumen
    from nucleo.config import nombre_asignatura, resumen_en_pc
    return RecordingEngine(log, transcriptor=Transcriptor(cargar()["ajustes"], log=log),
                           repositorio=JsonClassRepository(), audio_input=SoundDeviceInput(),
                           load_config=cargar, subject_name=nombre_asignatura,
                           current_subject=horario.asignatura_actual,
                           summary_enabled=resumen_en_pc, schedule_summary=resumen.en_segundo_plano,
                           write_status=lambda status: write_status(RUTA_DATOS, status),
                           open_wave=lambda cid, rate: open_wave(RUTA_DATOS, cid, rate))
