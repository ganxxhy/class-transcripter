"""Exercise optional GPU selection and fallback without downloading models."""
from io import BytesIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agente"))

from infrastructure.transcription import LocalTranscriber
from infrastructure.vulkan_whisper import VulkanWhisper, read_segments


class VulkanSelectionTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.log = Mock()
        self.make_legacy = self.enterContext(patch("infrastructure.transcription.Transcriptor"))
        self.cuda = self.enterContext(patch("infrastructure.transcription.cuda_available", return_value=False))
        self.backend = LocalTranscriber({}, directory, self.log)
        self.backend.vulkan = Mock()
        self.legacy = self.make_legacy.return_value
        self.audio = np.zeros(16000, dtype=np.float32)

    def test_missing_worker_preserves_legacy_auto_selection(self):
        self.backend.vulkan.installed.return_value = False
        self.backend.cargar()
        self.make_legacy.assert_called_once_with({"dispositivo": "auto"}, self.log)
        self.cuda.assert_not_called()
        self.backend.vulkan.cargar.assert_not_called()

    def test_legacy_loaded_check_reflects_active_backend(self):
        self.backend.vulkan.installed.return_value = False
        self.assertIsNone(self.backend.modelo)
        self.backend.cargar()
        self.assertIs(self.backend.modelo, self.legacy)

    def test_cuda_has_priority(self):
        self.cuda.return_value = True
        self.backend.cargar()
        self.make_legacy.assert_called_once_with({"dispositivo": "cuda"}, self.log)
        self.backend.vulkan.cargar.assert_not_called()

    def test_explicit_legacy_modes_skip_vulkan(self):
        for device in ("cpu", "cuda"):
            with self.subTest(device=device):
                self.backend.settings["dispositivo"] = device
                self.backend.active = None
                self.backend.cargar()
                self.make_legacy.assert_called_with({"dispositivo": device}, self.log)
        self.cuda.assert_not_called()
        self.backend.vulkan.installed.assert_not_called()

    def test_auto_uses_vulkan_when_cuda_is_absent(self):
        self.backend.cargar()
        self.assertIs(self.backend.active, self.backend.vulkan)
        self.assertFalse(self.backend.puede_aligerar())
        self.make_legacy.assert_not_called()

    def test_failed_cuda_startup_still_tries_vulkan(self):
        self.cuda.return_value = True
        self.legacy.cargar.side_effect = RuntimeError("CUDA probe failed")
        self.backend.cargar()
        self.assertIs(self.backend.active, self.backend.vulkan)

    def test_explicit_vulkan_startup_failure_selects_cpu(self):
        self.backend.settings["dispositivo"] = "vulkan"
        self.backend.vulkan.cargar.side_effect = RuntimeError("driver missing")
        self.backend.cargar()
        self.make_legacy.assert_called_once_with({"dispositivo": "cpu"}, self.log)
        self.cuda.assert_not_called()
        self.assertTrue(any("driver missing" in call.args[0] for call in self.log.call_args_list))

    def test_inference_failure_retries_once_and_keeps_cpu(self):
        result = [{"ini": 3.0, "fin": 4.0, "texto": "Matrices"}]
        self.legacy.transcribir.return_value = result
        self.backend.vulkan.transcribir.side_effect = RuntimeError("device lost")
        self.assertIs(self.backend.transcribir(self.audio, 3), result)
        self.legacy.transcribir.assert_called_once_with(self.audio, 3, "")
        self.assertIs(self.backend.transcribir(self.audio, 4), result)
        self.backend.vulkan.transcribir.assert_called_once()
        self.backend.vulkan.close.assert_called_once()
        self.assertTrue(any("Velocidad de transcripción:" in call.args[0] for call in self.log.call_args_list))


class TranscriberContractTests(unittest.TestCase):
    def test_transcribers_expose_ui_contract(self):
        from infrastructure.whisper import Transcriptor
        with TemporaryDirectory() as directory:
            backends = [LocalTranscriber({}, directory), Transcriptor({})]
        for backend in backends:
            with self.subTest(backend=type(backend).__name__):
                for name in ("cargar", "transcribir", "puede_aligerar", "aligerar"):
                    self.assertTrue(callable(getattr(backend, name)))
                self.assertIsNone(backend.modelo)
                self.assertEqual(backend.descripcion, "sin cargar")


class VulkanProtocolTests(unittest.TestCase):
    def test_worker_requires_voice_activity_model_before_launch(self):
        with TemporaryDirectory() as directory:
            adapter = VulkanWhisper(directory, {}, Mock())
            adapter.worker.touch()
            adapter.model.touch()
            with patch("infrastructure.vulkan_whisper.subprocess.Popen") as launch:
                with self.assertRaisesRegex(RuntimeError, "detección de voz"):
                    adapter.cargar()
            launch.assert_not_called()

    def test_response_preserves_class_offsets_and_filters_silence(self):
        transcript = "Álgebra lineal".encode()
        stream = BytesIO(
            b"SEGMENTS 2\n25 140 0.1 " + str(len(transcript)).encode() + b"\n" + transcript
            + b"10 20 0.99 3\nabc"
        )
        adapter = VulkanWhisper(Path.cwd(), {}, Mock())
        with patch.object(adapter, "_infer", return_value=read_segments(stream)):
            self.assertEqual(
                adapter.transcribir(np.zeros(16000, dtype=np.float32), 6),
                [{"ini": 6.2, "fin": 7.0, "texto": "Álgebra lineal"}],
            )

    def test_truncated_response_fails_as_a_whole(self):
        with self.assertRaisesRegex(RuntimeError, "Incomplete Vulkan segment"):
            read_segments(BytesIO(b"SEGMENTS 2\n0 1 0 2\nok0 1 0 5\nbad"))


if __name__ == "__main__":
    unittest.main()
