"""Adaptadores de IA. Las llamadas existentes se conservan durante la migración."""
import json
from .interfaces import IAIProvider


class ClaudeProvider:
    def generar(self, cfg, clave, usuario):
        from .resumen import _con_claude
        texto, modelo = _con_claude(cfg, clave, usuario)
        return json.loads(texto), modelo


class GeminiProvider:
    def generar(self, cfg, clave, usuario):
        from .resumen import _con_gemini
        texto, modelo = _con_gemini(cfg, clave, usuario)
        return json.loads(texto), modelo


class OpenAIProvider:
    def generar(self, cfg, clave, usuario):
        from .resumen import _con_openai
        return _con_openai(cfg, clave, usuario)


def elegir_proveedor(cfg) -> IAIProvider:
    tipo = cfg["ajustes"].get("proveedor")
    return {"openai": OpenAIProvider, "gemini": GeminiProvider}.get(tipo, ClaudeProvider)()
