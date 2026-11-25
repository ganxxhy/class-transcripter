"""Decide qué asignatura toca en cada momento según el horario.

Reglas:
- Una clase empieza a contar `margen_inicio_min` antes de su hora (si no pisa a la anterior).
- Si la siguiente clase empieza poco después (descanso <= `margen_descanso_min`),
  la clase actual sigue "activa" hasta que empieza la siguiente: el descanso se queda
  en la clase anterior y el cambio se hace justo a la hora de la nueva.
- Si no hay clase justo después, se sigue grabando `margen_fin_min` por si el profe se alarga.
- Fuera de esas franjas no se graba (modo espera).
"""
from datetime import datetime, timedelta

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
_NORMALIZA = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouaeiou")


def _dia(nombre):
    return nombre.strip().lower().translate(_NORMALIZA)


def _hm(fecha, texto):
    h, m = texto.split(":")
    return fecha.replace(hour=int(h), minute=int(m), second=0, microsecond=0)


def franjas_del_dia(cfg, ahora):
    """Lista de franjas de hoy con inicio/fin reales y efectivos, ordenadas."""
    aj = cfg["ajustes"]
    m_ini = timedelta(minutes=aj["margen_inicio_min"])
    m_desc = timedelta(minutes=aj["margen_descanso_min"])
    m_fin = timedelta(minutes=aj["margen_fin_min"])
    hoy = DIAS[ahora.weekday()]
    base = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    fr = []
    for h in cfg["horario"]:
        if _dia(h["dia"]) != hoy:
            continue
        fr.append({**h, "ini": _hm(base, h["inicio"]), "fin_dt": _hm(base, h["fin"])})
    fr.sort(key=lambda x: x["ini"])
    prev_fin_ef = None
    for i, f in enumerate(fr):
        sig = fr[i + 1] if i + 1 < len(fr) else None
        ini_ef = f["ini"] - m_ini
        if prev_fin_ef is not None and ini_ef < prev_fin_ef:
            ini_ef = prev_fin_ef
        if sig is not None and sig["ini"] - f["fin_dt"] <= m_desc:
            fin_ef = sig["ini"]
        else:
            fin_ef = f["fin_dt"] + m_fin
            if sig is not None and fin_ef > sig["ini"] - m_ini:
                fin_ef = max(f["fin_dt"], sig["ini"] - m_ini)
        f["ini_ef"], f["fin_ef"] = ini_ef, fin_ef
        prev_fin_ef = fin_ef
    return fr


def asignatura_actual(cfg, ahora=None):
    """Devuelve (franja | None, proxima_franja | None)."""
    ahora = ahora or datetime.now()
    fr = franjas_del_dia(cfg, ahora)
    actual = next((f for f in fr if f["ini_ef"] <= ahora < f["fin_ef"]), None)
    proxima = next((f for f in fr if f["ini_ef"] > ahora), None)
    return actual, proxima
