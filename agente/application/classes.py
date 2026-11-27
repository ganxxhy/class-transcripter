"""Class management use cases; dependencies are supplied by the caller."""
from domain.ports import IClassRepository

MAX_SEGMENTOS = 1500

def _version(c):
    r = c.get("resumen") or {}
    return f"{c.get('n_segmentos', 0)}|{c.get('estado_resumen')}|{int(bool(c.get('en_curso')))}|{c.get('asignatura')}|{r.get('generado', '')}"


class ClassService:
    def __init__(self, repository: IClassRepository, load_config, read_status):
        self.repository = repository
        self.load_config = load_config
        self.read_status = read_status

    def estado(self, _):
        cfg = self.load_config()
        agent, panel = self.read_status()
        return {"asignaturas": cfg["asignaturas"], "horario": cfg["horario"], "agente": agent, "panel": panel,
                "nombre": (cfg.get("perfil") or {}).get("nombre", "")}

    def listar(self, _):
        out = []
        for record in self.repository.listar():
            c = dict(record)
            c["version"] = _version(c)
            out.append(c)
        return {"clases": out}


    def leer(self, a):
        d = dict(self.repository.leer(a["id"]))
        desde = int(a.get("desde", 0))
        segs = d.pop("segmentos")
        d["version"] = _version({**d, "n_segmentos": len(segs)})
        return {"clase": d, "total": len(segs), "desde": desde, "segmentos": segs[desde:desde + MAX_SEGMENTOS]}


    def guardar_resumen(self, a):
        self.repository.actualizar(a["id"], resumen=a["resumen"], estado_resumen="listo", error_resumen=None)
        return {"ok": True}


    def marcar_estado_resumen(self, a):
        self.repository.actualizar(a["id"], estado_resumen=a["estado"], error_resumen=a.get("error"))
        return {"ok": True}


    def mover(self, a):
        cfg = self.load_config()
        asig = next(x for x in cfg["asignaturas"] if x["id"] == a["asignatura"])
        self.repository.actualizar(a["id"], asignatura=asig["id"], nombre_asignatura=asig["nombre"])
        return {"ok": True}


    def borrar(self, a):
        self.repository.eliminar(a["id"])
        return {"ok": True}
