"""Read status files using the existing wire format."""
import json
import os


def read_status(data_path):
    def read(name, default):
        try:
            with open(os.path.join(data_path, name), encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return default
    return read("estado_agente.json", {"activo": False}), read("panel.json", None)
