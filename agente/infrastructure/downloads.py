"""Verified file download shared by the optional engine installers."""
import hashlib
import os
from pathlib import Path
import urllib.request


def fetch_verified(name, url, size, digest, directory, log, opener=urllib.request.urlopen, chunk_size=1 << 20):
    """Download url to directory/name through a .part file; raise on a size or SHA-256 mismatch."""
    directory = Path(directory)
    final = directory / name
    part = directory / f"{name}.part"
    request = urllib.request.Request(url, headers={"User-Agent": "Estudio"})
    sha = hashlib.sha256()
    received = 0
    next_report = 10
    try:
        with opener(request, timeout=60) as response, open(part, "wb") as out:
            while True:
                block = response.read(chunk_size)
                if not block:
                    break
                out.write(block)
                sha.update(block)
                received += len(block)
                while size and received * 100 // size >= next_report <= 100:
                    log(f"Descargando {name}: {next_report} %")
                    next_report += 10
        if received != size or sha.hexdigest() != digest:
            raise RuntimeError(f"Descarga corrupta: {name}")
        os.replace(part, final)
    finally:
        part.unlink(missing_ok=True)
