"""Transcription device options shown in Settings; stored values keep the `dispositivo` config key."""

DEVICE_CHOICES = (
    ("auto", "Automático"),
    ("cpu", "Solo CPU"),
    ("cuda", "GPU NVIDIA (CUDA)"),
    ("openvino", "GPU Intel (OpenVINO, opcional)"),
    ("vulkan", "GPU Intel o AMD (Vulkan, opcional)"),
)

DEVICE_HELP = {
    "auto": "Usa la GPU NVIDIA si hay; si no, la GPU Intel con OpenVINO si está instalado; y si no, la CPU.",
    "cpu": "Usa solo el procesador.",
    "cuda": "Usa la GPU NVIDIA; si falla, vuelve a la CPU.",
    "openvino": "Usa la GPU Intel con OpenVINO (opcional); si falla, vuelve a la CPU.",
    "vulkan": "Usa una GPU Intel o AMD con Vulkan (opcional, hay que compilar el motor); si falla, vuelve a la CPU.",
}


def device_help(value):
    """Return the explanation shown under the selector; hand-edited unknown values get none."""
    return DEVICE_HELP.get(value, "")


def device_label(value):
    """Return the label for a stored value; unknown hand-edited values are shown as they are."""
    return dict(DEVICE_CHOICES).get(value, str(value))


def device_value(label, current="auto"):
    """Return the stored value for a label, keeping `current` if the label is not a known option."""
    for value, text in DEVICE_CHOICES:
        if text == label:
            return value
    return current
