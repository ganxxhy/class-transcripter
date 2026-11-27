"""Adaptadores de IA. Las llamadas existentes se conservan durante la migración."""
import json
from domain.ports import IAIProvider
from nucleo.formato_resumen import ESQUEMA, sistema, extract_json, check_summary


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


class ChatGPTProvider:
    """Use the signed-in ChatGPT plan; never fall back to API-key billing."""

    def generar(self, cfg, clave, usuario):
        from infrastructure.chatgpt import SESSION

        account_id = cfg["ajustes"].get("chatgpt_account_id") or SESSION.status()["active"]
        model = cfg["ajustes"].get("modelo_chatgpt", "").strip()
        if not model:
            raise RuntimeError("Selecciona un modelo de ChatGPT en el asistente.")
        instructions = (sistema(cfg) + "\n\nDevuelve SOLO un objeto JSON que cumpla este esquema:\n"
                        + json.dumps(ESQUEMA, ensure_ascii=False))
        messages = [{"role": "user", "content": usuario}]
        text, actual_model = SESSION.infer(model, instructions, messages, account_id=account_id)
        try:
            return check_summary(extract_json(text)), actual_model
        except ValueError:
            messages.extend([{"role": "assistant", "content": text},
                             {"role": "user", "content": "Devuelve SOLO el JSON completo y válido con todos los campos."}])
        text, actual_model = SESSION.infer(model, instructions, messages, account_id=account_id)
        try:
            return check_summary(extract_json(text)), actual_model
        except ValueError:
            raise RuntimeError("ChatGPT no devolvió un resumen válido tras dos intentos.") from None


def elegir_proveedor(cfg) -> IAIProvider:
    tipo = cfg["ajustes"].get("proveedor")
    return {"openai": OpenAIProvider, "gemini": GeminiProvider, "chatgpt": ChatGPTProvider}.get(tipo, ClaudeProvider)()


def _con_claude(cfg, clave, usuario):
    import anthropic

    client = anthropic.Anthropic(api_key=clave)
    peticion = dict(
        model=cfg["ajustes"]["modelo_resumen"],
        max_tokens=16000,
        system=sistema(cfg),
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
        "systemInstruction": {"parts": [{"text": sistema(cfg)}]},
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
    instrucciones = (sistema(cfg) + "\n\nResponde SOLO con un objeto JSON (sin texto antes ni después ni bloques de código) "
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


