"""Esquema, instrucciones y validación compartidos por los proveedores."""
import json
import re

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


