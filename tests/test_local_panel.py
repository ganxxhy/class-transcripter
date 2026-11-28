"""Regression tests for the provider-independent local web panel and schedule editor."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

DATA = tempfile.TemporaryDirectory()
os.environ['AGENTE_CLASES_DATOS'] = DATA.name
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agente'))
from asistente.class_viewer import PanelApi, panel_html
from asistente.asistente import Api
from nucleo import config
from bootstrap import build_repository


class LocalPanelTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config.vacia()
        self.cfg['asignaturas'] = [{'id': 'rest', 'nombre': 'REST', 'color': '#2563EB'},
                                  {'id': 'db', 'nombre': 'Datos', 'color': '#0E9F8E'}]
        self.cfg['horario'] = [{'dia': 'lunes', 'inicio': '15:00', 'fin': '16:40', 'asignatura': 'rest', 'aula': '704'}]
        self.cfg['ajustes'].update(proveedor='chatgpt', modelo_chatgpt='test-model', chatgpt_account_id='test-account', microfono='test-mic')
        with patch.object(config, 'escribir_puntero'):
            config.guardar(self.cfg)
        self.repository = build_repository()
        self.cid = self.repository.crear_clase('rest', 'REST', 'manual')
        self.repository.anadir_segmentos(self.cid, [{'ini': 0, 'fin': 5, 'texto': 'HTTP'}])
        self.repository.cerrar(self.cid)
        self.repository.actualizar(self.cid, estado_resumen='listo', resumen={'titulo': 'REST', 'destacados': [{'titulo': 'Entrega'}]})
        self.api = PanelApi()

    def tearDown(self):
        if any(c['id'] == self.cid for c in self.repository.listar()):
            self.repository.eliminar(self.cid)

    def test_shared_html(self):
        html = panel_html('calendario')
        self.assertIn('window.ESTUDIO_LOCAL = true', html)
        self.assertIn("window.ESTUDIO_SECTION = 'calendario'", html)
        self.assertIn('function vCal()', html)
        self.assertNotIn('fonts.googleapis.com', html)
        self.assertNotIn('claude-artifacts-manifest', html)
        with self.assertRaises(ValueError):
            panel_html('invalid')

    def test_read_local_data_and_task(self):
        data = self.api.snapshot()
        self.assertEqual(data['horario'], self.cfg['horario'])
        self.assertTrue(data['local_summaries'])
        self.assertNotIn('ajustes', data)
        record = next(c for c in data['clases'] if c['id'] == self.cid)
        self.assertNotIn('segmentos', record)
        self.assertEqual(self.api.read_class(self.cid)['segmentos'][0]['texto'], 'HTTP')
        key = self.cid + '~0'
        self.api.mark_done(key, True)
        self.assertIn(key, self.api.snapshot()['hechos'])
        self.api.mark_done(key, False)
        self.assertNotIn(key, self.api.snapshot()['hechos'])

    def test_move_delete_and_active_guard(self):
        self.repository.actualizar(self.cid, en_curso=True)
        with self.assertRaises(RuntimeError): self.api.delete_class(self.cid)
        with self.assertRaises(RuntimeError): self.api.move_class(self.cid, 'db')
        self.repository.actualizar(self.cid, en_curso=False)
        self.api.move_class(self.cid, 'db')
        self.assertEqual(self.repository.leer(self.cid)['asignatura'], 'db')
        self.api.delete_class(self.cid)
        self.assertFalse(any(c['id'] == self.cid for c in self.api.snapshot()['clases']))

    def test_schedule_editor_preserves_account_and_settings(self):
        new_schedule = [{**self.cfg['horario'][0], 'aula': '705'}]
        with patch.object(config, 'escribir_puntero'):
            self.assertTrue(Api(schedule_only=True).guardar({'asignaturas': self.cfg['asignaturas'], 'horario': new_schedule})['ok'])
        saved = config.cargar()
        self.assertEqual(saved['horario'], new_schedule)
        self.assertEqual(saved['ajustes'], self.cfg['ajustes'])
        self.assertEqual(saved['perfil'], self.cfg['perfil'])

    def test_summary_uses_existing_provider(self):
        with patch('nucleo.resumen.generar_seguro', return_value=True) as generate:
            self.assertEqual(self.api.summarize(self.cid), {'ok': True})
            generate.assert_called_once_with(self.cid, repositorio=self.api._repository)


if __name__ == '__main__':
    unittest.main()
