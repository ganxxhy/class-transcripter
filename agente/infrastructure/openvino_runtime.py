"""Download, verify and activate the OpenVINO runtime as an optional acceleration pack.

Packaged builds cannot run pip, so the pinned wheels (plain zip files) are fetched from PyPI,
checked against their known SHA-256 and extracted under datos/openvino/runtime.
"""
from collections import namedtuple
import importlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform as platform_module
import re
import shutil
import sys
import urllib.request
import zipfile

import numpy

from .downloads import fetch_verified
from .file_lock import try_file_lock

RUNTIME_VERSION = "2026.4.1"
NUMPY_BELOW = (2, 6)  # openvino 2026.4.1 requires numpy<2.6
MARKER = ".runtime.json"
LOCK = ".install.lock"
GB = 1024 ** 3
RUNTIME_SPACE = GB // 2     # downloaded wheels plus the extracted runtime, with margin
MODEL_SPACE = 2 * GB        # the 1.5 GB model plus Hugging Face temporary files

Wheel = namedtuple("Wheel", "filename url size sha256")

WHEELS = {
    ("cp312", "linux", "x86_64"): (
            Wheel("openvino-2026.4.1-22982-cp312-cp312-manylinux_2_28_x86_64.whl",
                  "https://files.pythonhosted.org/packages/ec/3a/2a173ac1ad749ff0b041788eefc1ade0d410231fedfc43f77474f3b806cc/openvino-2026.4.1-22982-cp312-cp312-manylinux_2_28_x86_64.whl",
                  59144434, "6b4375c17ddcac83a5180349e2e2bb811185c261066e2a920659892d58ef0e3b"),
            Wheel("openvino_genai-2026.4.1.0-2636-cp312-cp312-manylinux_2_28_x86_64.whl",
                  "https://files.pythonhosted.org/packages/bb/88/0fe4ebbe51ca991eeb69baabf3a99d05c5c1db35a9ec3e0f43b3b6670268/openvino_genai-2026.4.1.0-2636-cp312-cp312-manylinux_2_28_x86_64.whl",
                  6659845, "9ac9caa404931598c1ad1af4aa5a009409483095e97ee55888c6055bd97394fb"),
            Wheel("openvino_tokenizers-2026.4.1.0-py3-none-manylinux_2_28_x86_64.whl",
                  "https://files.pythonhosted.org/packages/8d/63/03b056370f6fa951256a1190b56e582b9315cab559e5338b3133b6eb87b1/openvino_tokenizers-2026.4.1.0-py3-none-manylinux_2_28_x86_64.whl",
                  1857119, "f30dc9d6dd9e485b10495bcf72fc257f33bf35938da783fbb8f17c98c5ab517f"),
    ),
    ("cp312", "win32", "amd64"): (
            Wheel("openvino-2026.4.1-22982-cp312-cp312-win_amd64.whl",
                  "https://files.pythonhosted.org/packages/d0/44/66a61b7cfccea1dfa20e95a04b4157f07a0e4dc3f7e894b22a92abb8822b/openvino-2026.4.1-22982-cp312-cp312-win_amd64.whl",
                  84964415, "4e04316abff1b99e29b8cbd38deaef9bde4739eba216d982d4b3981e456ecd87"),
            Wheel("openvino_genai-2026.4.1.0-2636-cp312-cp312-win_amd64.whl",
                  "https://files.pythonhosted.org/packages/8d/16/30618b90e07e735cba428763c873aea625a4e2a47fbe059ea54a78718a34/openvino_genai-2026.4.1.0-2636-cp312-cp312-win_amd64.whl",
                  3888058, "9ca3545173020d758693d7e484ec6660fb5665ee149d0de0fb6b126d95f881c5"),
            Wheel("openvino_tokenizers-2026.4.1.0-py3-none-win_amd64.whl",
                  "https://files.pythonhosted.org/packages/7a/8f/3d8386a8ad50a02e51320028730aa8e65814c28d3bd9d20d6ecb01636421/openvino_tokenizers-2026.4.1.0-py3-none-win_amd64.whl",
                  1560547, "e6250eae9d00704249d21bfd8ad1600de2e49635aa2dcbb6e54a6aa9087f052d"),
    ),
}


def runtime_key(platform=sys.platform, version_info=sys.version_info, machine=None):
    """Return (python tag, os, cpu architecture) identifying the wheel set for this interpreter."""
    system = "linux" if platform.startswith("linux") else platform
    return (f"cp{version_info[0]}{version_info[1]}", system, (machine or platform_module.machine()).lower())


def wheels_for(key=None):
    key = key or runtime_key()
    try:
        return WHEELS[key]
    except KeyError:
        raise RuntimeError(
            f"No hay un paquete de OpenVINO preparado para este sistema ({key[0]}, {key[1]}, {key[2]}). "
            "Desde el código fuente: pip install openvino-genai.") from None


def pack_available(key=None):
    """True when the pack can be downloaded here or OpenVINO is already installed with pip."""
    if importlib.util.find_spec("openvino_genai") is not None:
        return True
    try:
        wheels_for(key)
    except RuntimeError:
        return False
    return True


