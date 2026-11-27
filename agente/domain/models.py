"""Typed records matching the existing on-disk format."""
from typing import TypedDict


class Segment(TypedDict):
    ini: float
    fin: float
    texto: str


class ClassRecord(TypedDict):
    id: str
    asignatura: str
    nombre_asignatura: str
    aula: str
    modo: str
    fecha: str
    inicio: str
    fin: str | None
    en_curso: bool
    segmentos: list[Segment]
    estado_resumen: str
    resumen: dict | None
    error_resumen: str | None
