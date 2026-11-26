import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTE = os.path.join(ROOT, "agente")


def _run(code, **env):
    """Run code in a fresh interpreter, since config computes its paths on import."""
    e = {k: v for k, v in os.environ.items() if k not in ("AGENTE_CLASES_DATOS", "APPIMAGE")}
    e.update(env)
    out = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {AGENTE!r}); {code}"],
                         capture_output=True, text=True, env=e, check=True)
    return json.loads(out.stdout)


def test_xdg_paths():
    with tempfile.TemporaryDirectory() as t:
        r = _run("import sys; sys.platform = 'linux'; sys.frozen = True; "
                 "from nucleo import config; print(__import__('json').dumps([config.RAIZ, config.RUTA_CONFIG]))",
                 XDG_DATA_HOME=t + "/d", XDG_CONFIG_HOME=t + "/c")
        assert r == [t + "/d/estudio", t + "/c/estudio/config.json"]


def test_data_env_wins():
    with tempfile.TemporaryDirectory() as t:
        r = _run("import sys; sys.platform = 'linux'; sys.frozen = True; "
                 "from nucleo import config; print(__import__('json').dumps([config.RAIZ, config.RUTA_CONFIG]))",
                 AGENTE_CLASES_DATOS=t)
        assert r == [t, t + "/config.json"]


def test_source_mode_unchanged():
    r = _run("from nucleo import config; print(__import__('json').dumps([config.RAIZ, config.RUTA_CONFIG]))")
    assert r == [AGENTE, os.path.join(AGENTE, "config.json")]


def test_mcp_entry_appimage():
    r = _run("import registrar_mcp; print(__import__('json').dumps(registrar_mcp.entrada()))",
             APPIMAGE="/home/u/Estudio.AppImage")
    assert r == {"command": "/home/u/Estudio.AppImage", "args": ["--mcp"]}


def test_claude_config_path_linux():
    with tempfile.TemporaryDirectory() as t:
        r = _run("import sys; sys.platform = 'linux'; import registrar_mcp; "
                 "print(__import__('json').dumps(registrar_mcp.configs_claude()))", XDG_CONFIG_HOME=t)
        assert os.path.join(t, "Claude", "claude_desktop_config.json") in r


def test_desktop_files():
    with tempfile.TemporaryDirectory() as t:
        r = _run("import os, json, linux_desktop as l; l.install(); p = l._paths(); "
                 "out = {k: os.path.exists(v) for k, v in p.items()}; "
                 "out['exec'] = [x for x in open(p['autostart'], encoding='utf-8').read().splitlines() if x.startswith('Exec=')][0]; "
                 "l.uninstall(); out['gone'] = not os.path.exists(p['autostart']); print(json.dumps(out))",
                 XDG_DATA_HOME=t + "/d", XDG_CONFIG_HOME=t + "/c", APPIMAGE="/home/u/Mi Estudio.AppImage")
        assert r["launcher"] and r["autostart"] and r["gone"]
        assert r["exec"] == 'Exec="/home/u/Mi Estudio.AppImage" --inicio'


def test_updater_picks_appimage_on_linux():
    r = _run("import sys; sys.platform = 'linux'; import actualizacion as a; "
             "rel = {'tag_name': 'v2.0.0', 'assets': [{'name': 'Estudio-2.0.0-instalador.exe', 'browser_download_url': 'win', 'size': 1}, "
             "{'name': 'Estudio-2.0.0-x86_64.AppImage', 'browser_download_url': 'linux', 'size': 2}]}; "
             "print(__import__('json').dumps(a._resumen(rel)['instalador']))")
    assert r == "linux"


def test_mcp_mode_answers_initialize():
    msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
           "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    with tempfile.TemporaryDirectory() as t:
        out = subprocess.run([sys.executable, os.path.join(AGENTE, "app.py"), "--mcp"], input=json.dumps(msg) + "\n",
                             capture_output=True, text=True, timeout=60, env={**os.environ, "AGENTE_CLASES_DATOS": t})
    assert "agente_clases" in out.stdout


if __name__ == "__main__":
    test_xdg_paths(); test_data_env_wins(); test_source_mode_unchanged()
    test_mcp_entry_appimage(); test_claude_config_path_linux(); test_desktop_files(); test_updater_picks_appimage_on_linux(); test_mcp_mode_answers_initialize()
    print("OK")
