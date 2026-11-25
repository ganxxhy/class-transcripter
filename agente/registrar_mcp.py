"""Añade el servidor MCP "agente_clases" a la configuración de la app de escritorio de Claude,
para que el hub "Mis clases" pueda leer las clases de este ordenador.

Se usa desde el instalador (AgenteClases.exe --registrar-mcp) o a mano (python registrar_mcp.py).
"""
import glob
import json
import os
import shutil
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))


def entrada():
    """Cómo arranca la app de Claude el servidor MCP."""
    if getattr(sys, "frozen", False):
        # App instalada: agente-mcp.exe va junto a AgenteClases.exe
        return {"command": os.path.join(os.path.dirname(sys.executable), "agente-mcp.exe"), "args": []}
    py = os.path.join(RAIZ, ".venv", "Scripts", "python.exe")
    if not os.path.exists(py):
        py = sys.executable
    return {"command": py, "args": [os.path.join(RAIZ, "mcp_servidor.py")]}


def configs_claude():
    candidatas = []
    appdata = os.environ.get("APPDATA")
    local = os.environ.get("LOCALAPPDATA")
    if appdata:
        candidatas.append(os.path.join(appdata, "Claude", "claude_desktop_config.json"))
    if local:  # versión de la Microsoft Store
        for d in glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude")):
            candidatas.append(os.path.join(d, "claude_desktop_config.json"))
        # versiones nuevas: %LOCALAPPDATA%\Claude-Data\claude_xxxx\
        for d in glob.glob(os.path.join(local, "Claude-Data", "*")):
            if os.path.isdir(d):
                candidatas.append(os.path.join(d, "claude_desktop_config.json"))
    return candidatas


def registrar(log=print, quitar=False):
    """Devuelve cuántas configuraciones se han tocado. Con quitar=True lo elimina (desinstalar)."""
    hechas = 0
    for ruta in configs_claude():
        if not os.path.isdir(os.path.dirname(ruta)):
            continue
        cfg = {}
        if os.path.exists(ruta):
            try:
                with open(ruta, encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception as e:
                log(f"No toco {ruta}: no es JSON válido ({e})")
                continue
            if not quitar:
                shutil.copy2(ruta, ruta + ".antes-agente-clases")
        elif quitar:
            continue
        servidores = cfg.setdefault("mcpServers", {})
        if quitar:
            if "agente_clases" not in servidores:
                continue
            servidores.pop("agente_clases")
        else:
            servidores["agente_clases"] = entrada()
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        log(f"{'Quitado de' if quitar else 'Registrado en'} {ruta}")
        hechas += 1
    return hechas


if __name__ == "__main__":
    quitar = "--quitar" in sys.argv
    if not registrar(quitar=quitar) and not quitar:
        print("No encuentro la app de escritorio de Claude. Instálala y vuelve a ejecutar este script.")
    elif not quitar:
        print("Cierra del todo la app de Claude (también desde el icono junto al reloj) y vuelve a abrirla.")
