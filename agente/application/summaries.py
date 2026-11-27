"""Summary generation use case, independent of concrete providers."""
from datetime import datetime
from domain.ports import IAIProvider, IClassRepository

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

def _formatear(segmentos):
    lineas = []
    for s in segmentos:
        t = int(s["ini"])
        lineas.append(f"[{t // 60:02d}:{t % 60:02d}] {s['texto']}")
    return "\n".join(lineas)


def generate_summary(cid, *, repositorio: IClassRepository, proveedor: IAIProvider | None,
                     load_config, get_key, is_enabled, select_provider):
    cfg = load_config()
    clave = get_key(cfg)
    if not is_enabled(cfg):
        raise RuntimeError("Falta configurar los resúmenes (clave o servidor) en el asistente.")
    d = repositorio.leer(cid)
    if not d["segmentos"]:
        repositorio.actualizar(cid, estado_resumen="vacio", error_resumen="No se transcribió nada en esta clase.")
        return
    claim = getattr(repositorio, "claim_summary", None)
    if claim is not None:
        if not claim(cid):
            return False
    else:
        repositorio.actualizar(cid, estado_resumen="generando", error_resumen=None)
    ini = datetime.fromisoformat(d["inicio"])
    usuario = (
        f"Asignatura: {d['nombre_asignatura']}\n"
        f"Fecha de la clase: {DIAS[ini.weekday()]} {ini:%Y-%m-%d}, empezó a las {ini:%H:%M}\n\n"
        f"Transcripción:\n{_formatear(d['segmentos'])}"
    )
    proveedor = proveedor if proveedor is not None else select_provider(cfg)
    res, modelo = proveedor.generar(cfg, clave, usuario)
    res["generado"] = datetime.now().isoformat(timespec="seconds")
    res["modelo"] = modelo
    repositorio.actualizar(cid, estado_resumen="listo", resumen=res, error_resumen=None)
    return True

