"""Local pywebview host for the shared Mis clases HTML panel."""
import re
import sys
from pathlib import Path

from bootstrap import build_class_service
from nucleo import config
import ventana_web


class PanelApi:
    def __init__(self):
        self._service = build_class_service()
        self._repository = self._service.repository

    def snapshot(self):
        return {**self._service.estado({}), **self._service.listar({}),
                'hechos': self._repository.leer_estado().get('hechos', []),
                'local_summaries': config.resumen_en_pc(config.cargar())}

    def read_class(self, cid, offset=0):
        return self._service.leer({'id': cid, 'desde': max(0, int(offset))})

    def mark_done(self, key, done):
        cid, sep, index = key.rpartition('~')
        if not sep or not index.isdigit():
            raise ValueError('Tarea no válida')
        record = self._repository.leer(cid)
        if int(index) >= len((record.get('resumen') or {}).get('destacados', [])):
            raise ValueError('Tarea no encontrada')
        return self._repository.marcar_hecho(key, bool(done))

    def move_class(self, cid, subject):
        self._check_idle(cid)
        return self._service.mover({'id': cid, 'asignatura': subject})

    def delete_class(self, cid):
        self._check_idle(cid)
        return self._service.borrar({'id': cid})

    def summarize(self, cid):
        self._check_idle(cid)
        if not config.resumen_en_pc(config.cargar()):
            raise RuntimeError('Configura un proveedor de resúmenes locales en Estudio.')
        from nucleo import resumen
        if not resumen.generar_seguro(cid, repositorio=self._repository):
            record = self._repository.leer(cid)
            raise RuntimeError(record.get('error_resumen') or 'Ya se está procesando la clase.')
        return {'ok': True}

    def _check_idle(self, cid):
        record = self._repository.leer(cid)
        if record.get('en_curso') or record.get('estado_resumen') == 'generando':
            raise RuntimeError('Espera a que termine el procesamiento de la clase.')


def panel_html(section='hoy'):
    if section not in ('hoy', 'calendario'):
        raise ValueError('Unknown panel section')
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    html = (root / 'hub' / 'mis-clases.html').read_text(encoding='utf-8')
    # The local panel needs neither external fonts nor the Claude artifact manifest.
    html = re.sub(r'<link[^>]+fonts\.googleapis\.com[^>]*>\s*', '', html)
    html = html.replace('<script type="application/json" id="claude-artifacts-manifest">{"permissions": ["full-access"]}</script>', '')
    marker = '<script>\nconst LOCAL'
    if marker not in html:
        raise RuntimeError('No se encuentra el punto de entrada del panel web.')
    return html.replace(marker, '<script>window.ESTUDIO_LOCAL = true; window.ESTUDIO_SECTION = ' + repr(section) + ';</script>\n' + marker, 1)


def run_panel(section='hoy'):
    webview = ventana_web.importar_webview()
    webview.create_window('Estudio Hub', html=panel_html(section), js_api=PanelApi(),
                          width=1200, height=800, min_size=(640, 500), background_color='#CFE6FF')
    ventana_web.iniciar(webview)
