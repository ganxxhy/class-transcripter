import sys
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agente"))
import actualizacion as a


class ActualizacionTests(unittest.TestCase):
    def setUp(self):
        a._cache = None
        self.data = {"schema": 1, "version": "1.2.1"}
        for platform, suffix in (("windows", "instalador.exe"), ("linux", "x86_64.AppImage")):
            self.data[platform] = {"url": f"https://github.com/{a.REPO}/releases/download/v1.2.1/Estudio-1.2.1-{suffix}",
                                   "sha256": hashlib.sha256(b"abc").hexdigest(), "size": 3}

    def test_manifest_and_cache(self):
        with patch.object(a, "_get", return_value=self.data) as get:
            self.assertEqual(a.buscar()["version"], "1.2.1")
            self.assertEqual(a.buscar()["tamano"], 3)
            get.assert_called_once_with(a.MANIFEST)

    def test_platform(self):
        for linux in (True, False):
            with patch.object(a, "ES_LINUX", linux):
                self.assertEqual(a._manifest_info(self.data)["instalador"], self.data["linux" if linux else "windows"]["url"])

    def test_fallback(self):
        with patch.object(a, "_registrar_error"), patch.object(a, "_get", side_effect=[ValueError(), {"tag_name": "v1.2.0"}]):
            self.assertEqual(a.buscar()["version"], "1.2.0")

    def test_rate_limit(self):
        with patch.object(a, "_registrar_error"), patch.object(a, "_get", side_effect=HTTPError(a.API, 403, "rate limit", {}, None)):
            self.assertIsNone(a.buscar())
            self.assertIn("limitado", a.ultimo_error)

    def test_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "installer"
            p.write_bytes(b"abc")
            info = a._manifest_info(self.data)
            a._verificar_descarga(p, info)
            p.write_bytes(b"xyz")
            with self.assertRaises(RuntimeError):
                a._verificar_descarga(p, info)


if __name__ == "__main__":
    unittest.main()
