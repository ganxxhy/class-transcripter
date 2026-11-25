"""Añade el servidor MCP "agente_clases" a la configuración de la app de escritorio de Claude."""
import glob
import json
import os
import shutil
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(RAIZ, ".venv", "Scripts", "python.exe")
if not os.path.exists(PY):
    PY = sys.executable
ENTRADA = {"command": PY, "args": [os.path.join(RAIZ, "mcp_servidor.py")]}

candidatas = []
appdata = os.environ.get("APPDATA")
local = os.environ.get("LOCALAPPDATA")
if appdata:
    candidatas.append(os.path.join(appdata, "Claude", "claude_desktop_config.json"))
if local:  # versión de la Microsoft Store
    for d in glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude")):
        candidatas.append(os.path.join(d, "claude_desktop_config.json"))

if local:  # versiones nuevas: %LOCALAPPDATA%\Claude-Data\claude_xxxx\
    for d in glob.glob(os.path.join(local, "Claude-Data", "*")):
        if os.path.isdir(d):
            candidatas.append(os.path.join(d, "claude_desktop_config.json"))

hechas = 0
for ruta in candidatas:
    carpeta = os.path.dirname(ruta)
    if not os.path.isdir(carpeta):
        continue
    cfg = {}
    if os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            print(f"No toco {ruta}: no es JSON válido ({e})")
            continue
        shutil.copy2(ruta, ruta + ".antes-agente-clases")
    cfg.setdefault("mcpServers", {})["agente_clases"] = ENTRADA
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"Registrado en {ruta}")
    hechas += 1

if not hechas:
    print("No encuentro la app de escritorio de Claude. Instálala y vuelve a ejecutar este script.")
else:
    print("Cierra del todo la app de Claude (también desde el icono junto al reloj) y vuelve a abrirla.")
