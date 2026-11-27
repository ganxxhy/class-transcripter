"""Local recording output adapters."""
import json
import os
import tempfile
import wave


def write_status(data_path, status):
    os.makedirs(data_path, exist_ok=True)
    fd, path = tempfile.mkstemp(dir=data_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(status, handle, ensure_ascii=False)
        os.replace(path, os.path.join(data_path, "estado_agente.json"))
    finally:
        if os.path.exists(path):
            os.unlink(path)


def open_wave(data_path, class_id, sample_rate):
    directory = os.path.join(data_path, "audio")
    os.makedirs(directory, exist_ok=True)
    output = wave.open(os.path.join(directory, class_id + ".wav"), "wb")
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(sample_rate)
    return output
