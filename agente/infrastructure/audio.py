"""PortAudio device discovery and capture adapter."""
import sys

def microfonos(refrescar=False):
    """Entradas de audio de la API por defecto (en Windows, MME; en Linux, ALSA).
    Con refrescar=True vuelve a preguntar al sistema (para micros conectados después de abrir la app)."""
    import sounddevice as sd
    if refrescar:
        try:
            sd._terminate()
            sd._initialize()
        except Exception:
            pass
    try:
        por_defecto = sd.default.device[0]
        api_def = sd.query_devices(por_defecto)["hostapi"] if por_defecto is not None and por_defecto >= 0 else 0
    except Exception:
        por_defecto, api_def = None, 0
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and d["hostapi"] == api_def:
            out.append({"indice": i, "nombre": d["name"], "defecto": i == por_defecto})
    if sys.platform.startswith("linux"):  # sound servers first, raw ALSA (hw:…) after
        out.sort(key=lambda m: SERVIDORES_SONIDO.index(m["nombre"]) if m["nombre"] in SERVIDORES_SONIDO else len(SERVIDORES_SONIDO))
    return out


# On Linux, PortAudio only exposes ALSA (and JACK). PipeWire and PulseAudio are reached through
# their ALSA plugin devices, so they are preferred by name and raw ALSA is the last resort.
SERVIDORES_SONIDO = ("pipewire", "pulse")


def _microfono_linux(lista):
    """Index of the PipeWire device, else PulseAudio, else None (the system default)."""
    for nombre in SERVIDORES_SONIDO:
        m = next((m for m in lista if m["nombre"] == nombre), None)
        if m:
            return m["indice"]
    return None


def buscar_microfono(eleccion, log=print):
    """Convierte lo guardado en config (nombre del micro, o None = el del sistema) en un índice."""
    if eleccion is None or eleccion == "":
        return _microfono_linux(microfonos()) if sys.platform.startswith("linux") else None
    for m in microfonos():
        if m["nombre"] == eleccion or m["indice"] == eleccion:
            return m["indice"]
    log(f"No encuentro el micrófono «{eleccion}»; uso el predeterminado del sistema.")
    return None



class SoundDeviceInput:
    def open(self, selection, callback, log):
        import sounddevice as sd
        device = buscar_microfono(selection, log)
        info = sd.query_devices(device, "input")
        rate = int(info["default_samplerate"])

        def on_audio(data, frames, timing, status):
            callback(rate, data[:, 0].copy())

        stream = sd.InputStream(device=device, channels=1, samplerate=rate,
                                dtype="float32", blocksize=int(rate * 0.25),
                                callback=on_audio)
        try:
            stream.start()
        except Exception:
            stream.close()
            raise
        name = info["name"] + ("" if device is not None else " (predeterminado)")
        return stream, name
