"""Compatibility facade for existing class service consumers."""
from . import almacen
from .config import RUTA_DATOS, cargar
from application.classes import ClassService, MAX_SEGMENTOS
from infrastructure.status import read_status


class ServicioClases(ClassService):
    def __init__(self, repositorio=almacen, cargar_config=cargar, ruta_datos=RUTA_DATOS):
        super().__init__(repositorio, cargar_config, lambda: read_status(ruta_datos))
