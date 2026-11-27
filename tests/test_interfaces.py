"""Pruebas de los contratos sin cargar Whisper ni llamar a servicios de IA."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ["AGENTE_CLASES_DATOS"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agente"))
from nucleo import resumen, motor


class RepositorioFalso:
    def __init__(self):
        self.clase = {"inicio": "2026-01-01T10:00:00", "nombre_asignatura": "Álgebra",
                      "segmentos": [{"ini": 0, "fin": 2, "texto": "Matrices"}]}
        self.estados = []

    def leer(self, cid):
        return self.clase

    def actualizar(self, cid, **campos):
        self.clase.update(campos)
        self.estados.append(campos.get("estado_resumen"))
        return self.clase

    def cerrar(self, cid, fin=None):
        self.clase["en_curso"] = False
        return self.clase

    def anadir_segmentos(self, cid, segmentos):
        self.clase["segmentos"].extend(segmentos)


class ProveedorFalso:
    def generar(self, cfg, clave, usuario):
        assert "Matrices" in usuario
        return {"titulo": "Matrices"}, "simulado"


class TranscriptorFalso:
    descripcion = "simulado"

    def cargar(self):
        pass

    def transcribir(self, audio, offset_s, contexto=""):
        return [{"ini": offset_s, "fin": offset_s + 1, "texto": "Prueba"}]

    def puede_aligerar(self):
        return False

    def aligerar(self):
        pass


class ContratosTest(unittest.TestCase):
    def test_resumen_inyectado(self):
        repo = RepositorioFalso()
        with patch.object(resumen, "cargar", return_value={"ajustes": {}}), \
             patch.object(resumen, "api_key", return_value=""), \
             patch.object(resumen, "resumen_en_pc", return_value=True):
            resumen.generar("clase", proveedor=ProveedorFalso(), repositorio=repo)
        self.assertEqual(repo.estados, ["generando", "listo"])
        self.assertEqual(repo.clase["resumen"]["modelo"], "simulado")

    def test_motor_inyectado(self):
        repo = RepositorioFalso()
        transcriptor = TranscriptorFalso()
        m = motor.Motor(log=lambda _: None, transcriptor=transcriptor, repositorio=repo)
        self.assertIs(m.transcriptor, transcriptor)
        m.cola_trans.put(("frag", "clase", None, 2))
        m.cola_trans.put(("cerrar", "clase"))
        m.cola_trans.put(("fin",))
        with patch.object(motor, "resumen_en_pc", return_value=False), \
             patch.object(m, "guardar_estado"):
            m._bucle_transcripcion()
        self.assertEqual(repo.clase["segmentos"][-1]["texto"], "Prueba")
        self.assertFalse(repo.clase["en_curso"])

    def test_seleccion_proveedores(self):
        for nombre, tipo in [("claude", resumen.ClaudeProvider),
                             ("gemini", resumen.GeminiProvider),
                             ("openai", resumen.OpenAIProvider)]:
            self.assertIsInstance(resumen.elegir_proveedor({"ajustes": {"proveedor": nombre}}), tipo)


if __name__ == "__main__":
    unittest.main()
