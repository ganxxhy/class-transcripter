"""Genera el resumen y los destacados de una clase con Claude, Gemini o un servidor compatible con OpenAI."""
import threading
from datetime import datetime

from . import almacen
from .interfaces import IAIProvider, IClassRepository
from .proveedores import (ClaudeProvider, GeminiProvider, OpenAIProvider, elegir_proveedor,
                          _con_claude, _con_gemini, _con_openai, _chat_url, _sin_additional)
from .formato_resumen import ESQUEMA, SISTEMA, sistema, extract_json, check_summary
from .config import api_key, cargar, resumen_en_pc

from application.summaries import generate_summary, _formatear, DIAS


def generar(cid, *, proveedor: IAIProvider | None = None,
            repositorio: IClassRepository = almacen):
    return generate_summary(cid, repositorio=repositorio, proveedor=proveedor,
                            load_config=cargar, get_key=api_key,
                            is_enabled=resumen_en_pc, select_provider=elegir_proveedor)


def generar_seguro(cid, log=print, *, repositorio: IClassRepository = almacen):
    try:
        if generar(cid, repositorio=repositorio) is False:
            return False
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


def pendientes(*, repositorio: IClassRepository = almacen):
    return [c["id"] for c in repositorio.listar()
            if not c.get("en_curso") and c.get("estado_resumen") in ("pendiente", "error", "generando") and c.get("n_segmentos")]
