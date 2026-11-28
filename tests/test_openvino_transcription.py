"""Exercise the optional OpenVINO backend and its selection without the package or a model."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agente"))

from infrastructure.openvino_models import MODEL_DIRECTORY, REPO, REVISION, download_openvino_model
from infrastructure.openvino_whisper import OpenVinoWhisper
from infrastructure.transcription import LocalTranscriber


def chunk(start, end, text):
    return Mock(start_ts=start, end_ts=end, text=text)


class FakeModelDirectory:
    def __init__(self, test):
        self.root = Path(test.enterContext(TemporaryDirectory()))
        self.model = self.root / "whisper-large-v3-int8-ov"
        self.model.mkdir()
        (self.model / "openvino_encoder_model.xml").touch()


class OpenVinoBackendTests(unittest.TestCase):
    def setUp(self):
        self.files = FakeModelDirectory(self)
        self.pipeline = Mock()
        self.pipeline.get_generation_config.return_value = Mock()
        self.factory = Mock(return_value=self.pipeline)
        self.log = Mock()
        self.enterContext(patch.object(OpenVinoWhisper, "installed", return_value=True))
        self.backend = OpenVinoWhisper(self.files.root, {"idioma": "es"}, self.log, self.factory,
                                       lambda: ("GPU", "Intel(R) Arc(TM) Graphics"))
        self.speech = np.full(16000, 0.1, dtype=np.float32)

    def test_loading_selects_the_gpu_and_describes_it(self):
        self.backend.cargar()
        self.factory.assert_called_once_with(self.files.model.resolve(), "GPU")
        config = self.pipeline.get_generation_config.return_value
        self.assertEqual((config.language, config.task, config.return_timestamps), ("<|es|>", "transcribe", True))
        self.pipeline.generate.assert_called_once()  # startup probe
        self.assertIn("OpenVINO (Intel(R) Arc(TM) Graphics)", self.backend.descripcion)

    def test_missing_model_names_directory_and_remedy(self):
        backend = OpenVinoWhisper(self.files.root, {"modelo_whisper": "small"}, self.log)
        with self.assertRaisesRegex(RuntimeError, "--descargar-modelo-openvino"):
            backend.cargar()

    def test_missing_package_is_reported(self):
        with patch.object(OpenVinoWhisper, "installed", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "openvino-genai"):
                self.backend.cargar()

    def test_no_gpu_is_reported_instead_of_using_cpu(self):
        def no_gpu():
            raise RuntimeError("OpenVINO no encuentra ninguna GPU")
        backend = OpenVinoWhisper(self.files.root, {}, self.log, self.factory, no_gpu)
        with self.assertRaisesRegex(RuntimeError, "GPU"):
            backend.cargar()
        self.factory.assert_not_called()

    def test_segments_keep_class_offsets_and_drop_hallucinations(self):
        self.backend.cargar()
        self.pipeline.generate.reset_mock()
        self.pipeline.generate.return_value = Mock(chunks=[
            chunk(0.0, 2.5, " Álgebra lineal"), chunk(2.5, 3.0, " Gracias."), chunk(3.0, 99.0, " Matrices")])
        result = self.backend.transcribir(np.full(16000 * 4, 0.1, dtype=np.float32), 60)
        self.assertEqual([s["texto"] for s in result], ["Álgebra lineal", "Matrices"])
        self.assertEqual(result[0]["ini"], 60.0)
        self.assertEqual(result[1]["fin"], 64.0)  # clamped to the chunk length

    def test_silent_chunks_skip_inference(self):
        self.backend.cargar()
        self.pipeline.generate.reset_mock()
        self.assertEqual(self.backend.transcribir(np.zeros(16000, dtype=np.float32), 0), [])
        self.pipeline.generate.assert_not_called()


class OpenVinoSelectionTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.log = Mock()
        self.make_legacy = self.enterContext(patch("infrastructure.transcription.Transcriptor"))
        self.cuda = self.enterContext(patch("infrastructure.transcription.cuda_available", return_value=False))
        self.backend = LocalTranscriber({}, directory, self.log)
        self.backend.vulkan = Mock()
        self.backend.openvino = Mock()
        self.audio = np.zeros(16000, dtype=np.float32)

    def test_auto_prefers_openvino_over_vulkan(self):
        self.backend.cargar()
        self.assertIs(self.backend.active, self.backend.openvino)
        self.backend.vulkan.cargar.assert_not_called()
        self.assertFalse(self.backend.puede_aligerar())

    def test_auto_falls_back_from_openvino_to_vulkan(self):
        self.backend.openvino.cargar.side_effect = RuntimeError("no model")
        self.backend.cargar()
        self.assertIs(self.backend.active, self.backend.vulkan)
        self.assertTrue(any("OpenVINO" in call.args[0] and "no model" in call.args[0] for call in self.log.call_args_list))

    def test_auto_without_optional_engines_uses_faster_whisper(self):
        self.backend.openvino.installed.return_value = False
        self.backend.vulkan.installed.return_value = False
        self.backend.cargar()
        self.make_legacy.assert_called_once_with({"dispositivo": "auto"}, self.log)

    def test_explicit_openvino_failure_selects_cpu(self):
        self.backend.settings["dispositivo"] = "openvino"
        self.backend.openvino.cargar.side_effect = RuntimeError("driver missing")
        self.backend.cargar()
        self.make_legacy.assert_called_once_with({"dispositivo": "cpu"}, self.log)
        self.backend.vulkan.cargar.assert_not_called()

    def test_openvino_inference_failure_retries_on_cpu(self):
        result = [{"ini": 0.0, "fin": 1.0, "texto": "Hola"}]
        self.make_legacy.return_value.transcribir.return_value = result
        self.backend.openvino.transcribir.side_effect = RuntimeError("device lost")
        self.assertIs(self.backend.transcribir(self.audio, 0), result)
        self.backend.openvino.close.assert_called_once()
        self.assertTrue(any("Falló OpenVINO" in call.args[0] for call in self.log.call_args_list))


class OpenVinoDownloadTests(unittest.TestCase):
    def test_download_is_pinned_and_skipped_when_present(self):
        with TemporaryDirectory() as directory:
            downloader = Mock()
            download_openvino_model(directory, {}, Mock(), downloader)
            downloader.assert_called_once_with(repo_id=REPO, revision=REVISION,
                                               local_dir=str(Path(directory) / MODEL_DIRECTORY))
            target = Path(directory) / MODEL_DIRECTORY
            target.mkdir()
            (target / "openvino_encoder_model.xml").touch()
            downloader.reset_mock()
            download_openvino_model(directory, {}, Mock(), downloader)
            downloader.assert_not_called()

    def test_other_models_are_placed_by_hand(self):
        log = Mock()
        downloader = Mock()
        download_openvino_model("unused", {"modelo_whisper": "small"}, log, downloader)
        downloader.assert_not_called()
        self.assertIn("whisper-small-int8-ov", log.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
