"""Explicit adapter for the existing JSON class store."""
from . import json_store as almacen


class JsonClassRepository:
    crear_clase = staticmethod(almacen.crear_clase)
    leer = staticmethod(almacen.leer)
    actualizar = staticmethod(almacen.actualizar)
    anadir_segmentos = staticmethod(almacen.anadir_segmentos)
    cerrar = staticmethod(almacen.cerrar)
    listar = staticmethod(almacen.listar)
    eliminar = staticmethod(almacen.eliminar)
    claim_summary = staticmethod(almacen.claim_summary)

    clases_abiertas_huerfanas = staticmethod(almacen.clases_abiertas_huerfanas)
    leer_estado = staticmethod(almacen.leer_estado)
    marcar_hecho = staticmethod(almacen.marcar_hecho)
