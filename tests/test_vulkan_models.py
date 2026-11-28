"""Verify Vulkan model downloads without network access."""
from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agente"))

from infrastructure import vulkan_models

DATA = b"model-bytes" * 10


class FailingBody(BytesIO):
    def read(self, size=-1):
        if self.tell():
            raise OSError("connection lost")
        return super().read(10)


def opener_for(body_factory):
    @contextmanager
    def opener(request, timeout):
        yield body_factory()
    return Mock(side_effect=opener)


class VulkanModelDownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.entry = ("ggml-large-v3-turbo.bin", "https://example.invalid/m", len(DATA), sha256(DATA).hexdigest())
        self.enterContext(patch.object(vulkan_models, "VULKAN_MODELS", (self.entry,)))
        self.log = Mock()

    def download(self, opener, settings=None):
        vulkan_models.download_vulkan_models(self.directory, settings, self.log, opener, chunk_size=16)

    def test_download_is_verified_and_leaves_no_partial_file(self):
        self.download(opener_for(lambda: BytesIO(DATA)))
        self.assertEqual((self.directory / self.entry[0]).read_bytes(), DATA)
        self.assertEqual([p.name for p in self.directory.iterdir()], [self.entry[0]])

    def test_wrong_checksum_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "corrupta"):
            self.download(opener_for(lambda: BytesIO(b"x" * len(DATA))))
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_existing_file_with_expected_size_is_kept(self):
        (self.directory / self.entry[0]).write_bytes(DATA)
        opener = opener_for(lambda: BytesIO(DATA))
        self.download(opener)
        opener.assert_not_called()

    def test_interrupted_download_removes_partial_file(self):
        with self.assertRaises(OSError):
            self.download(opener_for(lambda: FailingBody(DATA)))
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_custom_model_name_skips_the_default_model(self):
        opener = opener_for(lambda: BytesIO(DATA))
        self.download(opener, {"modelo_whisper": "small"})
        opener.assert_not_called()
        self.assertIn("ggml-small.bin", self.log.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
