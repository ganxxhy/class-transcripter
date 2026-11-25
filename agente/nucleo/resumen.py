"""Genera el resumen y los destacados de una clase con la API de Claude."""
import json
import threading
from datetime import datetime

from . import almacen
from .config import api_key, cargar

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

ESQUEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string", "description": "Tema principal de la clase en pocas palabras"},
        "resumen": {"type": "string", "description": "Resumen COMPLETO de toda la clase, en orden, con líneas '## Tema' como títulos de sección y \\n entre párrafos"},
        "puntos_clave": {"type": "array", "items": {"type": "string"}},
        "conceptos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"termino": {"type": "string"}, "explicacion": {"type": "string"}},
                "required": ["termino", "explicacion"],
                "additionalProperties": False,
            },
        },
        "destacados": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string", "enum": ["examen", "trabajo", "entrega", "fecha", "aviso", "comentario"]},
                    "titulo": {"type": "string"},
                    "detalle": {"type": "string"},
                    "fecha_iso": {"type": "string", "description": "AAAA-MM-DD si se puede deducir; si no, cadena vacía"},
                    "importancia": {"type": "string", "enum": ["alta", "media"]},
                    "minuto": {"type": "string", "description": "Marca [mm:ss] aproximada donde se dijo"},
                    "cita": {"type": "string", "description": "Frase literal (o casi) del profesor"},
                },
                "required": ["tipo", "titulo", "detalle", "fecha_iso", "importancia", "minuto", "cita"],
                "additionalProperties": False,
            },
        },
        "tareas": {"type": "array", "items": {"type": "string"}, "description": "Cosas que el alumno tiene que hacer"},
        "calidad_audio": {"type": "string", "enum": ["buena", "regular", "mala"]},
    },
    "required": ["titulo", "resumen", "puntos_clave", "conceptos", "destacados", "tareas", "calidad_audio"],
    "additionalProperties": False,
}

SISTEMA = """Eres el asistente de estudio de {quien}.
Recibes la transcripción automática de una clase grabada con el micrófono de su portátil. La transcripción tiene errores de reconocimiento, frases cortadas y ruido: interpreta con sentido común y no inventes nada que no se diga.

Tu trabajo:
- resumen: cubrir TODA la clase, de principio a fin y en orden, para que pueda estudiar con él sin escuchar la grabación. Incluye cada tema que se explique, cómo se explica, los ejemplos, los ejercicios resueltos, las preguntas de los alumnos con su respuesta y las digresiones con contenido. No te saltes partes ni lo reduzcas a una idea general. Organízalo por temas con una línea "## Nombre del tema" antes de cada bloque. La longitud va con la clase: una clase normal de 1 h 40 min suele necesitar entre 8 y 20 párrafos. Ignora charlas de alumnos que no sean de la clase.
- Lo importante va APARTE, en "destacados" (puede estar también en el resumen).
- Sacar los puntos clave y los conceptos con una explicación breve.
- Detectar TODO lo que pueda importar para la nota, como "destacados":
  · examen: exámenes, parciales, pruebas, qué entra, formato, si se puede llevar algo.
  · trabajo / entrega: prácticas, proyectos, entregas, requisitos, fechas límite, cómo se entrega.
  · fecha: cualquier fecha relevante (clases que no hay, cambios de aula, tutorías…).
  · aviso: cambios, normas, cosas que el profe pide.
  · comentario: frases del profesor del tipo "esto es importante", "esto entra", "fijaos bien", "esto lo pregunto siempre", pistas sobre el examen.
  Marca importancia "alta" para exámenes, entregas con fecha y cualquier cosa que el profesor diga que entra o es importante. Si no hay destacados, devuelve la lista vacía: no rellenes por rellenar.
- fecha_iso: convierte fechas relativas ("el jueves que viene", "dentro de dos semanas") usando la fecha de la clase. Si no se puede saber, deja "".
- tareas: lo que el alumno tiene que hacer antes de la próxima clase o para una entrega.
- calidad_audio: "mala" si gran parte de la transcripción es ininteligible."""



def sistema():
    """Instrucciones con el perfil del usuario (config.json -> perfil)."""
    try:
        from .config import cargar
        perfil = cargar().get("perfil") or {}
    except Exception:
        perfil = {}
    nombre = (perfil.get("nombre") or "").strip()
    estudios = (perfil.get("estudios") or "").strip()
    quien = nombre or "un estudiante universitario"
    if estudios:
        quien += f", que estudia {estudios}"
    return SISTEMA.replace("{quien}", quien)


def _formatear(segmentos):
    lineas = []
    for s in segmentos:
        t = int(s["ini"])
        lineas.append(f"[{t // 60:02d}:{t % 60:02d}] {s['texto']}")
    return "\n".join(lineas)


