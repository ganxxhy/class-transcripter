"""Servidor MCP local (stdio) para que el hub "Mis clases" (artefacto de Claude) lea las
clases guardadas en este ordenador. Lo arranca la app de escritorio de Claude.
Solo usa la biblioteca estándar de Python.
"""
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nucleo.servicio_clases import MAX_SEGMENTOS
from bootstrap import build_class_service  # noqa: E402

NOMBRE = "agente_clases"
VERSION = "1.0.0"


servicio = build_class_service()
t_estado = servicio.estado
t_listar = servicio.listar
t_leer = servicio.leer
t_guardar_resumen = servicio.guardar_resumen
t_marcar_estado_resumen = servicio.marcar_estado_resumen
t_mover = servicio.mover
t_borrar = servicio.borrar


S_ID = {"id": {"type": "string", "description": "Id de la clase"}}
TOOLS = {
    "estado": (t_estado, "Asignaturas, horario y si el agente está grabando ahora.", {}, [], True),
    "listar_clases": (t_listar, "Lista las clases guardadas (sin transcripción) con su versión.", {}, [], True),
    "leer_clase": (t_leer, f"Lee una clase con su transcripción (hasta {MAX_SEGMENTOS} segmentos desde 'desde').",
                   {**S_ID, "desde": {"type": "integer", "minimum": 0}}, ["id"], True),
    "guardar_resumen": (t_guardar_resumen, "Guarda el resumen generado de una clase.",
                        {**S_ID, "resumen": {"type": "object"}}, ["id", "resumen"], False),
    "marcar_estado_resumen": (t_marcar_estado_resumen, "Marca el estado del resumen de una clase.",
                              {**S_ID, "estado": {"type": "string", "enum": ["pendiente", "generando", "error", "vacio"]},
                               "error": {"type": "string"}}, ["id", "estado"], False),
    "mover_clase": (t_mover, "Cambia la asignatura de una clase.",
                    {**S_ID, "asignatura": {"type": "string"}}, ["id", "asignatura"], False),
    "borrar_clase": (t_borrar, "Borra una clase de este ordenador.", S_ID, ["id"], False),
}


def lista_tools():
    out = []
    for nombre, (_f, desc, props, req, solo_lectura) in TOOLS.items():
        out.append({
            "name": nombre,
            "description": desc,
            "inputSchema": {"type": "object", "properties": props, "required": req},
            "annotations": {"readOnlyHint": solo_lectura, "destructiveHint": nombre == "borrar_clase"},
        })
    return out


def responder(id_, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def manejar(msg):
    metodo, id_ = msg.get("method"), msg.get("id")
    if id_ is None:  # notificación
        return
    if metodo == "initialize":
        pv = (msg.get("params") or {}).get("protocolVersion") or "2025-06-18"
        responder(id_, {"protocolVersion": pv, "capabilities": {"tools": {}},
                        "serverInfo": {"name": NOMBRE, "version": VERSION}})
    elif metodo == "ping":
        responder(id_, {})
    elif metodo == "tools/list":
        responder(id_, {"tools": lista_tools()})
    elif metodo == "tools/call":
        p = msg.get("params") or {}
        t = TOOLS.get(p.get("name"))
        if not t:
            return responder(id_, error={"code": -32602, "message": "Herramienta desconocida"})
        try:
            res = t[0](p.get("arguments") or {})
            responder(id_, {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}],
                            "structuredContent": res, "isError": False})
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            responder(id_, {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True})
    else:
        responder(id_, error={"code": -32601, "message": f"Método no soportado: {metodo}"})


def main():
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            msg = json.loads(linea)
        except Exception:
            continue
        for m in (msg if isinstance(msg, list) else [msg]):
            manejar(m)


if __name__ == "__main__":
    main()
