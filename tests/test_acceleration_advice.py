"""Exercise the texts Settings shows about optional GPU acceleration."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agente"))

from acceleration_advice import AccelerationStatus, acceleration_advice, install_done_text


def status(vendors, ready=False, vulkan=False, pack=True, running=False):
    return AccelerationStatus(vendors, ready, vulkan, pack, running)


class AdviceTests(unittest.TestCase):
    def test_intel_without_the_pack_offers_the_download(self):
        advice = acceleration_advice(status(["intel"]), "auto")
        self.assertTrue(advice.can_install)
        self.assertIn("1,7 GB", advice.text)

    def test_intel_with_a_ready_pack_confirms_it(self):
        advice = acceleration_advice(status(["intel"], ready=True), "auto")
        self.assertEqual(advice.text, "GPU Intel detectada: la aceleración con OpenVINO está lista.")
        self.assertFalse(advice.can_install)

    def test_ready_pack_with_another_device_says_how_to_use_it(self):
        advice = acceleration_advice(status(["intel"], ready=True), "cpu")
        self.assertIn("Elige «Automático»", advice.text)
        self.assertFalse(advice.can_install)

    def test_running_install_has_priority(self):
        advice = acceleration_advice(status(["intel"], running=True), "auto")
        self.assertIn("Descargando", advice.text)
        self.assertFalse(advice.can_install)

    def test_unsupported_python_points_to_manual_install(self):
        advice = acceleration_advice(status(["intel"], pack=False), "auto")
        self.assertIn("pip install openvino-genai", advice.text)
        self.assertFalse(advice.can_install)

    def test_amd_only_gets_text(self):
        for vulkan, fragment in ((False, "compilar el motor"), (True, "Vulkan está instalado")):
            with self.subTest(vulkan=vulkan):
                advice = acceleration_advice(status(["amd"], vulkan=vulkan), "auto")
                self.assertIn(fragment, advice.text)
                self.assertFalse(advice.can_install)

    def test_nvidia_or_unknown_gpus_get_nothing(self):
        self.assertIsNone(acceleration_advice(status(["intel", "nvidia"]), "auto"))
        self.assertIsNone(acceleration_advice(status([]), "auto"))

    def test_done_text_depends_on_the_chosen_device(self):
        self.assertIn("Reinicia", install_done_text("auto"))
        self.assertIn("Reinicia", install_done_text("openvino"))
        self.assertIn("Elige", install_done_text("cpu"))


if __name__ == "__main__":
    unittest.main()
