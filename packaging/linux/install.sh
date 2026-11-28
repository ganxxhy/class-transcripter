#!/usr/bin/env bash
# Instala Estudio desde el código en Linux: entorno virtual, lanzador del menú y arranque con la sesión.
# Uso: bash packaging/linux/install.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$RAIZ"

# Python 3.12 o 3.13: las bibliotecas de transcripción aún no están para versiones más nuevas
PY=""
for c in python3.12 python3.13 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(not ((3, 10) <= sys.version_info[:2] <= (3, 13)))'; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Hace falta Python entre 3.10 y 3.13 (con venv y tkinter)." >&2
  echo "  Debian/Ubuntu: sudo apt install python3 python3-venv python3-tk" >&2
  echo "  Fedora:        sudo dnf install python3 python3-tkinter" >&2
  echo "  Arch:          sudo pacman -S python tk" >&2
  exit 1
fi
"$PY" -c 'import tkinter' 2>/dev/null || { echo "Falta tkinter (python3-tk / python3-tkinter / tk)." >&2; exit 1; }

# PortAudio lo usa sounddevice para grabar; las ventanas web usan el WebKitGTK del sistema (con PyGObject)
"$PY" - <<'PYEOF' || true
import ctypes.util
if not ctypes.util.find_library("portaudio"):
    print("Aviso: no encuentro PortAudio. Debian/Ubuntu: libportaudio2 · Fedora: portaudio · Arch: portaudio")
try:
    import gi
    for v in ("4.1", "4.0"):
        try:
            gi.require_version("WebKit2", v)
            break
        except ValueError:
            pass
    else:
        raise ValueError
except Exception:
    print("Aviso: falta WebKitGTK con PyGObject para las ventanas del asistente.")
    print("  Debian/Ubuntu: sudo apt install python3-gi gir1.2-webkit2-4.1 · Fedora: sudo dnf install python3-gobject webkit2gtk4.1 · Arch: sudo pacman -S python-gobject webkit2gtk-4.1")
PYEOF

echo "Creando el entorno virtual…"
"$PY" -m venv --system-site-packages .venv  # así ve el PyGObject de la distribución
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r agente/requirements.txt

echo "Creando el lanzador del menú y el arranque con la sesión…"
.venv/bin/python agente/app.py --integrar
.venv/bin/python agente/app.py --registrar-mcp || true

echo "Descargando el modelo de voz (hasta 1,6 GB la primera vez)…"
.venv/bin/python agente/app.py --descargar-modelo || true

echo "Estudio Hub: abre su acceso directo o ejecuta .venv/bin/python agente/app.py --hub"
echo "Listo. Abre «Estudio» desde el menú de aplicaciones, o ejecuta: .venv/bin/python agente/app.py"
