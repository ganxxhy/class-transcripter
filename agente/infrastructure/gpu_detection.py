"""Detect GPU vendors without loading any GPU runtime."""
import glob
import os
from pathlib import Path
import re
import subprocess
import sys

VENDOR_IDS = {0x8086: "intel", 0x1002: "amd", 0x10DE: "nvidia"}
_POWERSHELL = "(Get-CimInstance Win32_VideoController).PNPDeviceID"


def _vendors_from_ids(ids):
    return sorted({VENDOR_IDS[i] for i in ids if i in VENDOR_IDS})


def _linux_vendor_ids(drm_root):
    ids = []
    for path in glob.glob(os.path.join(drm_root, "card*", "device", "vendor")):
        if not re.fullmatch(r"card\d+", Path(path).parents[1].name):  # skip connectors such as card1-eDP-1
            continue
        try:
            with open(path, encoding="ascii") as file:
                ids.append(int(file.read().strip(), 16))
        except (OSError, ValueError):
            continue
    return ids


def _windows_vendor_ids(run):
    output = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL],
                 capture_output=True, text=True, timeout=15,
                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    return [int(match, 16) for match in re.findall(r"VEN_([0-9A-Fa-f]{4})", output)]


def detect_gpu_vendors(platform=sys.platform, drm_root="/sys/class/drm", run=subprocess.run):
    """Return the sorted vendors present ('intel', 'amd', 'nvidia'); empty when unknown."""
    try:
        if platform == "win32":
            return _vendors_from_ids(_windows_vendor_ids(run))
        if platform.startswith("linux"):
            return _vendors_from_ids(_linux_vendor_ids(drm_root))
    except Exception:
        pass
    return []
