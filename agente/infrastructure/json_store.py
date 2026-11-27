"""Guarda cada clase como un JSON en datos/clases/. Se escribe tras cada fragmento,
así que si el ordenador se apaga a mitad de clase no se pierde lo transcrito."""
import json
import os
from infrastructure.file_lock import FileLock
from datetime import datetime

from nucleo.config import RUTA_DATOS

DIR_CLASES = os.path.join(RUTA_DATOS, "clases")
RUTA_ESTADO = os.path.join(RUTA_DATOS, "estado.json")
_lock = FileLock(os.path.join(RUTA_DATOS, '.storage.lock'))


def _ruta(cid):
    if not cid or "/" in cid or "\\" in cid or ".." in cid:
        raise ValueError("id no válido")
    return os.path.join(DIR_CLASES, cid + ".json")


def _escribir(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def crear_clase(asignatura, nombre, modo, inicio=None, aula=""):
    inicio = inicio or datetime.now()
    cid = f"{inicio:%Y-%m-%d_%H%M%S}_{asignatura}"
    datos = {
        "id": cid,
        "asignatura": asignatura,
        "nombre_asignatura": nombre,
        "aula": aula,
        "modo": modo,
        "fecha": f"{inicio:%Y-%m-%d}",
        "inicio": inicio.isoformat(timespec="seconds"),
        "fin": None,
        "en_curso": True,
        "segmentos": [],
        "estado_resumen": "pendiente",
        "resumen": None,
        "error_resumen": None,
    }
    with _lock.hold():
        _escribir(_ruta(cid), datos)
    return cid


def leer(cid):
    with _lock.hold():
        with open(_ruta(cid), encoding="utf-8") as f:
            return json.load(f)


def actualizar(cid, **campos):
    with _lock.hold():
        d = leer(cid)
        d.update(campos)
        _escribir(_ruta(cid), d)
        return d


def anadir_segmentos(cid, segmentos):
    if not segmentos:
        return
    with _lock.hold():
        d = leer(cid)
        d["segmentos"].extend(segmentos)
        _escribir(_ruta(cid), d)


def cerrar(cid, fin=None):
    fin = fin or datetime.now()
    return actualizar(cid, fin=fin.isoformat(timespec="seconds"), en_curso=False)


def listar(incluir_segmentos=False):
    out = []
    if not os.path.isdir(DIR_CLASES):
        return out
    for nombre in sorted(os.listdir(DIR_CLASES), reverse=True):
        if not nombre.endswith(".json"):
            continue
        try:
            d = leer(nombre[:-5])
        except Exception:
            continue
        if not incluir_segmentos:
            segs = d.pop("segmentos", [])
            d["n_segmentos"] = len(segs)
            d["palabras"] = sum(len(s["texto"].split()) for s in segs)
            d["duracion_s"] = int(segs[-1]["fin"]) if segs else 0
        out.append(d)
    return out


def eliminar(cid):
    with _lock.hold():
        os.remove(_ruta(cid))


def clases_abiertas_huerfanas():
    """Clases marcadas en curso de una ejecución anterior que se cortó."""
    return [c["id"] for c in listar() if c.get("en_curso")]


# Estado de los destacados (marcar como hecho)
def leer_estado():
    try:
        with open(RUTA_ESTADO, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"hechos": []}


def marcar_hecho(clave, hecho):
    with _lock.hold():
        st = leer_estado()
        s = set(st.get("hechos", []))
        (s.add if hecho else s.discard)(clave)
        st["hechos"] = sorted(s)
        _escribir(RUTA_ESTADO, st)
        return st
