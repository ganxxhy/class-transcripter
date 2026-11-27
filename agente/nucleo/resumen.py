"""Genera el resumen y los destacados de una clase con Claude, Gemini o un servidor compatible con OpenAI."""
import threading
from datetime import datetime

from . import almacen
from .interfaces import IAIProvider, IClassRepository
from .proveedores import (ClaudeProvider, GeminiProvider, OpenAIProvider, elegir_proveedor,
                          _con_claude, _con_gemini, _con_openai, _chat_url, _sin_additional)
from .formato_resumen import ESQUEMA, SISTEMA, sistema, extract_json, check_summary
from .config import api_key, cargar, resumen_en_pc

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

def _formatear(segmentos):
    lineas = []
    for s in segmentos:
        t = int(s["ini"])
        lineas.append(f"[{t // 60:02d}:{t % 60:02d}] {s['texto']}")
    return "\n".join(lineas)


def generar(cid, *, proveedor: IAIProvider | None = None,
            repositorio: IClassRepository = almacen):
    """Genera el resumen de una clase y lo guarda. Lanza excepción si falla."""
    cfg = cargar()
    clave = api_key(cfg)
    if not resumen_en_pc(cfg):
        raise RuntimeError("Falta configurar los resúmenes (clave o servidor) en el asistente.")
    d = repositorio.leer(cid)
    if not d["segmentos"]:
        repositorio.actualizar(cid, estado_resumen="vacio", error_resumen="No se transcribió nada en esta clase.")
        return
    repositorio.actualizar(cid, estado_resumen="generando", error_resumen=None)
    ini = datetime.fromisoformat(d["inicio"])
    usuario = (
        f"Asignatura: {d['nombre_asignatura']}\n"
        f"Fecha de la clase: {DIAS[ini.weekday()]} {ini:%Y-%m-%d}, empezó a las {ini:%H:%M}\n\n"
        f"Transcripción:\n{_formatear(d['segmentos'])}"
    )
    proveedor = proveedor if proveedor is not None else elegir_proveedor(cfg)
    res, modelo = proveedor.generar(cfg, clave, usuario)
    res["generado"] = datetime.now().isoformat(timespec="seconds")
    res["modelo"] = modelo
    repositorio.actualizar(cid, estado_resumen="listo", resumen=res, error_resumen=None)


def generar_seguro(cid, log=print, *, repositorio: IClassRepository = almacen):
    try:
        generar(cid, repositorio=repositorio)
        log(f"Resumen listo: {cid}")
        return True
    except Exception as e:
        log(f"No se pudo resumir {cid}: {e}")
        try:
            repositorio.actualizar(cid, estado_resumen="error", error_resumen=str(e))
        except Exception:
            pass
        return False


def en_segundo_plano(cid, log=print, *, repositorio: IClassRepository = almacen):
    threading.Thread(target=generar_seguro, args=(cid, log),
                     kwargs={"repositorio": repositorio}, daemon=True).start()


def pendientes():
    return [c["id"] for c in almacen.listar()
            if not c.get("en_curso") and c.get("estado_resumen") in ("pendiente", "error", "generando") and c.get("n_segmentos")]
