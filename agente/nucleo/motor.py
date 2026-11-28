"""Compatibility facade for the recording engine."""
from . import almacen, horario, resumen
from .config import RUTA_DATOS, cargar, nombre_asignatura, resumen_en_pc
from .transcripcion import Transcriptor
from application.recording import RecordingEngine, SR, MIN_FRAG_S, MAX_FRAG_S, SILENCIO_S, _a_16k
from infrastructure.recording_files import write_status, open_wave
from infrastructure.audio import SoundDeviceInput, microfonos, buscar_microfono, _microfono_linux, SERVIDORES_SONIDO


class Motor(RecordingEngine):
    def __init__(self, log=print, *, transcriptor=None, repositorio=almacen,
                 audio_input=None, load_config=None):
        loader = load_config or cargar
        if transcriptor is None:
            from bootstrap import build_transcriber  # lazy: keeps the composition root out of module import
            transcriptor = build_transcriber(loader()["ajustes"], log)
        super().__init__(log, transcriptor=transcriptor,
                         repositorio=repositorio, audio_input=audio_input if audio_input is not None else SoundDeviceInput(),
                         load_config=loader, subject_name=nombre_asignatura,
                         current_subject=horario.asignatura_actual,
                         summary_enabled=lambda cfg: resumen_en_pc(cfg),
                         schedule_summary=lambda *args, **kwargs: resumen.en_segundo_plano(*args, **kwargs),
                         write_status=lambda status: write_status(RUTA_DATOS, status),
                         open_wave=lambda cid, rate: open_wave(RUTA_DATOS, cid, rate))
