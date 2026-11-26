import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Must be set before importing nucleo, so the tests never read the real config.json
os.environ["AGENTE_CLASES_DATOS"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agente"))
from nucleo import config, resumen  # noqa: E402
from nucleo.config import AJUSTES_POR_DEFECTO  # noqa: E402

RESPUESTAS = []  # queued (status, body) pairs, consumed in order
PETICIONES = []  # what the fake server received


class Falso(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        PETICIONES.append({"path": self.path, "headers": dict(self.headers), "json": json.loads(self.rfile.read(n))})
        codigo, cuerpo = RESPUESTAS.pop(0)
        datos = (cuerpo if isinstance(cuerpo, str) else json.dumps(cuerpo)).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, *args):
        pass


SERVIDOR = ThreadingHTTPServer(("127.0.0.1", 0), Falso)
threading.Thread(target=SERVIDOR.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{SERVIDOR.server_address[1]}/v1"

VALIDO = {"titulo": "T", "resumen": "## A\ntexto", "puntos_clave": ["a"], "conceptos": [], "destacados": [],
          "tareas": [], "calidad_audio": "buena"}


def cfg(modelo="m"):
    return {"ajustes": {**AJUSTES_POR_DEFECTO, "proveedor": "openai", "openai_base_url": URL, "modelo_openai": modelo}}


def chat(texto, finish="stop"):
    return (200, {"model": "servidor-modelo", "choices": [{"finish_reason": finish, "message": {"content": texto}}]})


def lanzar(respuestas, clave="k"):
    RESPUESTAS[:] = respuestas
    PETICIONES.clear()
    return resumen._con_openai(cfg(), clave, "clase")


def fallo(respuestas, clave="k"):
    try:
        lanzar(respuestas, clave)
    except RuntimeError as e:
        return str(e)
    raise AssertionError("debería haber fallado")


def test_extract_json():
    assert resumen.extract_json('{"a": 1}') == {"a": 1}
    assert resumen.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert resumen.extract_json('¡Claro! Aquí tienes:\n{"a": 1}\nEspero que sirva.') == {"a": 1}
    for malo in ("sin json", "[1, 2]", '{"a": 1,}'):
        try:
            resumen.extract_json(malo)
        except ValueError:
            continue
        raise AssertionError(malo)


def test_check_summary():
    falta = dict(VALIDO)
    del falta["destacados"]
    try:
        resumen.check_summary(falta)
        raise AssertionError("debería faltar destacados")
    except ValueError as e:
        assert "destacados" in str(e)
    assert resumen.check_summary({**VALIDO, "tareas": None})["tareas"] == []
    assert resumen.check_summary({**VALIDO, "calidad_audio": "rara"})["calidad_audio"] == "regular"


def test_chat_url():
    assert resumen._chat_url("http://x/v1") == "http://x/v1/chat/completions"
    assert resumen._chat_url("http://x/v1/") == "http://x/v1/chat/completions"
    assert resumen._chat_url("http://x/v1/chat/completions") == "http://x/v1/chat/completions"


def test_resumen_en_pc():
    assert config.resumen_en_pc(cfg())
    assert not config.resumen_en_pc(cfg(modelo=""))


def test_valido_a_la_primera():
    res, modelo = lanzar([chat(json.dumps(VALIDO))])
    assert res["titulo"] == "T" and modelo == "servidor-modelo"
    assert len(PETICIONES) == 1
    p = PETICIONES[0]
    assert p["path"] == "/v1/chat/completions"
    assert p["headers"]["Authorization"] == "Bearer k"
    assert "temperature" in p["json"] and "response_format" not in p["json"]


def test_sin_clave():
    lanzar([chat(json.dumps(VALIDO))], clave="")
    assert "Authorization" not in PETICIONES[0]["headers"]


def test_valla_markdown():
    res, _ = lanzar([chat("Claro:\n```json\n" + json.dumps(VALIDO) + "\n```")])
    assert res["resumen"].startswith("## A")


def test_reintento():
    res, _ = lanzar([chat('{"titulo": "T"}'), chat(json.dumps(VALIDO))])
    assert res["titulo"] == "T" and len(PETICIONES) == 2
    msgs = PETICIONES[1]["json"]["messages"]
    assert len(msgs) == 4 and msgs[-1]["role"] == "user" and "faltan los campos" in msgs[-1]["content"]


def test_siempre_invalido():
    e = fallo([chat("no es json"), chat("sigue sin serlo")])
    assert "dos intentos" in e and len(PETICIONES) == 2


def test_error_http_sin_clave_en_mensaje():
    e = fallo([(429, '{"errors":[{"message":"daily free allocation k"}]}')])
    assert "429" in e and "daily free allocation" in e and "allocation ***" in e


def test_max_tokens_rechazado():
    lanzar([(400, '{"error":"Unsupported parameter: max_tokens"}'), chat(json.dumps(VALIDO))])
    assert "max_completion_tokens" in PETICIONES[1]["json"] and "max_tokens" not in PETICIONES[1]["json"]


def test_cortado_por_longitud():
    assert "cortó" in fallo([chat('{"titulo"', finish="length")])


def test_servidor_apagado():
    c = cfg()
    c["ajustes"]["openai_base_url"] = "http://127.0.0.1:1/v1"
    try:
        resumen._con_openai(c, "", "clase")
        raise AssertionError("debería fallar")
    except RuntimeError as e:
        assert "No se pudo conectar" in str(e)


if __name__ == "__main__":
    test_extract_json(); test_check_summary(); test_chat_url(); test_resumen_en_pc()
    test_valido_a_la_primera(); test_sin_clave(); test_valla_markdown(); test_reintento()
    test_siempre_invalido(); test_error_http_sin_clave_en_mensaje(); test_max_tokens_rechazado()
    test_cortado_por_longitud(); test_servidor_apagado()
    print("OK")
