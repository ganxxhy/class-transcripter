"""Regression checks for standalone Hub desktop integration."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agente"))
import linux_desktop
import tema


class HubLauncherTests(unittest.TestCase):
    def test_install_refresh_and_uninstall(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {
                "XDG_DATA_HOME": directory + "/data",
                "XDG_CONFIG_HOME": directory + "/config",
                "APPIMAGE": directory + "/Estudio AppImage",
            }):
                linux_desktop.install(autostart=False)
                paths = linux_desktop._paths()
                hub = Path(paths["hub_launcher"])
                self.assertIn("Name=Estudio Hub", hub.read_text(encoding="utf-8"))
                self.assertIn("--hub", hub.read_text(encoding="utf-8"))
                self.assertIn("Icon=estudio-hub", hub.read_text(encoding="utf-8"))
                self.assertTrue(Path(paths["hub_icon"]).is_file())
                self.assertFalse(Path(paths["autostart"]).exists())
                hub.unlink()
                linux_desktop.refresh_if_stale()
                self.assertTrue(hub.exists())
                linux_desktop.uninstall()
                self.assertTrue(all(not Path(p).exists() for p in paths.values()))

    def test_hub_icon_is_distinct(self):
        original = tema.icono(64)
        hub = tema.hub_icon(64)
        self.assertEqual(hub.size, original.size)
        self.assertNotEqual(hub.tobytes(), original.tobytes())

    def test_windows_shortcut_contract(self):
        installer = (ROOT / "packaging" / "instalador.iss").read_text(encoding="utf-8")
        self.assertIn('Parameters: "--hub"', installer)
        self.assertIn('Estudio Hub', installer)
        self.assertIn('hub.ico', installer)


if __name__ == "__main__":
    unittest.main()
