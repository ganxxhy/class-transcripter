"""Settings device options must map to the values LocalTranscriber understands."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agente"))

from device_choices import DEVICE_CHOICES, device_label, device_value


class DeviceChoicesTests(unittest.TestCase):
    def test_stored_values_are_the_supported_devices(self):
        self.assertEqual([value for value, _ in DEVICE_CHOICES], ["auto", "cpu", "cuda", "vulkan"])

    def test_labels_round_trip_to_stored_values(self):
        for value, _ in DEVICE_CHOICES:
            self.assertEqual(device_value(device_label(value)), value)

    def test_unknown_stored_value_is_kept(self):
        self.assertEqual(device_label("hand-edited"), "hand-edited")
        self.assertEqual(device_value("hand-edited", "hand-edited"), "hand-edited")

    def test_dialog_saves_the_dispositivo_key(self):
        source = (Path(__file__).resolve().parents[1] / "agente" / "app.py").read_text(encoding="utf-8")
        self.assertIn('aj["dispositivo"] = dispositivo', source)


if __name__ == "__main__":
    unittest.main()
