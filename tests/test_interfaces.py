"""Pruebas de los contratos sin cargar Whisper ni llamar a servicios de IA."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ["AGENTE_CLASES_DATOS"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agente"))
from nucleo import resumen, motor
from nucleo.servicio_clases import ServicioClases
from copy import deepcopy
import subprocess
from nucleo import almacen


class RepositorioFalso:
    def __init__(self):
        self.clase = {"inicio": "2026-01-01T10:00:00", "nombre_asignatura": "Álgebra",
                      "segmentos": [{"ini": 0, "fin": 2, "texto": "Matrices"}]}
        self.estados = []

    def leer(self, cid):
        return deepcopy(self.clase)

    def listar(self, incluir_segmentos=False):
        return [self.leer('clase')]

    def eliminar(self, cid):
        self.clase = None

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

    def test_servicio_clases(self):
        repo = RepositorioFalso()
        cfg = {"asignaturas": [{"id": "a", "nombre": "Álgebra"}], "horario": []}
        with tempfile.TemporaryDirectory() as ruta:
            servicio = ServicioClases(repo, lambda: cfg, ruta)
            self.assertFalse(servicio.estado({})["agente"]["activo"])
            self.assertEqual(servicio.leer({"id": "clase"})["total"], 1)
            self.assertEqual(servicio.leer({"id": "clase", "desde": 1})["segmentos"], [])
            self.assertIn("version", servicio.listar({})["clases"][0])
            servicio.guardar_resumen({"id": "clase", "resumen": {"titulo": "T"}})
            self.assertEqual(repo.clase["estado_resumen"], "listo")
            servicio.marcar_estado_resumen({"id": "clase", "estado": "error"})
            self.assertEqual(repo.clase["estado_resumen"], "error")
            servicio.mover({"id": "clase", "asignatura": "a"})
            self.assertEqual(repo.clase["asignatura"], "a")
            servicio.borrar({"id": "clase"})
            self.assertIsNone(repo.clase)

    def test_application_import_boundaries(self):
        import ast
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "agente"
        for layer in ("domain", "application"):
            for path in (root / layer).rglob("*.py"):
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                    names = ([node.module or ""] if isinstance(node, ast.ImportFrom)
                             else [alias.name for alias in node.names] if isinstance(node, ast.Import)
                             else [])
                    for name in names:
                        forbidden = ("infrastructure", "nucleo", "bootstrap", "app")
                        if layer == "domain":
                            forbidden += ("application",)
                        self.assertNotIn(name.split(".")[0], forbidden, str(path))

    def test_audio_adapter(self):
        class FakeAudio:
            def open(self, selection, callback, log):
                callback(16000, [0.1])
                return object(), "fake"
        engine = motor.Motor(log=lambda _: None, transcriptor=TranscriptorFalso(),
                             repositorio=RepositorioFalso(), audio_input=FakeAudio(),
                             load_config=lambda: {"ajustes": {}})
        engine._abrir_stream(None)
        self.assertEqual(engine.microfono_actual, "fake")
        self.assertEqual(engine.cola_audio.get_nowait(), (16000, [0.1]))

    def test_cross_process_storage(self):
        cid = almacen.crear_clase("test", "Test", "manual")
        source = ("import sys; sys.path.insert(0, 'agente'); "
                  "from nucleo import almacen; "
                  "cid=sys.argv[1]; "
                  "[(almacen.anadir_segmentos(cid, [{'ini': i, 'fin': i+1, 'texto': 'test'}])) "
                  "for i in range(20)]")
        processes = [subprocess.Popen([sys.executable, "-c", source, cid]) for _ in range(3)]
        try:
            for process in processes:
                self.assertEqual(process.wait(timeout=60), 0)
            self.assertEqual(len(almacen.leer(cid)["segmentos"]), 60)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            almacen.eliminar(cid)

    def test_seleccion_proveedores(self):
        for nombre, tipo in [("claude", resumen.ClaudeProvider),
                             ("gemini", resumen.GeminiProvider),
                             ("openai", resumen.OpenAIProvider)]:
            self.assertIsInstance(resumen.elegir_proveedor({"ajustes": {"proveedor": nombre}}), tipo)


if __name__ == "__main__":
    unittest.main()
