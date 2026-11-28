"""Linux desktop integration: menu launcher and autostart (.desktop files).

- install(): writes the launcher, the icon and (optionally) the autostart entry.
- uninstall(): removes them.
- refresh_if_stale(): rewrites them if the AppImage was moved, since they point at its path.
Run it from the app: `--integrar` / `--quitar-integracion`.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
NAME = "estudio"


def launch_command():
    """Command that starts the app: the AppImage, or the source checkout's venv."""
    if os.environ.get("APPIMAGE"):
        return [os.environ["APPIMAGE"]]
    venv = os.path.join(os.path.dirname(AQUI), ".venv", "bin", "python")
    return [venv if os.path.exists(venv) else sys.executable, os.path.join(AQUI, "app.py")]


def _quote(arg):
    """Quoting for the Exec key of a .desktop file."""
    if not any(c in arg for c in ' \t\n"\'\\><~|&;$*?#()`'):
        return arg
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$") + '"'


def _paths():
    home = os.path.expanduser("~")
    data = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    conf = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return {
        "hub_launcher": os.path.join(data, "applications", "estudio-hub.desktop"),
        "hub_icon": os.path.join(data, "icons", "hicolor", "256x256", "apps", "estudio-hub.png"),
        "launcher": os.path.join(data, "applications", f"{NAME}.desktop"),
        "icon": os.path.join(data, "icons", "hicolor", "256x256", "apps", f"{NAME}.png"),
        "autostart": os.path.join(conf, "autostart", f"{NAME}.desktop"),
    }


def _entry(extra_args, hidden_hint="", hub=False):
    exec_line = " ".join(_quote(a) for a in launch_command() + extra_args)
    name = "Estudio Hub" if hub else "Estudio"
    icon = "estudio-hub" if hub else NAME
    return (f"[Desktop Entry]\nType=Application\nName={name}\n"
            f"Comment={'Consulta y gestiona tus clases' if hub else 'Graba, transcribe y resume tus clases'}\n"
            f"Exec={exec_line}\nIcon={icon}\nTerminal=false\nCategories=Education;AudioVideo;\n"
            f"{hidden_hint}")


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def install(autostart=True):
    p = _paths()
    _write(p["launcher"], _entry([]))
    _write(p["hub_launcher"], _entry(["--hub"], hub=True))
    try:
        import tema
        os.makedirs(os.path.dirname(p["icon"]), exist_ok=True)
        tema.icono(256).save(p["icon"])
        tema.hub_icon(256).save(p["hub_icon"])
    except Exception:
        pass  # without PIL the launcher still works, just with a generic icon
    if autostart:
        _write(p["autostart"], _entry(["--inicio"], "X-GNOME-Autostart-enabled=true\n"))


def uninstall():
    for ruta in _paths().values():
        try:
            os.remove(ruta)
        except FileNotFoundError:
            pass


def refresh_if_stale():
    """If the AppImage moved, the launcher and autostart entries point at a dead path."""
    appimage = os.environ.get("APPIMAGE")
    p = _paths()
    if not appimage or not os.path.exists(p["launcher"]):
        return
    with open(p["launcher"], encoding="utf-8") as f:
        if _quote(appimage) in f.read() and os.path.exists(p["hub_launcher"]) and os.path.exists(p["hub_icon"]):
            return
    install(autostart=os.path.exists(p["autostart"]))
