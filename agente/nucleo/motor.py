"""Compatibility facade for the recording engine."""
from . import almacen, horario, resumen
from .config import RUTA_DATOS, cargar, nombre_asignatura, resumen_en_pc
from .transcripcion import Transcriptor
from application.recording import RecordingEngine, SR, MIN_FRAG_S, MAX_FRAG_S, SILENCIO_S, _a_16k
from infrastructure.audio import SoundDeviceInput, microfonos, buscar_microfono, _microfono_linux, SERVIDORES_SONIDO


class Motor(RecordingEngine):
    def __init__(self, log=print, *, transcriptor=None, repositorio=almacen,
                 audio_input=None, load_config=None):
        loader = load_config or cargar
        super().__init__(log, transcriptor=transcriptor if transcriptor is not None else Transcriptor(loader()["ajustes"], log=log),
                         repositorio=repositorio, audio_input=audio_input if audio_input is not None else SoundDeviceInput(),
                         load_config=loader, subject_name=nombre_asignatura,
                         current_subject=horario.asignatura_actual,
                         summary_enabled=lambda cfg: resumen_en_pc(cfg),
                         schedule_summary=lambda *args, **kwargs: resumen.en_segundo_plano(*args, **kwargs),
                         data_path=RUTA_DATOS)
