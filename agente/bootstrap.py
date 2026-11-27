"""Composition root for desktop and MCP entry points."""
from infrastructure.repository import JsonClassRepository
from infrastructure.audio import SoundDeviceInput
from nucleo.config import cargar, RUTA_DATOS


def build_class_service():
    from nucleo.servicio_clases import ServicioClases
    return ServicioClases(JsonClassRepository(), cargar, RUTA_DATOS)


def build_motor(log=print):
    from nucleo.motor import Motor
    from nucleo.transcripcion import Transcriptor
    return Motor(log, transcriptor=Transcriptor(cargar()["ajustes"], log=log),
                 repositorio=JsonClassRepository(), audio_input=SoundDeviceInput(),
                 load_config=cargar)
