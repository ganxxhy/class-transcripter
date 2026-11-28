"""--comprobar: loads, inside the frozen app, everything it needs at run time.

recortar.sh removes libraries from the bundle and ldd cannot see the ones loaded with dlopen, so the CI
runs this in the real AppImage. Exits with 1 if anything fails to load.
"""
import sys


def main():
    fallos = []

    def probar(nombre, f):
        try:
            f()
            print(f"ok      {nombre}")
        except Exception as e:  # noqa: BLE001
            fallos.append(nombre)
            print(f"FALLA   {nombre}: {type(e).__name__}: {e}")

    def importar(*mods):
        def f():
            for m in mods:
                __import__(m)
        return f

    def audio():
        import sounddevice
        sounddevice.query_devices()  # abre PortAudio

    def transcripcion():
        import ctranslate2
        ctranslate2.get_supported_compute_types("cpu")
        import onnxruntime
        onnxruntime.get_available_providers()

    probar("tkinter", importar("tkinter", "tkinter.ttk"))
    probar("imagen (Pillow, ImageTk)", importar("PIL.Image", "PIL.ImageTk"))
    probar("audio (PortAudio)", audio)
    probar("transcripción (ctranslate2, onnxruntime)", transcripcion)
    probar("faster-whisper y av", importar("faster_whisper", "av"))
    probar("resumen (anthropic)", importar("anthropic"))
    probar("icono de bandeja (pystray)", importar("pystray"))
    if sys.platform.startswith("linux"):
        import ventana_web
        probar("ventanas web (WebKitGTK)", lambda: (ventana_web.importar_webview(), __import__("webview.platforms.gtk")))
    sys.exit(1 if fallos else 0)


def openvino():
    """--comprobar-openvino: import the downloaded OpenVINO runtime inside the frozen app and list its devices."""
    from pathlib import Path
    from infrastructure.openvino_runtime import probe_runtime
    from nucleo.config import RUTA_DATOS
    try:
        message = f"ok openvino {probe_runtime(Path(RUTA_DATOS) / 'openvino')}"
        code = 0
    except Exception as e:  # noqa: BLE001
        message = f"FALLA openvino: {type(e).__name__}: {e}"
        code = 1
    print(message)
    Path(RUTA_DATOS).mkdir(parents=True, exist_ok=True)
    (Path(RUTA_DATOS) / "comprobar-openvino.txt").write_text(message + "\n", encoding="utf-8")
    sys.exit(code)
