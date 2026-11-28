"""Transcription device options shown in Settings; stored values keep the `dispositivo` config key."""

DEVICE_CHOICES = (
    ("auto", "Automático (NVIDIA, luego Intel/AMD opcional, luego CPU)"),
    ("cpu", "Solo CPU"),
    ("cuda", "GPU NVIDIA (CUDA)"),
    ("openvino", "GPU Intel (OpenVINO, opcional)"),
    ("vulkan", "GPU Intel o AMD (Vulkan, opcional)"),
)


def device_label(value):
    """Return the label for a stored value; unknown hand-edited values are shown as they are."""
    return dict(DEVICE_CHOICES).get(value, str(value))


def device_value(label, current="auto"):
    """Return the stored value for a label, keeping `current` if the label is not a known option."""
    for value, text in DEVICE_CHOICES:
        if text == label:
            return value
    return current
