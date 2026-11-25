import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agente"))
from nucleo import horario  # noqa: E402
from nucleo.config import AJUSTES_POR_DEFECTO  # noqa: E402

def _c(dia, ini, fin, a):
    return {"dia": dia, "inicio": ini, "fin": fin, "asignatura": a, "aula": ""}


# Horario de ejemplo para las pruebas (no depende de config.json)
CFG = {
    "asignaturas": [],
    "ajustes": dict(AJUSTES_POR_DEFECTO),
    "horario": [
        _c("lunes", "10:50", "12:30", "lf"), _c("lunes", "12:40", "14:20", "tal"),
        _c("lunes", "15:00", "16:40", "est"), _c("lunes", "16:50", "18:30", "papi"),
        _c("lunes", "18:40", "20:20", "vsie"),
        _c("miercoles", "16:50", "18:30", "si"), _c("miercoles", "18:40", "20:20", "sd"),
        _c("viernes", "15:00", "16:40", "vsie"), _c("viernes", "16:50", "18:30", "papi"),
    ],
}


def toca(fecha_hora):
    fr, prox = horario.asignatura_actual(CFG, datetime.fromisoformat(fecha_hora))
    return (fr["asignatura"] if fr else None), (prox["asignatura"] if prox else None)


# 2026-11-23 es lunes, 24 martes, 25 miércoles, 26 jueves, 27 viernes, 28 sábado
def test_lunes():
    assert toca("2026-11-23T10:30") == (None, "lf")
    assert toca("2026-11-23T10:46") == ("lf", "tal")      # 5 min antes empieza
    assert toca("2026-11-23T12:35") == ("lf", "tal")      # descanso: sigue en la anterior
    assert toca("2026-11-23T12:40") == ("tal", "est")     # cambia justo a la hora
    assert toca("2026-11-23T14:25") == ("tal", "est")     # margen fin (10 min)
    assert toca("2026-11-23T14:31") == (None, "est")      # comida: espera
    assert toca("2026-11-23T14:56") == ("est", "papi")
    assert toca("2026-11-23T16:20") == ("est", "papi")
    assert toca("2026-11-23T16:49") == ("est", "papi")
    assert toca("2026-11-23T16:50") == ("papi", "vsie")
    assert toca("2026-11-23T20:29") == ("vsie", None)
    assert toca("2026-11-23T20:31") == (None, None)


def test_miercoles_y_viernes():
    assert toca("2026-11-25T16:20") == (None, "si")
    assert toca("2026-11-25T18:39") == ("si", "sd")
    assert toca("2026-11-25T18:40")[0] == "sd"
    assert toca("2026-11-27T16:45") == ("vsie", "papi")
    assert toca("2026-11-27T17:00") == ("papi", None)


def test_finde():
    assert toca("2026-11-28T17:00") == (None, None)


if __name__ == "__main__":
    test_lunes(); test_miercoles_y_viernes(); test_finde()
    print("OK")
