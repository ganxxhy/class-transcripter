"""Genera el resumen y los destacados de una clase con Claude, Gemini o un servidor compatible con OpenAI."""
import json
import re
import threading
from datetime import datetime

from . import almacen
from .interfaces import IAIProvider, IClassRepository
from .config import api_key, cargar, resumen_en_pc

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


def extract_json(text):
    """Pull a JSON object out of a model reply (tolerates code fences and surrounding text)."""
    text = (text or "").strip()
    candidates = [text]
    for m in re.finditer(r"```(?:json)?\s*(.*?)```", text, re.S | re.I):
        candidates.append(m.group(1).strip())
    a, b = text.find("{"), text.rfind("}")
    if a != -1 and b > a:
        candidates.append(text[a:b + 1])
    for c in candidates:
        try:
            d = json.loads(c)
        except ValueError:
            continue
        if isinstance(d, dict):
            return d
    raise ValueError("la respuesta no contiene un JSON válido")


def check_summary(res):
    """Check the fields required by ESQUEMA and tidy up small slips. Raises ValueError if unusable."""
    faltan = [k for k in ESQUEMA["required"] if k not in res]
    if faltan:
        raise ValueError("faltan los campos: " + ", ".join(faltan))
    for k in ("puntos_clave", "conceptos", "destacados", "tareas"):
        if res[k] is None:
            res[k] = []
        if not isinstance(res[k], list):
            raise ValueError(f"el campo {k} debería ser una lista")
    for k in ("titulo", "resumen"):
        if not isinstance(res[k], str):
            raise ValueError(f"el campo {k} debería ser texto")
    if res["calidad_audio"] not in ("buena", "regular", "mala"):
        res["calidad_audio"] = "regular"
    return res


def _chat_url(base_url):
    url = base_url.strip().rstrip("/")
    return url if url.endswith("/chat/completions") else url + "/chat/completions"


def _con_openai(cfg, clave, usuario):
    import socket
    import urllib.error
    import urllib.request

    aj = cfg["ajustes"]
    base = (aj.get("openai_base_url") or "").strip()
    modelo = (aj.get("modelo_openai") or "").strip()
    if "TU_ID_DE_CUENTA" in base:
        raise RuntimeError("Pon tu ID de cuenta de Cloudflare en la dirección del servidor.")
    url = _chat_url(base)
    instrucciones = (sistema() + "\n\nResponde SOLO con un objeto JSON (sin texto antes ni después ni bloques de código) "
                     "que cumpla este esquema:\n" + json.dumps(ESQUEMA, ensure_ascii=False))
    mensajes = [{"role": "system", "content": instrucciones}, {"role": "user", "content": usuario}]
    cuerpo = {"model": modelo, "messages": mensajes, "temperature": 0.2, "max_tokens": 16000}
    headers = {"Content-Type": "application/json"}
    if clave:
        headers["Authorization"] = "Bearer " + clave

    def limpio(t):
        return t.replace(clave, "***") if clave else t

    def pedir():
        req = urllib.request.Request(url, data=json.dumps(cuerpo).encode("utf-8"), method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read().decode("utf-8"))

    def llamar():
        ajustes = 0
        while True:
            try:
                return pedir()
            except urllib.error.HTTPError as e:
                detalle = e.read().decode("utf-8", "replace")
                # Some servers reject max_tokens / temperature: adapt once each and retry
                if e.code == 400 and ajustes < 2:
                    if "max_tokens" in detalle and "max_tokens" in cuerpo:
                        cuerpo["max_completion_tokens"] = cuerpo.pop("max_tokens")
                        ajustes += 1
                        continue
                    if "temperature" in detalle and "temperature" in cuerpo:
                        cuerpo.pop("temperature")
                        ajustes += 1
                        continue
                raise RuntimeError(limpio(f"El servidor respondió {e.code}: {detalle[:500]}"))
            except (socket.timeout, TimeoutError):
                raise RuntimeError("El servidor tardó demasiado en responder.")
            except urllib.error.URLError as e:
                raise RuntimeError(limpio(f"No se pudo conectar con {url} ({e.reason}). ¿Está abierto el servidor?"))

    def leer(d):
        eleccion = (d.get("choices") or [{}])[0]
        if eleccion.get("finish_reason") == "length":
            raise RuntimeError("El resumen se cortó por longitud.")
        contenido = (eleccion.get("message") or {}).get("content")
        if isinstance(contenido, list):
            contenido = "".join(p.get("text", "") for p in contenido if isinstance(p, dict))
        contenido = (contenido or "").strip()
        if not contenido:
            raise RuntimeError("El modelo no devolvió resumen.")
        return contenido

    d = llamar()
    texto = leer(d)
    try:
        return check_summary(extract_json(texto)), d.get("model") or modelo
    except ValueError as e:
        mensajes.append({"role": "assistant", "content": texto})
        mensajes.append({"role": "user", "content": f"Tu respuesta no es válida ({e}). Devuelve SOLO el JSON completo con todos los campos."})
    d = llamar()
    try:
        return check_summary(extract_json(leer(d))), d.get("model") or modelo
    except ValueError as e:
        raise RuntimeError(f"El modelo no devolvió un resumen válido tras dos intentos: {e}")


class ClaudeProvider:
    def generar(self, cfg, clave, usuario):
        texto, modelo = _con_claude(cfg, clave, usuario)
        return json.loads(texto), modelo


class GeminiProvider:
    def generar(self, cfg, clave, usuario):
        texto, modelo = _con_gemini(cfg, clave, usuario)
        return json.loads(texto), modelo


class OpenAIProvider:
    def generar(self, cfg, clave, usuario):
        return _con_openai(cfg, clave, usuario)


def elegir_proveedor(cfg) -> IAIProvider:
    tipo = cfg["ajustes"].get("proveedor")
    return {"openai": OpenAIProvider, "gemini": GeminiProvider}.get(tipo, ClaudeProvider)()


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
