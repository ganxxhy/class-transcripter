"""Shared setup for the pywebview windows (the assistant and the update notice).

On Windows pywebview uses Edge WebView2. On Linux it uses the system's WebKitGTK, so the
AppImage does not have to ship a whole browser engine (that was ~170 MB of Chromium).
"""
import os
import sys

LINUX = sys.platform.startswith("linux")
GUI = "gtk" if LINUX else None

TYPELIBS = (
    "/usr/lib/girepository-1.0",  # Arch, Alpine
    "/usr/lib64/girepository-1.0",  # Fedora, openSUSE
    "/usr/lib/x86_64-linux-gnu/girepository-1.0",  # Debian, Ubuntu
    "/usr/local/lib/girepository-1.0",
    "/usr/local/lib64/girepository-1.0",
)

MENSAJE_SIN_WEBKIT = (
    "Estudio necesita WebKitGTK para mostrar sus ventanas y no lo encuentra en este sistema.\n\n"
    "Instálalo y vuelve a abrir Estudio:\n\n"
    "• Debian / Ubuntu / Mint:  sudo apt install gir1.2-webkit2-4.1\n"
    "• Fedora:  sudo dnf install webkit2gtk4.1\n"
    "• Arch / Manjaro:  sudo pacman -S webkit2gtk-4.1 gobject-introspection-runtime\n"
    "• openSUSE:  sudo zypper install typelib-1_0-WebKit2-4_1"
)


def importar_webview():
    """Imports pywebview, first letting the frozen app find the system's WebKitGTK typelibs."""
    if LINUX and getattr(sys, "frozen", False):
        # PyInstaller points GI_TYPELIB_PATH at its own (empty) folder, and the libgirepository that travels
        # in the bundle only knows Ubuntu's paths: give it the ones used by the main distributions
        carpetas = [c for c in TYPELIBS if os.path.isdir(c)]
        os.environ["GI_TYPELIB_PATH"] = os.pathsep.join(carpetas)
    import webview
    return webview


def iniciar(webview):
    """webview.start() for this platform. Returns False (after telling the user) if WebKitGTK is missing."""
    try:
        webview.start(gui=GUI)
    except webview.errors.WebViewException:
        if not LINUX:
            raise
        avisar_sin_webkit()
        return False
    return True


def avisar_sin_webkit():
    print(MENSAJE_SIN_WEBKIT, file=sys.stderr)
    try:
        import tkinter as tk
        from tkinter import messagebox
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror("Estudio", MENSAJE_SIN_WEBKIT, parent=raiz)
        raiz.destroy()
    except Exception:
        pass  # sin pantalla: ya está en la salida de errores
