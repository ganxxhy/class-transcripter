"""Casos de uso de clases compartidos por MCP y futuras interfaces."""
import json
import os
from . import almacen
from .config import RUTA_DATOS, cargar
from .interfaces import IClassRepository

MAX_SEGMENTOS = 1500

def _version(c):
    r = c.get("resumen") or {}
    return f"{c.get('n_segmentos', 0)}|{c.get('estado_resumen')}|{int(bool(c.get('en_curso')))}|{c.get('asignatura')}|{r.get('generado', '')}"


class ServicioClases:
    def __init__(self, repositorio: IClassRepository = almacen, cargar_config=cargar,
                 ruta_datos=RUTA_DATOS):
        self.repositorio = repositorio
        self.cargar_config = cargar_config
        self.ruta_datos = ruta_datos

    def estado(self, _):
        cfg = self.cargar_config()
        try:
            with open(os.path.join(self.ruta_datos, "estado_agente.json"), encoding="utf-8") as f:
                agente = json.load(f)
        except Exception:
            agente = {"activo": False}
        try:  # última versión del panel publicada (la apunta la app al buscar actualizaciones)
            with open(os.path.join(self.ruta_datos, "panel.json"), encoding="utf-8") as f:
                panel = json.load(f)
        except Exception:
            panel = None
        return {"asignaturas": cfg["asignaturas"], "horario": cfg["horario"], "agente": agente, "panel": panel,
                "nombre": (cfg.get("perfil") or {}).get("nombre", "")}


    def listar(self, _):
        out = []
        for c in self.repositorio.listar():
            c["version"] = _version(c)
            out.append(c)
        return {"clases": out}


    def leer(self, a):
        d = self.repositorio.leer(a["id"])
        desde = int(a.get("desde", 0))
        segs = d.pop("segmentos")
        d["version"] = _version({**d, "n_segmentos": len(segs)})
        return {"clase": d, "total": len(segs), "desde": desde, "segmentos": segs[desde:desde + MAX_SEGMENTOS]}


    def guardar_resumen(self, a):
        self.repositorio.actualizar(a["id"], resumen=a["resumen"], estado_resumen="listo", error_resumen=None)
        return {"ok": True}


    def marcar_estado_resumen(self, a):
        self.repositorio.actualizar(a["id"], estado_resumen=a["estado"], error_resumen=a.get("error"))
        return {"ok": True}


    def mover(self, a):
        cfg = self.cargar_config()
        asig = next(x for x in cfg["asignaturas"] if x["id"] == a["asignatura"])
        self.repositorio.actualizar(a["id"], asignatura=asig["id"], nombre_asignatura=asig["nombre"])
        return {"ok": True}


    def borrar(self, a):
        self.repositorio.eliminar(a["id"])
        return {"ok": True}
