"""Exercise the OpenVINO acceleration pack download without network, GPU or real wheels."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agente"))

from infrastructure import openvino_runtime
from infrastructure.file_lock import try_file_lock
from infrastructure.openvino_runtime import (Wheel, activate_runtime, download_runtime, install_acceleration_pack,
                                             install_running, runtime_installed, runtime_key, wheels_for)

KEY = ("cp312", "linux", "x86_64")


def fake_wheel(files):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class FakeIndex:
    """Serves in-memory wheels by URL and records which URLs were requested."""

    def __init__(self, wheels):
        self.payloads = {wheel.url: data for wheel, data in wheels}
        self.requested = []

    def __call__(self, request, timeout=None):
        self.requested.append(request.full_url)
        return BytesIO(self.payloads[request.full_url])


def make_wheel(name, files, corrupt=False):
    data = fake_wheel(files)
    wheel = Wheel(name, f"https://example.invalid/{name}", len(data),
                  "0" * 64 if corrupt else sha256(data).hexdigest())
    return wheel, data


class WheelTableTests(unittest.TestCase):
    def test_pinned_wheels_match_platform_and_interpreter(self):
        linux = wheels_for(KEY)
        self.assertEqual(len(linux), 3)
        self.assertTrue(all("manylinux_2_28_x86_64" in w.filename for w in linux))
        self.assertIn("cp312", linux[0].filename)
        self.assertIn("py3-none", linux[2].filename)
        windows = wheels_for(("cp312", "win32", "amd64"))
        self.assertEqual(len(windows), 3)
        self.assertTrue(all("win_amd64" in w.filename for w in windows))
        for wheel in linux + windows:
            self.assertEqual(len(wheel.sha256), 64)
            self.assertTrue(wheel.url.startswith("https://files.pythonhosted.org/"))
            self.assertGreater(wheel.size, 0)

    def test_unsupported_systems_are_pointed_to_pip(self):
        for key in (("cp314", "linux", "x86_64"), ("cp312", "linux", "aarch64")):
            with self.subTest(key=key):
                with self.assertRaisesRegex(RuntimeError, "pip install openvino-genai"):
                    wheels_for(key)

    def test_key_normalizes_platform_and_machine(self):
        self.assertEqual(runtime_key("win32", (3, 12), "AMD64"), ("cp312", "win32", "amd64"))
        self.assertEqual(runtime_key("linux", (3, 12), "x86_64"), KEY)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.log = Mock()

    def install(self, wheels):
        self.enterContext(patch.dict(openvino_runtime.WHEELS, {KEY: tuple(w for w, _ in wheels)}))
        self.index = FakeIndex(wheels)
        download_runtime(self.directory, self.log, self.index, KEY)

    def test_download_extracts_and_marks_the_runtime(self):
        self.install([make_wheel("a-1-cp312-cp312-manylinux_2_28_x86_64.whl", {"pkg/__init__.py": "x = 1"}),
                      make_wheel("b-1-py3-none-manylinux_2_28_x86_64.whl", {"other/__init__.py": ""})])
        self.assertTrue((self.directory / "runtime" / "pkg" / "__init__.py").is_file())
        self.assertTrue((self.directory / "runtime" / "other" / "__init__.py").is_file())
        self.assertFalse((self.directory / "runtime.new").exists())
        self.assertEqual(list((self.directory / "runtime").glob("*.whl")), [])
        self.assertTrue(runtime_installed(self.directory, KEY))

    def test_second_call_does_nothing(self):
        self.install([make_wheel("a-1-cp312-cp312-manylinux_2_28_x86_64.whl", {"pkg/__init__.py": ""})])
        requested = len(self.index.requested)
        download_runtime(self.directory, self.log, self.index, KEY)
        self.assertEqual(len(self.index.requested), requested)
        self.assertIn("Ya está", self.log.call_args.args[0])

    def test_corrupt_download_keeps_the_previous_runtime(self):
        self.install([make_wheel("a-1-cp312-cp312-manylinux_2_28_x86_64.whl", {"pkg/__init__.py": "old"})])
        (self.directory / "runtime" / ".runtime.json").write_text("[]", encoding="utf-8")  # an older version
        bad = make_wheel("c-1-cp312-cp312-manylinux_2_28_x86_64.whl", {}, corrupt=True)
        with patch.dict(openvino_runtime.WHEELS, {KEY: (bad[0],)}):
            with self.assertRaisesRegex(RuntimeError, "Descarga corrupta"):
                download_runtime(self.directory, self.log, FakeIndex([bad]), KEY)
        self.assertEqual((self.directory / "runtime" / "pkg" / "__init__.py").read_text(), "old")
        self.assertFalse((self.directory / "runtime.new").exists())

    def test_zip_slip_members_are_rejected(self):
        for member in ("../evil.py", "/abs.py", "a/../../evil.py", "C:\\evil.py"):
            with self.subTest(member=member):
                directory = self.directory / "case"
                wheel = make_wheel("a-1-cp312-cp312-manylinux_2_28_x86_64.whl", {member: "x"})
                with patch.dict(openvino_runtime.WHEELS, {KEY: (wheel[0],)}):
                    with self.assertRaisesRegex(RuntimeError, "Archivo no válido"):
                        download_runtime(directory, self.log, FakeIndex([wheel]), KEY)
                self.assertFalse((self.directory / "evil.py").exists())
                self.assertFalse(Path("/abs.py").exists())

    def test_marker_for_another_version_or_key_is_not_installed(self):
        self.install([make_wheel("a-1-cp312-cp312-manylinux_2_28_x86_64.whl", {"pkg/__init__.py": ""})])
        self.assertFalse(runtime_installed(self.directory, ("cp312", "win32", "amd64")))
        with patch.object(openvino_runtime, "RUNTIME_VERSION", "9.9"):
            self.assertFalse(runtime_installed(self.directory, KEY))


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        saved = sys.path[:]
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), saved))
        self.enterContext(patch.object(openvino_runtime, "runtime_installed", return_value=True))
        self.no_pip = self.enterContext(patch("infrastructure.openvino_runtime.importlib.util.find_spec", return_value=None))
        self.runtime = str(self.directory / "runtime")

    def test_runtime_is_added_to_the_path_once(self):
        self.assertIsNone(activate_runtime(self.directory))
        self.assertIsNone(activate_runtime(self.directory))
        self.assertEqual(sys.path.count(self.runtime), 1)

    def test_pip_installation_is_left_alone(self):
        self.no_pip.return_value = object()
        self.assertIsNone(activate_runtime(self.directory))
        self.assertNotIn(self.runtime, sys.path)

    def test_incompatible_numpy_is_reported_without_touching_the_path(self):
        for version in ("2.6.0", "2.6.0rc1", "3.0"):
            with self.subTest(version=version), patch.object(openvino_runtime.numpy, "__version__", version):
                self.assertIn("numpy", activate_runtime(self.directory))
                self.assertNotIn(self.runtime, sys.path)

    def test_failures_become_a_message_instead_of_an_exception(self):
        with patch.object(openvino_runtime, "runtime_installed", side_effect=OSError("denied")):
            self.assertIn("denied", activate_runtime(self.directory))


class InstallPackTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.runtime, self.model = Mock(), Mock()
        self.enterContext(patch("infrastructure.openvino_runtime.importlib.util.find_spec", return_value=None))
        self.disk = self.enterContext(patch("infrastructure.openvino_runtime.shutil.disk_usage",
                                            return_value=Mock(free=100 * 1024 ** 3)))

    def test_concurrent_install_is_refused(self):
        with try_file_lock(str(self.directory / ".install.lock")) as acquired:
            self.assertTrue(acquired)
            self.assertTrue(install_running(self.directory))
            with self.assertRaisesRegex(RuntimeError, "en curso"):
                install_acceleration_pack(self.directory, {}, Mock(), True, self.runtime, self.model)
        self.runtime.assert_not_called()
        self.model.assert_not_called()
        self.assertFalse(install_running(self.directory))

    def test_not_enough_free_space_is_reported_before_downloading(self):
        self.disk.return_value = Mock(free=1024 ** 3)
        with self.assertRaisesRegex(RuntimeError, "No hay espacio suficiente.*2.5 GB.*1.0 GB"):
            install_acceleration_pack(self.directory, {}, Mock(), True, self.runtime, self.model)
        self.runtime.assert_not_called()
        self.model.assert_not_called()

    def test_space_is_not_required_when_everything_is_installed(self):
        with patch("infrastructure.openvino_runtime.runtime_installed", return_value=True), \
                patch("infrastructure.openvino_models.model_complete", return_value=True), \
                patch.object(self.disk, "return_value", Mock(free=0)):
            install_acceleration_pack(self.directory, {}, Mock(), True, self.runtime, self.model)
        self.model.assert_called_once()

    def test_runtime_and_model_are_installed(self):
        install_acceleration_pack(self.directory, {}, Mock(), True, self.runtime, self.model)
        self.runtime.assert_called_once()
        self.model.assert_called_once()

    def test_model_can_be_skipped(self):
        install_acceleration_pack(self.directory, {}, Mock(), False, self.runtime, self.model)
        self.runtime.assert_called_once()
        self.model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