def _marker(key):
    return {"version": RUNTIME_VERSION, "key": list(key), "files": [wheel.filename for wheel in wheels_for(key)]}


def runtime_installed(directory, key=None):
    key = key or runtime_key()
    try:
        return json.loads((Path(directory) / "runtime" / MARKER).read_text(encoding="utf-8")) == _marker(key)
    except (OSError, ValueError, RuntimeError):
        return False


def _extract(wheel, destination):
    root = Path(destination).resolve()
    with zipfile.ZipFile(wheel) as archive:
        for member in archive.infolist():
            name = member.filename
            parts = PurePosixPath(name).parts + PureWindowsPath(name).parts
            if (PurePosixPath(name).is_absolute() or PureWindowsPath(name).is_absolute()
                    or PureWindowsPath(name).drive or ".." in parts
                    or not (root / name).resolve().is_relative_to(root)):
                raise RuntimeError(f"Archivo no válido en {Path(wheel).name}")
        archive.extractall(root)


def download_runtime(directory, log=print, opener=urllib.request.urlopen, key=None, chunk_size=1 << 20):
    """Install the pinned OpenVINO wheels into directory/runtime unless they are already there."""
    directory = Path(directory)
    key = key or runtime_key()
    if runtime_installed(directory, key):
        log("Ya está: motor de OpenVINO")
        return
    wheels = wheels_for(key)
    staging = directory / "runtime.new"
    old = directory / "runtime.old"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        for wheel in wheels:
            log(f"Descargando motor de OpenVINO ({wheel.filename})…")
            fetch_verified(wheel.filename, wheel.url, wheel.size, wheel.sha256, staging, log, opener, chunk_size)
            _extract(staging / wheel.filename, staging)
            (staging / wheel.filename).unlink()
        (staging / MARKER).write_text(json.dumps(_marker(key)), encoding="utf-8")
        try:
            shutil.rmtree(old, ignore_errors=True)
            if (directory / "runtime").exists():
                os.replace(directory / "runtime", old)
            os.replace(staging, directory / "runtime")
            shutil.rmtree(old, ignore_errors=True)
        except PermissionError:
            raise RuntimeError("No se pudo sustituir el motor de OpenVINO; cierra Estudio y vuelve a intentarlo.") from None
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    log("Listo: motor de OpenVINO")


def activate_runtime(directory):
    """Make a downloaded runtime importable. Returns None when fine or a message for the user; never raises."""
    try:
        if importlib.util.find_spec("openvino_genai") is not None or not runtime_installed(directory):
            return None
        match = re.match(r"(\d+)\.(\d+)", numpy.__version__)
        if match is None or (int(match.group(1)), int(match.group(2))) >= NUMPY_BELOW:
            return "La versión de numpy incluida no es compatible con el motor de OpenVINO descargado."
        runtime = str(Path(directory) / "runtime")
        if runtime not in sys.path:
            sys.path.insert(0, runtime)
            importlib.invalidate_caches()
        return None
    except Exception as error:
        return f"No se pudo preparar el motor de OpenVINO: {error}"


def install_running(directory):
    """True when another process or thread is installing the pack."""
    with try_file_lock(str(Path(directory) / LOCK)) as acquired:
        return not acquired


def _require_free_space(directory, include_model):
    """Fail early with a readable message instead of a disk error in the middle of a 1.5 GB download."""
    from .openvino_models import MODEL_DIRECTORY, model_complete
    needed = 0
    if importlib.util.find_spec("openvino_genai") is None and not runtime_installed(directory):
        needed += RUNTIME_SPACE
    if include_model and not model_complete(directory / MODEL_DIRECTORY):
        needed += MODEL_SPACE
    free = shutil.disk_usage(directory).free if needed else 0
    if needed and free < needed:
        raise RuntimeError(f"No hay espacio suficiente en {directory}: hacen falta unos {needed / GB:.1f} GB libres "
                           f"y hay {free / GB:.1f} GB.")


def install_acceleration_pack(directory, settings, log=print, include_model=True,
                              runtime_downloader=download_runtime, model_downloader=None):
    """Download the runtime (unless pip provides it) and the model, one installation at a time."""
    directory = Path(directory)
    with try_file_lock(str(directory / LOCK)) as acquired:
        if not acquired:
            raise RuntimeError("Ya hay una descarga de OpenVINO en curso.")
        _require_free_space(directory, include_model)
        if importlib.util.find_spec("openvino_genai") is None:
            runtime_downloader(directory, log)
        if include_model:
            if model_downloader is None:
                from .openvino_models import download_openvino_model as model_downloader
            model_downloader(directory, settings, log)


def probe_runtime(directory):
    """Import the runtime and return the OpenVINO devices; raises with the real cause on failure."""
    problem = activate_runtime(directory)
    if problem:
        raise RuntimeError(problem)
    import openvino
    importlib.import_module("openvino_genai")
    return list(openvino.Core().available_devices)