def generar(cid):
    """Genera el resumen de una clase y lo guarda. Lanza excepción si falla."""
    cfg = cargar()
    clave = api_key(cfg)
    if not clave:
        raise RuntimeError("Falta la clave de la API (Ajustes en la app).")
    d = almacen.leer(cid)
    if not d["segmentos"]:
        almacen.actualizar(cid, estado_resumen="vacio", error_resumen="No se transcribió nada en esta clase.")
        return
    almacen.actualizar(cid, estado_resumen="generando", error_resumen=None)
    ini = datetime.fromisoformat(d["inicio"])
    usuario = (
        f"Asignatura: {d['nombre_asignatura']}\n"
        f"Fecha de la clase: {DIAS[ini.weekday()]} {ini:%Y-%m-%d}, empezó a las {ini:%H:%M}\n\n"
        f"Transcripción:\n{_formatear(d['segmentos'])}"
    )
    if cfg["ajustes"].get("proveedor") == "gemini":
        texto, modelo = _con_gemini(cfg, clave, usuario)
    else:
        texto, modelo = _con_claude(cfg, clave, usuario)
    res = json.loads(texto)
    res["generado"] = datetime.now().isoformat(timespec="seconds")
    res["modelo"] = modelo
    almacen.actualizar(cid, estado_resumen="listo", resumen=res, error_resumen=None)


def _con_claude(cfg, clave, usuario):
    import anthropic

    client = anthropic.Anthropic(api_key=clave)
    peticion = dict(
        model=cfg["ajustes"]["modelo_resumen"],
        max_tokens=16000,
        system=sistema(),
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": ESQUEMA}},
        messages=[{"role": "user", "content": usuario}],
    )
    try:
        # Si el modelo principal rechaza la petición, la API la reintenta con otro modelo.
        r = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **peticion)
    except (anthropic.BadRequestError, TypeError):  # SDK antiguo o parámetro no admitido
        r = client.messages.create(**peticion)
    if r.stop_reason == "refusal":
        raise RuntimeError("El modelo no ha querido resumir esta clase.")
    if r.stop_reason == "max_tokens":
        raise RuntimeError("El resumen se cortó por longitud.")
    return next(b.text for b in r.content if b.type == "text"), r.model


def _sin_additional(esq):
    """Gemini no acepta additionalProperties en el esquema."""
    if isinstance(esq, dict):
        return {k: _sin_additional(v) for k, v in esq.items() if k != "additionalProperties"}
    if isinstance(esq, list):
        return [_sin_additional(v) for v in esq]
    return esq


def _con_gemini(cfg, clave, usuario):
    import urllib.error
    import urllib.request

    modelo = cfg["ajustes"].get("modelo_gemini") or "gemini-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    cuerpo = {
        "systemInstruction": {"parts": [{"text": sistema()}]},
        "contents": [{"role": "user", "parts": [{"text": usuario}]}],
        "generationConfig": {"responseMimeType": "application/json",
                             "responseJsonSchema": _sin_additional(ESQUEMA), "maxOutputTokens": 16000},
    }

    def pedir(c):
        req = urllib.request.Request(url, data=json.dumps(c).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": clave})
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read().decode("utf-8"))

    try:
        d = pedir(cuerpo)
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise RuntimeError(f"Gemini respondió {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
        # Versión de la API sin responseJsonSchema: pedimos JSON y el esquema va en las instrucciones
        cuerpo["generationConfig"].pop("responseJsonSchema")
        cuerpo["systemInstruction"]["parts"][0]["text"] += "\n\nResponde SOLO con un JSON que cumpla este esquema:\n" + json.dumps(ESQUEMA, ensure_ascii=False)
        d = pedir(cuerpo)
    cand = (d.get("candidates") or [{}])[0]
    if cand.get("finishReason") == "MAX_TOKENS":
        raise RuntimeError("El resumen se cortó por longitud.")
    partes = (cand.get("content") or {}).get("parts") or []
    texto = "".join(p.get("text", "") for p in partes).strip()
    if not texto:
        raise RuntimeError(f"Gemini no devolvió resumen ({cand.get('finishReason', 'sin motivo')}).")
    return texto, d.get("modelVersion", modelo)


def generar_seguro(cid, log=print):
    try:
        generar(cid)
        log(f"Resumen listo: {cid}")
        return True
    except Exception as e:
        log(f"No se pudo resumir {cid}: {e}")
        try:
            almacen.actualizar(cid, estado_resumen="error", error_resumen=str(e))
        except Exception:
            pass
        return False


def en_segundo_plano(cid, log=print):
    threading.Thread(target=generar_seguro, args=(cid, log), daemon=True).start()


def pendientes():
    return [c["id"] for c in almacen.listar()
            if not c.get("en_curso") and c.get("estado_resumen") in ("pendiente", "error", "generando") and c.get("n_segmentos")]
