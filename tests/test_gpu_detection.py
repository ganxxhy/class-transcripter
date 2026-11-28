"""Exercise GPU vendor detection with fake sysfs trees and PowerShell output."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agente"))

from infrastructure.gpu_detection import detect_gpu_vendors


def fake_drm(root, entries):
    for name, content in entries.items():
        device = Path(root) / name / "device"
        device.mkdir(parents=True)
        (device / "vendor").write_text(content, encoding="ascii")


class LinuxDetectionTests(unittest.TestCase):
    def test_cards_are_read_and_connectors_and_garbage_ignored(self):
        with TemporaryDirectory() as root:
            fake_drm(root, {"card0": "0x8086\n", "card1": "0x1002\n", "card1-eDP-1": "0x10de\n", "card2": "basura"})
            self.assertEqual(detect_gpu_vendors("linux", root), ["amd", "intel"])

    def test_missing_drm_directory_gives_no_vendors(self):
        self.assertEqual(detect_gpu_vendors("linux", "/nonexistent/drm"), [])


class WindowsDetectionTests(unittest.TestCase):
    def test_vendor_ids_are_parsed_from_pnp_device_ids(self):
        run = Mock(return_value=Mock(stdout="PCI\\VEN_8086&DEV_64A0&SUBSYS\r\nPCI\\VEN_10DE&DEV_2560\r\n"))
        self.assertEqual(detect_gpu_vendors("win32", run=run), ["intel", "nvidia"])
        self.assertIn("Win32_VideoController", run.call_args.args[0][-1])

    def test_failures_give_no_vendors(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("powershell", 15)):
            with self.subTest(error=type(error).__name__):
                self.assertEqual(detect_gpu_vendors("win32", run=Mock(side_effect=error)), [])

    def test_other_platforms_give_no_vendors(self):
        self.assertEqual(detect_gpu_vendors("darwin"), [])


if __name__ == "__main__":
    unittest.main()
