"""Decide what Settings should tell the user about optional GPU acceleration (no UI code)."""
from collections import namedtuple

AccelerationStatus = namedtuple("AccelerationStatus", "vendors openvino_ready vulkan_installed pack_available install_running")
Advice = namedtuple("Advice", "text can_install")

USES_OPENVINO = ("auto", "openvino")


def acceleration_advice(status, device):
    """Return an Advice for the detected GPU vendors, or None when there is nothing to suggest."""
    if "nvidia" in status.vendors:  # auto tries CUDA first, so suggesting Intel would only cost the user a download
        return None
    if "intel" in status.vendors:
        if status.install_running:
            return Advice("Descargando la aceleración Intel en segundo plano…", False)
        if status.openvino_ready:
            if device in USES_OPENVINO:
                return Advice("GPU Intel detectada: la aceleración con OpenVINO está lista.", False)
            return Advice("GPU Intel detectada: OpenVINO está listo. Elige «Automático» o «GPU Intel (OpenVINO, opcional)» "
                          "en Dispositivo para usarlo.", False)
        if status.pack_available:
            return Advice("GPU Intel detectada. Con OpenVINO la transcripción puede ir bastante más rápida que en CPU. "
                          "Hay que descargar unos 1,7 GB (motor y modelo).", True)
        return Advice("GPU Intel detectada. En esta instalación OpenVINO se activa a mano: pip install openvino-genai "
                      "y --descargar-modelo-openvino (ver README).", False)
    if "amd" in status.vendors:
        if status.vulkan_installed:
            return Advice("GPU AMD detectada: el motor de Vulkan está instalado. Elige «GPU Intel o AMD (Vulkan, opcional)» "
                          "en Dispositivo para probarlo.", False)
        return Advice("GPU AMD detectada. Vulkan puede liberar la CPU, pero hay que compilar el motor y descargar los "
                      "modelos (ver README, sección Vulkan).", False)
    return None


def install_done_text(device):
    if device in USES_OPENVINO:
        return "Listo. Reinicia Estudio para usar OpenVINO."
    return "Listo. Elige «Automático» o «GPU Intel (OpenVINO, opcional)» en Dispositivo, guarda y reinicia Estudio."
